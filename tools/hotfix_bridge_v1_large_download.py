from pathlib import Path

bridge = Path('shared/google-drive-bridge/bridge.gs')
s = bridge.read_text(encoding='utf-8')

old_poll_head = """function largeDownloadPoll_(p, cfg) {
  const ticket = cleanId_(p.download_ticket, 'download_ticket');
"""
new_poll_head = """function largeDownloadPoll_(p, cfg) {
  if (String(p.mode || '') === 'range_chunk') return largeDownloadChunk_(p, cfg);
  const ticket = cleanId_(p.download_ticket, 'download_ticket');
"""
if old_poll_head in s:
    s = s.replace(old_poll_head, new_poll_head, 1)
elif "mode || '') === 'range_chunk'" not in s:
    raise RuntimeError('largeDownloadPoll_ patch anchor not found')

marker = "function validateLargeDownloadMeta_(meta) {\n"
helper = r'''function largeDownloadChunk_(p, cfg) {
  const fileId = cleanId_(p.file_id, 'file_id');
  assertFileInsideRoot_(fileId, cfg);
  const meta = rawMetadata_(fileId);
  validateLargeDownloadMeta_(meta);

  const total = Number(meta.size);
  const offset = Number(p.offset);
  const requested = Number(p.length || (4 * 1024 * 1024));
  const maxChunk = 4 * 1024 * 1024;
  if (!Number.isInteger(offset) || offset < 0 || offset >= total) {
    throw bridgeError_('INVALID_RANGE', 'large-download offset is outside file bounds', false);
  }
  if (!Number.isInteger(requested) || requested < 1 || requested > maxChunk) {
    throw bridgeError_('INVALID_RANGE', 'large-download chunk length is invalid', false);
  }
  const end = Math.min(total - 1, offset + requested - 1);
  const headers = {
    Authorization: 'Bearer ' + ScriptApp.getOAuthToken(),
    Accept: 'application/octet-stream',
    Range: 'bytes=' + offset + '-' + end
  };
  if (meta.resourceKey) headers['X-Goog-Drive-Resource-Keys'] = fileId + '/' + String(meta.resourceKey);
  const url = 'https://www.googleapis.com/drive/v3/files/' + encodeURIComponent(fileId) + '?alt=media';
  const response = UrlFetchApp.fetch(url, {
    method: 'get',
    headers: headers,
    muteHttpExceptions: true,
    followRedirects: true
  });
  const code = response.getResponseCode();
  if (code !== 200 && code !== 206) {
    throw bridgeError_('LARGE_DOWNLOAD_CHUNK_FAILED', 'Drive range fetch failed with HTTP ' + code, retryableHttp_(code));
  }
  const bytes = response.getContent();
  const expectedLength = end - offset + 1;
  if (bytes.length !== expectedLength) {
    throw bridgeError_('LARGE_DOWNLOAD_CHUNK_SIZE_MISMATCH', 'Drive range fetch returned unexpected byte count', true);
  }
  return {
    mode: 'range_chunk',
    file_id: fileId,
    offset: offset,
    next_offset: offset + bytes.length,
    total_bytes: total,
    eof: offset + bytes.length >= total,
    content_base64: Utilities.base64Encode(bytes),
    sha256: String(meta.sha256Checksum || '').toLowerCase(),
    mime_type: String(meta.mimeType || ''),
    modified_time: String(meta.modifiedTime || '')
  };
}

'''
if 'function largeDownloadChunk_(p, cfg)' not in s:
    if marker not in s:
        raise RuntimeError('large download helper anchor not found')
    s = s.replace(marker, helper + marker, 1)
bridge.write_text(s, encoding='utf-8')

client = Path('shared/google-drive-bridge/python_client/bridge_client.py')
c = client.read_text(encoding='utf-8')
start = c.index('    async def download_large_by_id(\n')
end = c.index('    async def upload_resumable_chunks(\n', start)
replacement = r'''    async def download_large_by_id(
        self,
        file_id: str,
        *,
        max_bytes: int = 512 * 1024 * 1024,
        max_polls: int = 30,
        poll_seconds: float = 2.0,
        chunk_size: int = 4 * 1024 * 1024,
    ) -> tuple[dict[str, Any], bytes]:
        """Download a Drive blob without exposing the Apps Script OAuth token.

        Apps Script authenticates and validates the fixed-root boundary, brokers the
        Drive files.download LRO, and fetches bounded authenticated byte ranges.
        The Google OAuth credential never leaves Apps Script.
        """
        state = await self.large_download_start(file_id)
        for poll_index in range(max_polls + 1):
            if state.get("ready") is True:
                break
            ticket = str(state.get("download_ticket") or "").strip()
            if not ticket:
                raise BridgeError("DOWNLOAD_TICKET_MISSING", "bridge returned no download ticket", retryable=True)
            if poll_index >= max_polls:
                raise BridgeError("LARGE_DOWNLOAD_NOT_READY", "Drive download operation did not become ready", retryable=True)
            await asyncio.sleep(max(0.1, float(poll_seconds)))
            state = await self.large_download_poll(ticket)
        else:
            raise BridgeError("LARGE_DOWNLOAD_NOT_READY", "Drive download operation did not become ready", retryable=True)

        expected_size = int(state.get("total_bytes") if state.get("total_bytes") is not None else -1)
        expected_sha = str(state.get("sha256") or "").strip().lower()
        if expected_size < 0:
            raise BridgeError("SIZE_UNAVAILABLE", "bridge returned no valid large-download size", retryable=False)
        if expected_size > int(max_bytes):
            raise BridgeError("DOWNLOAD_TOO_LARGE", f"large download exceeds client safety limit {max_bytes}", retryable=False)
        if not _is_sha256(expected_sha):
            raise BridgeError("SHA256_UNAVAILABLE", "bridge returned no valid large-download SHA256", retryable=False)

        buffer = bytearray()
        hasher = hashlib.sha256()
        offset = 0
        per_chunk = max(1, min(int(chunk_size), 4 * 1024 * 1024))
        while offset < expected_size:
            length = min(per_chunk, expected_size - offset)
            part = await self.call(
                "large_download_poll",
                {"mode": "range_chunk", "file_id": file_id, "offset": offset, "length": length},
            )
            if str(part.get("mode") or "") != "range_chunk":
                raise BridgeError("INVALID_RESPONSE", "bridge returned invalid large-download chunk mode", retryable=False)
            if int(part.get("offset") if part.get("offset") is not None else -1) != offset:
                raise BridgeError("LARGE_DOWNLOAD_OFFSET_MISMATCH", "bridge returned unexpected chunk offset", retryable=False)
            if int(part.get("total_bytes") if part.get("total_bytes") is not None else -1) != expected_size:
                raise BridgeError("DOWNLOAD_SOURCE_CHANGED", "Drive file size changed during chunked download", retryable=True)
            if str(part.get("sha256") or "").strip().lower() != expected_sha:
                raise BridgeError("DOWNLOAD_SOURCE_CHANGED", "Drive file checksum changed during chunked download", retryable=True)
            try:
                chunk = base64.b64decode(str(part.get("content_base64") or ""), validate=True)
            except Exception as exc:
                raise BridgeError("INVALID_BASE64", "bridge returned invalid large-download chunk", retryable=False) from exc
            next_offset = int(part.get("next_offset") if part.get("next_offset") is not None else -1)
            if not chunk or next_offset != offset + len(chunk) or len(chunk) > length:
                raise BridgeError("LARGE_DOWNLOAD_CHUNK_SIZE_MISMATCH", "bridge returned invalid chunk byte count", retryable=False)
            buffer.extend(chunk)
            hasher.update(chunk)
            offset = next_offset
            if len(buffer) > expected_size:
                raise BridgeError("SIZE_MISMATCH", "large download exceeded expected Drive size", retryable=False)

        raw = bytes(buffer)
        if len(raw) != expected_size:
            raise BridgeError("SIZE_MISMATCH", f"large download size mismatch: {len(raw)} != {expected_size}", retryable=False)
        if hasher.hexdigest() != expected_sha:
            raise BridgeError("SHA256_MISMATCH", "large download SHA256 mismatch", retryable=False)
        metadata = {
            "id": file_id,
            "size": expected_size,
            "sha256_checksum": expected_sha,
            "mime_type": state.get("mime_type"),
            "modified_time": state.get("modified_time"),
            "partial_download_allowed": bool(state.get("partial_download_allowed")),
        }
        return metadata, raw

'''
c = c[:start] + replacement + c[end:]
client.write_text(c, encoding='utf-8')

protocol = Path('shared/google-drive-bridge/PROTOCOL.md')
p = protocol.read_text(encoding='utf-8')
note = "\n> Security note (v1.0.0 hotfix): the final Google Drive content URL requires Google OAuth authorization. Bridge v1 never forwards `ScriptApp.getOAuthToken()` to Yandex clients. After `large_download_start` / `large_download_poll` report LRO readiness, bounded authenticated range chunks are fetched inside Apps Script via `large_download_poll` with `mode=range_chunk`. Exact final size and SHA256 remain mandatory.\n"
if 'mode=range_chunk' not in p:
    p += note
protocol.write_text(p, encoding='utf-8')

print('BRIDGE_V1_AUTHENTICATED_RANGE_PROXY_PATCH=PASS')
