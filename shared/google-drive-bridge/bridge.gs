/**
 * Yandex Cloud <-> Google Drive Bridge
 * Protocol v1 / release 1.0.0-alpha.2
 *
 * Same source is deployed separately for every client project.
 * Required Script Properties:
 *   MCP_DRIVE_BRIDGE_SECRET
 *   MCP_DRIVE_BRIDGE_PROJECT_ID
 *   MCP_DRIVE_BRIDGE_ROOT_ID
 *   MCP_DRIVE_BRIDGE_ROOT_NAME
 *
 * Optional Script Properties:
 *   MCP_DRIVE_BRIDGE_SMALL_MAX_BYTES (default 5 MiB)
 *   MCP_DRIVE_BRIDGE_SHEETS_ENABLED (true|false)
 */
const BRIDGE_PROTOCOL_VERSION = 1;
const BRIDGE_RELEASE = '1.0.0-alpha.2';
const PROP_SECRET = 'MCP_DRIVE_BRIDGE_SECRET';
const PROP_PROJECT = 'MCP_DRIVE_BRIDGE_PROJECT_ID';
const PROP_ROOT_ID = 'MCP_DRIVE_BRIDGE_ROOT_ID';
const PROP_ROOT_NAME = 'MCP_DRIVE_BRIDGE_ROOT_NAME';
const PROP_SMALL_MAX = 'MCP_DRIVE_BRIDGE_SMALL_MAX_BYTES';
const PROP_SHEETS = 'MCP_DRIVE_BRIDGE_SHEETS_ENABLED';
const DEFAULT_SMALL_MAX = 5 * 1024 * 1024;
const DOWNLOAD_TICKET_TTL_SECONDS = 21600;
const FOLDER_MIME = 'application/vnd.google-apps.folder';
const SHEET_MIME = 'application/vnd.google-apps.spreadsheet';
const SHORTCUT_MIME = 'application/vnd.google-apps.shortcut';
const GOOGLE_APPS_PREFIX = 'application/vnd.google-apps.';

function doGet() {
  try {
    const cfg = config_();
    return json_({
      ok: true,
      service: 'yandex-google-drive-bridge',
      protocol_version: BRIDGE_PROTOCOL_VERSION,
      bridge_release: BRIDGE_RELEASE,
      project_id: cfg.projectId,
      liveness: true
    });
  } catch (err) {
    return json_({ok: false, service: 'yandex-google-drive-bridge', liveness: false});
  }
}

function doPost(e) {
  let requestId = '';
  let action = '';
  let projectId = '';
  try {
    const body = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    requestId = cleanId_(body.request_id, 'request_id');
    action = String(body.action || '').trim().toLowerCase();
    projectId = String(body.project_id || '').trim();
    const cfg = config_();
    authorize_(body, cfg);
    const payload = body.payload && typeof body.payload === 'object' ? body.payload : {};
    const mutation = isMutation_(action);
    const idem = mutation ? cleanId_(body.idempotency_key, 'idempotency_key') : String(body.idempotency_key || '').trim();

    const result = dispatch_(action, payload, idem, cfg);
    return envelopeOk_(cfg, requestId, action, result);
  } catch (err) {
    const info = errorInfo_(err);
    return json_({
      ok: false,
      protocol_version: BRIDGE_PROTOCOL_VERSION,
      bridge_release: BRIDGE_RELEASE,
      project_id: projectId,
      request_id: requestId,
      action: action,
      error: info
    });
  }
}

function dispatch_(action, p, idem, cfg) {
  if (action === 'health') return health_(cfg);
  if (action === 'stat') return stat_(p, cfg);
  if (action === 'metadata_by_id') return metadataById_(p, cfg);
  if (action === 'read_small') return readSmall_(p, cfg);
  if (action === 'write_small') return writeSmall_(p, idem, cfg);
  if (action === 'trash_by_id') return trashById_(p, cfg);
  if (action === 'resumable_start') return resumableStart_(p, idem, cfg);
  if (action === 'promote_verified') return promoteVerified_(p, idem, cfg);
  if (action === 'large_download_start') return largeDownloadStart_(p, cfg);
  if (action === 'large_download_poll') return largeDownloadPoll_(p, cfg);
  if (action === 'sheet_ensure') return sheetEnsure_(p, idem, cfg);
  if (action === 'sheet_stage_begin') return sheetStageBegin_(p, idem, cfg);
  if (action === 'sheet_write_chunk') return sheetWriteChunk_(p, idem, cfg);
  if (action === 'sheet_verify') return sheetVerify_(p, cfg);
  if (action === 'sheet_commit') return sheetCommit_(p, idem, cfg);
  if (action === 'sheet_abort') return sheetAbort_(p, idem, cfg);
  throw bridgeError_('UNKNOWN_ACTION', 'unknown action', false);
}

function config_() {
  const props = PropertiesService.getScriptProperties();
  const injected = (typeof BRIDGE_DEPLOYMENT_CONFIG === 'object' && BRIDGE_DEPLOYMENT_CONFIG) ? BRIDGE_DEPLOYMENT_CONFIG : {};
  const secret = String(props.getProperty(PROP_SECRET) || injected.secret || '').trim();
  const projectId = String(props.getProperty(PROP_PROJECT) || injected.projectId || '').trim();
  const rootId = String(props.getProperty(PROP_ROOT_ID) || injected.rootId || '').trim();
  const rootName = String(props.getProperty(PROP_ROOT_NAME) || injected.rootName || '').trim();
  if (!secret || !projectId || !rootId || !rootName) throw bridgeError_('NOT_CONFIGURED', 'bridge deployment configuration is incomplete', false);
  const root = DriveApp.getFolderById(rootId);
  if (root.getName() !== rootName) throw bridgeError_('WRONG_ROOT', 'configured root name does not match Drive', false);
  const maxRaw = Number(props.getProperty(PROP_SMALL_MAX) || injected.smallMaxBytes || DEFAULT_SMALL_MAX);
  const maxBytes = Number.isFinite(maxRaw) && maxRaw > 0 ? Math.floor(maxRaw) : DEFAULT_SMALL_MAX;
  const sheetsRaw = props.getProperty(PROP_SHEETS);
  const sheetsEnabled = sheetsRaw === null ? Boolean(injected.sheetsEnabled) : String(sheetsRaw).toLowerCase() === 'true';
  return {secret: secret, projectId: projectId, rootId: rootId, rootName: rootName, maxBytes: maxBytes, sheetsEnabled: sheetsEnabled};
}

function authorize_(body, cfg) {
  if (!body.secret || String(body.secret) !== cfg.secret) throw bridgeError_('UNAUTHORIZED', 'unauthorized', false);
  if (!body.project_id || String(body.project_id).trim() !== cfg.projectId) throw bridgeError_('PROJECT_MISMATCH', 'project_id does not match this deployment', false);
}

function health_(cfg) {
  return {
    configured: true,
    reachable: true,
    protocol_version: BRIDGE_PROTOCOL_VERSION,
    bridge_release: BRIDGE_RELEASE,
    project_id: cfg.projectId,
    root_id: cfg.rootId,
    root_name: cfg.rootName,
    capabilities: {
      drive_small_io: true,
      drive_resumable_upload: true,
      drive_large_download: true,
      drive_large_download_transport: 'drive_files_download_lro',
      google_sheets_chunked: cfg.sheetsEnabled,
      fixed_root_file_id_guard: true,
      idempotent_mutations: true,
      global_script_lock: false
    },
    limits: {small_io_max_bytes: cfg.maxBytes}
  };
}

function stat_(p, cfg) {
  const path = normalizePath_(p.path || '');
  const filename = validateFilename_(p.filename);
  const folder = resolveFolder_(path, false, cfg);
  if (!folder) return {found: false};
  const it = folder.getFilesByName(filename);
  if (!it.hasNext()) return {found: false};
  const file = it.next();
  assertFileInsideRoot_(file.getId(), cfg);
  return {found: true, file: metadata_(file.getId(), cfg)};
}

function metadataById_(p, cfg) {
  const id = cleanId_(p.file_id, 'file_id');
  assertFileInsideRoot_(id, cfg);
  return {file: metadata_(id, cfg)};
}

function readSmall_(p, cfg) {
  const path = normalizePath_(p.path || '');
  const filename = validateFilename_(p.filename);
  const folder = resolveFolder_(path, false, cfg);
  if (!folder) return {found: false};
  const it = folder.getFilesByName(filename);
  if (!it.hasNext()) return {found: false};
  const file = it.next();
  assertFileInsideRoot_(file.getId(), cfg);
  const size = Number(file.getSize());
  if (size > cfg.maxBytes) throw bridgeError_('LARGE_READ_REQUIRED', 'file exceeds bounded Apps Script read limit', false);
  const bytes = file.getBlob().getBytes();
  return {found: true, file: metadata_(file.getId(), cfg), content_base64: Utilities.base64Encode(bytes), sha256: sha256HexBytes_(bytes)};
}

function writeSmall_(p, idem, cfg) {
  const path = normalizePath_(p.path || '');
  const filename = validateFilename_(p.filename);
  const mime = String(p.mime_type || 'application/octet-stream');
  const raw = String(p.content_base64 || '');
  let bytes;
  try { bytes = Utilities.base64Decode(raw); } catch (e) { throw bridgeError_('INVALID_BASE64', 'content_base64 is invalid', false); }
  if (bytes.length > cfg.maxBytes) throw bridgeError_('LARGE_WRITE_REQUIRED', 'payload exceeds bounded Apps Script write limit', false);
  const sha = sha256HexBytes_(bytes);
  if (p.sha256 && String(p.sha256).toLowerCase() !== sha) throw bridgeError_('SHA256_MISMATCH', 'request SHA256 does not match decoded bytes', false);
  const folder = resolveFolder_(path, true, cfg);

  const current = folder.getFilesByName(filename);
  while (current.hasNext()) {
    const f = current.next();
    const m = metadata_(f.getId(), cfg);
    if (Number(m.size) === bytes.length && String(m.sha256_checksum || '').toLowerCase() === sha) {
      return {file: m, sha256: sha, replayed: true};
    }
  }

  const stageName = '.bridge-stage-' + shortHash_(idem) + '-' + filename;
  let staged = findSingleByName_(folder, stageName);
  if (staged) {
    const sm = metadata_(staged.getId(), cfg);
    if (Number(sm.size) !== bytes.length || String(sm.sha256_checksum || '').toLowerCase() !== sha) {
      throw bridgeError_('IDEMPOTENCY_CONFLICT', 'existing staged object for idempotency key has different content', false);
    }
  } else {
    staged = folder.createFile(Utilities.newBlob(bytes, mime, stageName));
  }
  return promoteFile_(folder, staged.getId(), stageName, filename, bytes.length, sha, '', cfg);
}

function trashById_(p, cfg) {
  const id = cleanId_(p.file_id, 'file_id');
  const meta = rawMetadata_(id);
  if (!meta.trashed) assertFileInsideRoot_(id, cfg);
  if (!meta.trashed) Drive.Files.update({trashed: true}, id, {fields: 'id,trashed'});
  return {file_id: id, trashed: true};
}

function resumableStart_(p, idem, cfg) {
  const path = normalizePath_(p.path || '');
  const filename = validateFilename_(p.filename);
  const mime = String(p.mime_type || 'application/octet-stream');
  const total = Number(p.total_bytes);
  if (!Number.isFinite(total) || total < 0) throw bridgeError_('INVALID_SIZE', 'total_bytes is invalid', false);
  const folder = resolveFolder_(path, true, cfg);
  const stageName = '.bridge-upload-' + shortHash_(idem) + '-' + filename;
  let staged = findSingleByName_(folder, stageName);
  if (!staged) {
    const created = Drive.Files.create({name: stageName, parents: [folder.getId()], mimeType: mime}, null, {fields: 'id,name,parents,mimeType'});
    staged = DriveApp.getFileById(created.id);
  }
  assertFileInsideRoot_(staged.getId(), cfg);

  const url = 'https://www.googleapis.com/upload/drive/v3/files/' + encodeURIComponent(staged.getId()) + '?uploadType=resumable&supportsAllDrives=true&fields=id,name,size,sha256Checksum,parents';
  const response = UrlFetchApp.fetch(url, {
    method: 'patch',
    headers: {
      Authorization: 'Bearer ' + ScriptApp.getOAuthToken(),
      'Content-Type': 'application/json; charset=UTF-8',
      'X-Upload-Content-Type': mime,
      'X-Upload-Content-Length': String(total)
    },
    payload: JSON.stringify({name: stageName}),
    muteHttpExceptions: true,
    followRedirects: false
  });
  const code = response.getResponseCode();
  if (code < 200 || code >= 300) throw bridgeError_('RESUMABLE_START_FAILED', 'Drive resumable session start failed with HTTP ' + code, code === 429 || code >= 500);
  const headers = response.getAllHeaders();
  const sessionUri = String(headers.Location || headers.location || '').trim();
  if (!sessionUri) throw bridgeError_('RESUMABLE_START_FAILED', 'Drive returned no resumable session URI', true);
  return {file_id: staged.getId(), staging_filename: stageName, session_uri: sessionUri, total_bytes: total, mime_type: mime};
}

function promoteVerified_(p, idem, cfg) {
  const path = normalizePath_(p.path || '');
  const fileId = cleanId_(p.file_id, 'file_id');
  const stageName = validateFilename_(p.staging_filename);
  const canonicalName = validateFilename_(p.canonical_filename);
  const expectedBytes = Number(p.expected_bytes);
  const expectedSha = String(p.expected_sha256 || '').toLowerCase();
  const previous = String(p.previous_file_id || '').trim();
  const folder = resolveFolder_(path, false, cfg);
  if (!folder) throw bridgeError_('PARENT_NOT_FOUND', 'target parent does not exist', false);
  return promoteFile_(folder, fileId, stageName, canonicalName, expectedBytes, expectedSha, previous, cfg);
}

function promoteFile_(folder, fileId, stageName, canonicalName, expectedBytes, expectedSha, previousFileId, cfg) {
  assertFileInsideRoot_(fileId, cfg);
  const m = metadata_(fileId, cfg);
  if (m.name !== stageName && m.name !== canonicalName) throw bridgeError_('STAGING_NAME_MISMATCH', 'staged file has unexpected name', false);
  if (String((m.parents || [])[0] || '') !== folder.getId()) throw bridgeError_('PARENT_MISMATCH', 'staged file parent mismatch', false);
  if (Number(m.size) !== Number(expectedBytes)) throw bridgeError_('SIZE_MISMATCH', 'staged file byte count mismatch', false);
  if (expectedSha && String(m.sha256_checksum || '').toLowerCase() !== expectedSha) throw bridgeError_('SHA256_MISMATCH', 'staged Drive SHA256 mismatch', false);

  let oldId = String(previousFileId || '').trim();
  if (oldId) {
    assertFileInsideRoot_(oldId, cfg);
  } else {
    const it = folder.getFilesByName(canonicalName);
    while (it.hasNext()) {
      const old = it.next();
      if (old.getId() !== fileId) { oldId = old.getId(); break; }
    }
  }

  if (m.name !== canonicalName) Drive.Files.update({name: canonicalName}, fileId, {fields: 'id,name'});
  let previousTrashed = !oldId || oldId === fileId;
  if (oldId && oldId !== fileId) {
    const oldMeta = rawMetadata_(oldId);
    if (!oldMeta.trashed) {
      assertFileInsideRoot_(oldId, cfg);
      Drive.Files.update({trashed: true}, oldId, {fields: 'id,trashed'});
    }
    previousTrashed = true;
  }
  return {file: metadata_(fileId, cfg), sha256: expectedSha, previous_file_trashed: previousTrashed, promoted: true};
}

function largeDownloadStart_(p, cfg) {
  const fileId = cleanId_(p.file_id, 'file_id');
  assertFileInsideRoot_(fileId, cfg);
  const meta = rawMetadata_(fileId);
  validateLargeDownloadMeta_(meta);
  const operation = startDriveDownloadOperation_(fileId, meta.resourceKey || '');
  if (operation.done === true) {
    return completedDownloadResult_(operation, meta, fileId, '');
  }

  const operationName = validateOperationName_(operation.name);
  const ticket = Utilities.getUuid().replace(/-/g, '');
  const binding = {
    file_id: fileId,
    operation_name: operationName,
    size: Number(meta.size),
    sha256: String(meta.sha256Checksum || '').toLowerCase(),
    modified_time: String(meta.modifiedTime || ''),
    resource_key: String(meta.resourceKey || ''),
    mime_type: String(meta.mimeType || '')
  };
  CacheService.getScriptCache().put(downloadTicketKey_(ticket), JSON.stringify(binding), DOWNLOAD_TICKET_TTL_SECONDS);
  return {
    ready: false,
    download_ticket: ticket,
    file_id: fileId,
    total_bytes: binding.size,
    sha256: binding.sha256,
    mime_type: binding.mime_type,
    modified_time: binding.modified_time
  };
}

function largeDownloadPoll_(p, cfg) {
  const ticket = cleanId_(p.download_ticket, 'download_ticket');
  const cache = CacheService.getScriptCache();
  const raw = cache.get(downloadTicketKey_(ticket));
  if (!raw) throw bridgeError_('DOWNLOAD_TICKET_EXPIRED', 'download ticket is missing or expired; restart large_download_start', true);
  let binding;
  try { binding = JSON.parse(raw); } catch (err) { throw bridgeError_('DOWNLOAD_TICKET_INVALID', 'download ticket state is invalid', true); }

  const fileId = cleanId_(binding.file_id, 'file_id');
  assertFileInsideRoot_(fileId, cfg);
  const meta = rawMetadata_(fileId);
  validateLargeDownloadMeta_(meta);
  if (Number(meta.size) !== Number(binding.size) ||
      String(meta.sha256Checksum || '').toLowerCase() !== String(binding.sha256 || '').toLowerCase() ||
      String(meta.modifiedTime || '') !== String(binding.modified_time || '')) {
    cache.remove(downloadTicketKey_(ticket));
    throw bridgeError_('DOWNLOAD_SOURCE_CHANGED', 'Drive file changed while preparing direct download', true);
  }

  const operation = pollDriveDownloadOperation_(validateOperationName_(binding.operation_name), binding.resource_key || '');
  if (operation.done !== true) {
    return {
      ready: false,
      download_ticket: ticket,
      file_id: fileId,
      total_bytes: Number(binding.size),
      sha256: String(binding.sha256),
      mime_type: String(binding.mime_type || ''),
      modified_time: String(binding.modified_time || '')
    };
  }
  cache.remove(downloadTicketKey_(ticket));
  return completedDownloadResult_(operation, meta, fileId, ticket);
}

function validateLargeDownloadMeta_(meta) {
  if (meta.trashed) throw bridgeError_('FILE_TRASHED', 'cannot download a trashed file', false);
  if (String(meta.mimeType || '').indexOf(GOOGLE_APPS_PREFIX) === 0) {
    throw bridgeError_('BLOB_DOWNLOAD_ONLY', 'large direct download v1 requires a blob file, not a Google Workspace document', false);
  }
  if (meta.capabilities && meta.capabilities.canDownload === false) {
    throw bridgeError_('DOWNLOAD_FORBIDDEN', 'Drive reports canDownload=false', false);
  }
  if (meta.size == null || !Number.isFinite(Number(meta.size)) || Number(meta.size) < 0) {
    throw bridgeError_('SIZE_UNAVAILABLE', 'Drive file size is unavailable', false);
  }
  if (!/^[0-9a-f]{64}$/i.test(String(meta.sha256Checksum || ''))) {
    throw bridgeError_('SHA256_UNAVAILABLE', 'Drive SHA256 is required for verified large download', false);
  }
}

function startDriveDownloadOperation_(fileId, resourceKey) {
  const headers = {
    Authorization: 'Bearer ' + ScriptApp.getOAuthToken(),
    Accept: 'application/json'
  };
  if (resourceKey) headers['X-Goog-Drive-Resource-Keys'] = fileId + '/' + resourceKey;
  const response = UrlFetchApp.fetch('https://www.googleapis.com/drive/v3/files/' + encodeURIComponent(fileId) + '/download', {
    method: 'post',
    headers: headers,
    payload: '',
    muteHttpExceptions: true,
    followRedirects: false
  });
  const code = response.getResponseCode();
  if (code < 200 || code >= 300) {
    throw bridgeError_('LARGE_DOWNLOAD_START_FAILED', 'Drive files.download failed with HTTP ' + code, retryableHttp_(code));
  }
  try { return JSON.parse(response.getContentText() || '{}'); }
  catch (err) { throw bridgeError_('LARGE_DOWNLOAD_START_FAILED', 'Drive files.download returned invalid JSON', true); }
}

function pollDriveDownloadOperation_(operationName, resourceKey) {
  const headers = {
    Authorization: 'Bearer ' + ScriptApp.getOAuthToken(),
    Accept: 'application/json'
  };
  if (resourceKey) headers['X-Goog-Drive-Resource-Keys'] = resourceKey;
  const response = UrlFetchApp.fetch('https://www.googleapis.com/drive/v3/' + operationName, {
    method: 'get',
    headers: headers,
    muteHttpExceptions: true,
    followRedirects: false
  });
  const code = response.getResponseCode();
  if (code < 200 || code >= 300) {
    throw bridgeError_('LARGE_DOWNLOAD_POLL_FAILED', 'Drive operations.get failed with HTTP ' + code, retryableHttp_(code));
  }
  try { return JSON.parse(response.getContentText() || '{}'); }
  catch (err) { throw bridgeError_('LARGE_DOWNLOAD_POLL_FAILED', 'Drive operations.get returned invalid JSON', true); }
}

function completedDownloadResult_(operation, meta, fileId, ticket) {
  if (operation.error) {
    const errorCode = Number(operation.error.code || 0);
    throw bridgeError_('LARGE_DOWNLOAD_OPERATION_FAILED', String(operation.error.message || 'Drive download operation failed'), retryableDriveOperationCode_(errorCode));
  }
  const response = operation.response && typeof operation.response === 'object' ? operation.response : {};
  const downloadUri = String(response.downloadUri || '').trim();
  if (!downloadUri || downloadUri.indexOf('https://') !== 0) {
    throw bridgeError_('LARGE_DOWNLOAD_URI_MISSING', 'completed Drive download operation returned no HTTPS downloadUri', true);
  }
  return {
    ready: true,
    download_ticket: ticket || null,
    file_id: fileId,
    total_bytes: Number(meta.size),
    sha256: String(meta.sha256Checksum || '').toLowerCase(),
    mime_type: String(meta.mimeType || ''),
    modified_time: String(meta.modifiedTime || ''),
    resource_key: String(meta.resourceKey || ''),
    partial_download_allowed: Boolean(response.partialDownloadAllowed),
    download_uri: downloadUri
  };
}

function validateOperationName_(value) {
  const name = String(value || '').trim();
  if (!/^operations\/[A-Za-z0-9._~%\/-]+$/.test(name)) throw bridgeError_('INVALID_DOWNLOAD_OPERATION', 'Drive operation name is invalid', false);
  return name;
}

function downloadTicketKey_(ticket) { return 'bridge-download:' + String(ticket); }
function retryableHttp_(code) { return [408,425,429,500,502,503,504].indexOf(Number(code)) >= 0; }
function retryableDriveOperationCode_(code) { return [1,2,4,8,10,13,14].indexOf(Number(code)) >= 0; }

function sheetEnsure_(p, idem, cfg) {
  requireSheets_(cfg);
  const existingId = String(p.spreadsheet_id || '').trim();
  if (existingId) {
    assertFileInsideRoot_(existingId, cfg);
    const m = metadata_(existingId, cfg);
    if (m.mime_type !== SHEET_MIME) throw bridgeError_('NOT_SPREADSHEET', 'file is not a Google spreadsheet', false);
    return {spreadsheet: m, created: false};
  }
  const path = normalizePath_(p.path || '');
  const filename = validateFilename_(p.filename);
  const folder = resolveFolder_(path, true, cfg);
  const found = findSingleByName_(folder, filename);
  if (found) {
    const m = metadata_(found.getId(), cfg);
    if (m.mime_type !== SHEET_MIME) throw bridgeError_('NAME_CONFLICT', 'existing object is not a spreadsheet', false);
    return {spreadsheet: m, created: false};
  }
  const ss = SpreadsheetApp.create(filename);
  const file = DriveApp.getFileById(ss.getId());
  file.moveTo(folder);
  assertFileInsideRoot_(file.getId(), cfg);
  return {spreadsheet: metadata_(file.getId(), cfg), created: true};
}

function sheetStageBegin_(p, idem, cfg) {
  requireSheets_(cfg);
  const spreadsheetId = cleanId_(p.spreadsheet_id, 'spreadsheet_id');
  assertFileInsideRoot_(spreadsheetId, cfg);
  const targetTitle = validateSheetTitle_(p.sheet_title);
  const ss = SpreadsheetApp.openById(spreadsheetId);
  const stageTitle = stageSheetTitle_(idem);
  let stage = ss.getSheetByName(stageTitle);
  if (!stage) stage = ss.insertSheet(stageTitle);
  stage.clear({contentsOnly: false});
  stage.setFrozenRows(0);
  return {spreadsheet_id: spreadsheetId, target_sheet_title: targetTitle, stage_sheet_title: stageTitle, stage_sheet_id: stage.getSheetId()};
}

function sheetWriteChunk_(p, idem, cfg) {
  requireSheets_(cfg);
  const spreadsheetId = cleanId_(p.spreadsheet_id, 'spreadsheet_id');
  assertFileInsideRoot_(spreadsheetId, cfg);
  const stageTitle = validateSheetTitle_(p.stage_sheet_title);
  const startRow = positiveInt_(p.start_row, 'start_row');
  const startCol = positiveInt_(p.start_col || 1, 'start_col');
  const values = p.values;
  if (!Array.isArray(values) || values.length === 0 || !Array.isArray(values[0])) throw bridgeError_('INVALID_VALUES', 'values must be a non-empty 2D array', false);
  const width = values[0].length;
  if (width < 1 || values.some(function(r){ return !Array.isArray(r) || r.length !== width; })) throw bridgeError_('INVALID_VALUES', 'all rows must have equal width', false);
  const expected = String(p.chunk_sha256 || '').toLowerCase();
  const actual = sha256HexString_(JSON.stringify(values));
  if (expected && expected !== actual) throw bridgeError_('SHA256_MISMATCH', 'chunk digest mismatch', false);
  const ss = SpreadsheetApp.openById(spreadsheetId);
  const stage = ss.getSheetByName(stageTitle);
  if (!stage) throw bridgeError_('STAGE_NOT_FOUND', 'stage sheet not found', false);
  ensureSheetSize_(stage, startRow + values.length - 1, startCol + width - 1);
  stage.getRange(startRow, startCol, values.length, width).setValues(values);
  SpreadsheetApp.flush();
  return {written_rows: values.length, written_columns: width, start_row: startRow, start_col: startCol, chunk_sha256: actual};
}

function sheetVerify_(p, cfg) {
  requireSheets_(cfg);
  const spreadsheetId = cleanId_(p.spreadsheet_id, 'spreadsheet_id');
  assertFileInsideRoot_(spreadsheetId, cfg);
  const stageTitle = validateSheetTitle_(p.stage_sheet_title);
  const ss = SpreadsheetApp.openById(spreadsheetId);
  const stage = ss.getSheetByName(stageTitle);
  if (!stage) throw bridgeError_('STAGE_NOT_FOUND', 'stage sheet not found', false);
  const lastRow = stage.getLastRow();
  const lastCol = stage.getLastColumn();
  const digest = sheetDigestV1_(stage, lastRow, lastCol);
  const dateCol = Number(p.date_column || 0);
  let firstDate = null;
  let lastDate = null;
  if (dateCol > 0 && lastRow > 0 && lastCol >= dateCol) {
    const vals = stage.getRange(1, dateCol, lastRow, 1).getDisplayValues().map(function(r){return r[0];});
    const nonEmpty = vals.filter(function(v){return String(v).trim() !== '';});
    if (nonEmpty.length) { firstDate = nonEmpty[0]; lastDate = nonEmpty[nonEmpty.length - 1]; }
  }
  return {spreadsheet_id: spreadsheetId, stage_sheet_title: stageTitle, row_count: lastRow, column_count: lastCol, digest_algorithm: 'sheet_digest_v1', digest: digest, first_date: firstDate, last_date: lastDate};
}

function sheetCommit_(p, idem, cfg) {
  requireSheets_(cfg);
  const spreadsheetId = cleanId_(p.spreadsheet_id, 'spreadsheet_id');
  assertFileInsideRoot_(spreadsheetId, cfg);
  const targetTitle = validateSheetTitle_(p.target_sheet_title);
  const stageTitle = validateSheetTitle_(p.stage_sheet_title);
  const expectedDigest = String(p.expected_digest || '').toLowerCase();
  const ss = SpreadsheetApp.openById(spreadsheetId);
  let stage = ss.getSheetByName(stageTitle);
  const target = ss.getSheetByName(targetTitle);

  if (!stage && target) {
    if (expectedDigest) {
      const td = sheetDigestV1_(target, target.getLastRow(), target.getLastColumn());
      if (td !== expectedDigest) throw bridgeError_('IDEMPOTENCY_CONFLICT', 'target exists but digest differs on replay', false);
    }
    return {committed: true, replayed: true, spreadsheet_id: spreadsheetId, target_sheet_title: targetTitle};
  }
  if (!stage) throw bridgeError_('STAGE_NOT_FOUND', 'stage sheet not found', false);
  if (expectedDigest) {
    const sd = sheetDigestV1_(stage, stage.getLastRow(), stage.getLastColumn());
    if (sd !== expectedDigest) throw bridgeError_('VERIFY_REQUIRED', 'stage digest does not match expected digest', false);
  }

  const backupTitle = backupSheetTitle_(idem);
  let backup = ss.getSheetByName(backupTitle);
  if (backup) ss.deleteSheet(backup);
  try {
    if (target) target.setName(backupTitle);
    stage.setName(targetTitle);
    SpreadsheetApp.flush();
    backup = ss.getSheetByName(backupTitle);
    if (backup) ss.deleteSheet(backup);
    return {committed: true, replayed: false, spreadsheet_id: spreadsheetId, target_sheet_title: targetTitle, target_sheet_id: stage.getSheetId()};
  } catch (err) {
    try {
      const newTarget = ss.getSheetByName(targetTitle);
      const oldBackup = ss.getSheetByName(backupTitle);
      if (newTarget && newTarget.getSheetId() === stage.getSheetId()) newTarget.setName(stageTitle);
      if (oldBackup) oldBackup.setName(targetTitle);
      SpreadsheetApp.flush();
    } catch (rollbackErr) {}
    throw bridgeError_('SHEET_COMMIT_FAILED', 'sheet commit failed; rollback attempted', true);
  }
}

function sheetAbort_(p, idem, cfg) {
  requireSheets_(cfg);
  const spreadsheetId = cleanId_(p.spreadsheet_id, 'spreadsheet_id');
  assertFileInsideRoot_(spreadsheetId, cfg);
  const stageTitle = validateSheetTitle_(p.stage_sheet_title);
  const ss = SpreadsheetApp.openById(spreadsheetId);
  const stage = ss.getSheetByName(stageTitle);
  if (stage && ss.getSheets().length > 1) ss.deleteSheet(stage);
  return {aborted: true, spreadsheet_id: spreadsheetId, stage_sheet_title: stageTitle};
}

function resolveFolder_(path, createMissing, cfg) {
  let folder = DriveApp.getFolderById(cfg.rootId);
  const normalized = normalizePath_(path);
  if (!normalized) return folder;
  const parts = normalized.split('/');
  for (let i = 0; i < parts.length; i++) {
    if (!folder) return null;
    const name = parts[i];
    const it = folder.getFoldersByName(name);
    if (it.hasNext()) folder = it.next();
    else if (createMissing) folder = folder.createFolder(name);
    else return null;
  }
  return folder;
}

function normalizePath_(path) {
  const parts = String(path || '').split('/').map(function(x){return x.trim();}).filter(Boolean);
  parts.forEach(function(x){ if (x === '.' || x === '..' || x.indexOf('\\') >= 0) throw bridgeError_('INVALID_PATH', 'invalid path segment', false); });
  return parts.join('/');
}

function validateFilename_(name) {
  const f = String(name || '').trim();
  if (!f || f.indexOf('/') >= 0 || f.indexOf('\\') >= 0) throw bridgeError_('INVALID_FILENAME', 'invalid filename', false);
  return f;
}

function validateSheetTitle_(name) {
  const v = String(name || '').trim();
  if (!v || v.length > 90 || /[\[\]\*\?\/\\:]/.test(v)) throw bridgeError_('INVALID_SHEET_TITLE', 'invalid sheet title', false);
  return v;
}

function assertFileInsideRoot_(fileId, cfg) {
  let current = cleanId_(fileId, 'file_id');
  const seen = {};
  for (let depth = 0; depth < 128; depth++) {
    if (current === cfg.rootId) return true;
    if (seen[current]) throw bridgeError_('ANCESTRY_CYCLE', 'Drive ancestry cycle detected', false);
    seen[current] = true;
    const m = rawMetadata_(current);
    if (m.mimeType === SHORTCUT_MIME) throw bridgeError_('SHORTCUT_FORBIDDEN', 'Drive shortcuts are not allowed by bridge v1', false);
    const parents = m.parents || [];
    if (parents.length !== 1) throw bridgeError_('OUTSIDE_ROOT', 'file is not provably inside fixed root', false);
    current = String(parents[0]);
  }
  throw bridgeError_('OUTSIDE_ROOT', 'Drive ancestry exceeded safety depth', false);
}

function rawMetadata_(fileId) {
  try {
    return Drive.Files.get(fileId, {fields: 'id,name,mimeType,parents,size,modifiedTime,sha256Checksum,md5Checksum,trashed,shortcutDetails,resourceKey,capabilities(canDownload)'});
  } catch (err) {
    throw bridgeError_('FILE_LOOKUP_FAILED', 'Drive file metadata lookup failed', false);
  }
}

function metadata_(fileId, cfg) {
  assertFileInsideRoot_(fileId, cfg);
  const m = rawMetadata_(fileId);
  return {
    id: String(m.id || fileId),
    name: String(m.name || ''),
    mime_type: String(m.mimeType || ''),
    size: m.size != null ? Number(m.size) : null,
    modified_time: m.modifiedTime || null,
    sha256_checksum: m.sha256Checksum || null,
    md5_checksum: m.md5Checksum || null,
    parents: m.parents || [],
    trashed: Boolean(m.trashed)
  };
}

function findSingleByName_(folder, name) {
  const it = folder.getFilesByName(name);
  return it.hasNext() ? it.next() : null;
}

function requireSheets_(cfg) {
  if (!cfg.sheetsEnabled) throw bridgeError_('CAPABILITY_DISABLED', 'Google Sheets extension is disabled for this deployment', false);
}

function ensureSheetSize_(sheet, rows, cols) {
  if (sheet.getMaxRows() < rows) sheet.insertRowsAfter(sheet.getMaxRows(), rows - sheet.getMaxRows());
  if (sheet.getMaxColumns() < cols) sheet.insertColumnsAfter(sheet.getMaxColumns(), cols - sheet.getMaxColumns());
}

function sheetDigestV1_(sheet, rows, cols) {
  if (!rows || !cols) return sha256HexString_('');
  const chunkHashes = [];
  const block = 1000;
  for (let r = 1; r <= rows; r += block) {
    const count = Math.min(block, rows - r + 1);
    const values = sheet.getRange(r, 1, count, cols).getDisplayValues();
    chunkHashes.push(sha256HexString_(JSON.stringify(values)));
  }
  return sha256HexString_(chunkHashes.join('\n'));
}

function stageSheetTitle_(idem) { return '__bridge_stage_' + shortHash_(idem).slice(0, 16); }
function backupSheetTitle_(idem) { return '__bridge_backup_' + shortHash_(idem).slice(0, 16); }
function shortHash_(value) { return sha256HexString_(String(value)).slice(0, 24); }

function positiveInt_(value, name) {
  const n = Number(value);
  if (!Number.isInteger(n) || n < 1) throw bridgeError_('INVALID_ARGUMENT', name + ' must be a positive integer', false);
  return n;
}

function cleanId_(value, name) {
  const v = String(value || '').trim();
  if (!v || v.length > 512) throw bridgeError_('INVALID_ARGUMENT', name + ' is required', false);
  return v;
}

function isMutation_(action) {
  return ['write_small','trash_by_id','resumable_start','promote_verified','sheet_ensure','sheet_stage_begin','sheet_write_chunk','sheet_commit','sheet_abort'].indexOf(action) >= 0;
}

function sha256HexString_(s) {
  return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, String(s), Utilities.Charset.UTF_8)
    .map(function(b){return (b < 0 ? b + 256 : b).toString(16).padStart(2, '0');}).join('');
}

function sha256HexBytes_(bytes) {
  return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, bytes)
    .map(function(b){return (b < 0 ? b + 256 : b).toString(16).padStart(2, '0');}).join('');
}

function bridgeError_(code, message, retryable) {
  const e = new Error(message);
  e.bridgeCode = code;
  e.bridgeRetryable = Boolean(retryable);
  return e;
}

function errorInfo_(err) {
  return {
    code: String(err && err.bridgeCode || 'INTERNAL_ERROR'),
    message: String(err && err.message || 'internal error').slice(0, 500),
    retryable: Boolean(err && err.bridgeRetryable)
  };
}

function envelopeOk_(cfg, requestId, action, result) {
  return json_({
    ok: true,
    protocol_version: BRIDGE_PROTOCOL_VERSION,
    bridge_release: BRIDGE_RELEASE,
    project_id: cfg.projectId,
    request_id: requestId,
    action: action,
    result: result || {}
  });
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}