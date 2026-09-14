from pathlib import Path

root = Path('shared/google-drive-bridge')
bridge = root / 'bridge.gs'
s = bridge.read_text(encoding='utf-8')

old = "  if (action === 'sheet_verify') return sheetVerify_(p, cfg);\n  if (action === 'sheet_commit') return sheetCommit_(p, idem, cfg);"
new = "  if (action === 'sheet_verify') return sheetVerify_(p, cfg);\n  if (action === 'sheet_inspect') return sheetInspect_(p, cfg);\n  if (action === 'sheet_commit') return sheetCommit_(p, idem, cfg);"
if new not in s:
    if old not in s:
        raise SystemExit('dispatch insertion point not found')
    s = s.replace(old, new, 1)

old_verify_tail = """  return {spreadsheet_id: spreadsheetId, stage_sheet_title: stageTitle, row_count: lastRow, column_count: lastCol, digest_algorithm: 'sheet_digest_v1', digest: digest, first_date: firstDate, last_date: lastDate};
}

function sheetCommit_(p, idem, cfg) {
"""
new_verify_tail = """  return {spreadsheet_id: spreadsheetId, stage_sheet_title: stageTitle, row_count: lastRow, column_count: lastCol, digest_algorithm: 'sheet_digest_v1', digest: digest, first_date: firstDate, last_date: lastDate};
}

function sheetInspect_(p, cfg) {
  requireSheets_(cfg);
  const spreadsheetId = cleanId_(p.spreadsheet_id, 'spreadsheet_id');
  assertFileInsideRoot_(spreadsheetId, cfg);
  const sheetTitle = validateSheetTitle_(p.sheet_title);
  const ss = SpreadsheetApp.openById(spreadsheetId);
  const sheet = ss.getSheetByName(sheetTitle);
  if (!sheet) return {found: false, spreadsheet_id: spreadsheetId, sheet_title: sheetTitle};
  const lastRow = sheet.getLastRow();
  const lastCol = sheet.getLastColumn();
  const digest = sheetDigestV1_(sheet, lastRow, lastCol);
  const dateCol = Number(p.date_column || 0);
  let firstDate = null;
  let lastDate = null;
  if (dateCol > 0 && lastRow > 0 && lastCol >= dateCol) {
    const vals = sheet.getRange(1, dateCol, lastRow, 1).getDisplayValues().map(function(r){return r[0];});
    const nonEmpty = vals.filter(function(v){return String(v).trim() !== '';});
    if (nonEmpty.length) { firstDate = nonEmpty[0]; lastDate = nonEmpty[nonEmpty.length - 1]; }
  }
  return {
    found: true,
    spreadsheet_id: spreadsheetId,
    sheet_title: sheetTitle,
    sheet_id: sheet.getSheetId(),
    row_count: lastRow,
    column_count: lastCol,
    digest_algorithm: 'sheet_digest_v1',
    digest: digest,
    first_date: firstDate,
    last_date: lastDate
  };
}

function sheetCommit_(p, idem, cfg) {
"""
if 'function sheetInspect_' not in s:
    if old_verify_tail not in s:
        raise SystemExit('sheet inspect insertion point not found')
    s = s.replace(old_verify_tail, new_verify_tail, 1)

s = s.replace(
    "google_sheets_chunked: cfg.sheetsEnabled,",
    "google_sheets_chunked: cfg.sheetsEnabled,\n      google_sheets_inspect: cfg.sheetsEnabled,",
    1,
)
bridge.write_text(s, encoding='utf-8')

client = root / 'python_client/bridge_client.py'
c = client.read_text(encoding='utf-8')
marker = """    async def sheet_commit(
        self,
        *,
        spreadsheet_id: str,
        stage_sheet_title: str,
        target_sheet_title: str,
        expected_digest: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
"""
method = """    async def sheet_inspect(
        self,
        *,
        spreadsheet_id: str,
        sheet_title: str,
        date_column: int = 0,
    ) -> dict[str, Any]:
        return await self.call(
            "sheet_inspect",
            {"spreadsheet_id": spreadsheet_id, "sheet_title": sheet_title, "date_column": int(date_column)},
        )

"""
if 'async def sheet_inspect(' not in c:
    if marker not in c:
        raise SystemExit('python client insertion point not found')
    c = c.replace(marker, method + marker, 1)
client.write_text(c, encoding='utf-8')

protocol = root / 'PROTOCOL.md'
p = protocol.read_text(encoding='utf-8')
anchor = """### `sheet_verify`
Returns parity metadata such as row count, digest, first/last date and caller-requested verification fields.

### `sheet_commit`
"""
replacement = """### `sheet_verify`
Returns parity metadata for a staged sheet: row count, digest, first/last date and caller-requested verification fields.

### `sheet_inspect`
Read-only post-commit inspection of a canonical sheet. Payload: `spreadsheet_id`, `sheet_title`, optional 1-based `date_column`. Returns `found`, row/column count, `sheet_digest_v1`, and optional first/last date. Clients use this after commit for independent read-back parity.

### `sheet_commit`
"""
if '### `sheet_inspect`' not in p:
    if anchor not in p:
        raise SystemExit('protocol insertion point not found')
    p = p.replace(anchor, replacement, 1)
protocol.write_text(p, encoding='utf-8')

acceptance = root / 'scripts/sheets_acceptance.py'
a = acceptance.read_text(encoding='utf-8')
old_first_write = """    await client.sheet_write_chunk(
        spreadsheet_id=spreadsheet_id,
        stage_sheet_title=stage_title,
        start_row=1,
        start_col=1,
        values=rows1,
        idempotency_key=f"sheets-acceptance-chunk1:{project}:{spreadsheet_id}",
    )
    await client.sheet_write_chunk(
"""
new_first_write = """    await client.sheet_write_chunk(
        spreadsheet_id=spreadsheet_id,
        stage_sheet_title=stage_title,
        start_row=1,
        start_col=1,
        values=rows1,
        idempotency_key=f"sheets-acceptance-chunk1:{project}:{spreadsheet_id}",
    )

    # Replaying stage-begin with the same idempotency key must preserve rows already written.
    replayed_stage = await client.sheet_stage_begin(
        spreadsheet_id=spreadsheet_id,
        sheet_title=target_title,
        idempotency_key=stage_key,
    )
    if replayed_stage.get("replayed") is not True or str(replayed_stage.get("stage_sheet_title") or "") != stage_title:
        raise RuntimeError(f"stage-begin replay contract failed: {replayed_stage}")
    preserved = await client.sheet_verify(
        spreadsheet_id=spreadsheet_id,
        stage_sheet_title=stage_title,
        date_column=2,
    )
    if int(preserved.get("row_count") or -1) != 3:
        raise RuntimeError(f"stage replay destroyed staged rows: {preserved}")

    await client.sheet_write_chunk(
"""
if 'stage replay destroyed staged rows' not in a:
    if old_first_write not in a:
        raise SystemExit('acceptance stage replay insertion point not found')
    a = a.replace(old_first_write, new_first_write, 1)

commit_anchor = """    if first_commit.get("committed") is not True:
        raise RuntimeError("first sheet commit failed")

    replay = await client.sheet_commit(
"""
commit_replacement = """    if first_commit.get("committed") is not True:
        raise RuntimeError("first sheet commit failed")

    inspected = await client.sheet_inspect(
        spreadsheet_id=spreadsheet_id,
        sheet_title=target_title,
        date_column=2,
    )
    if inspected.get("found") is not True:
        raise RuntimeError(f"post-commit target is missing: {inspected}")
    if int(inspected.get("row_count") or -1) != 5 or str(inspected.get("digest") or "") != digest:
        raise RuntimeError(f"post-commit read-back parity failed: {inspected}")
    if str(inspected.get("first_date") or "") != "date" or str(inspected.get("last_date") or "") != "2026-09-16":
        raise RuntimeError(f"post-commit date parity failed: {inspected}")

    replay = await client.sheet_commit(
"""
if 'post-commit read-back parity failed' not in a:
    if commit_anchor not in a:
        raise SystemExit('acceptance inspect insertion point not found')
    a = a.replace(commit_anchor, commit_replacement, 1)

trash_anchor = """    await client.trash_by_id(
        spreadsheet_id,
        idempotency_key=f"sheets-acceptance-trash:{project}:{spreadsheet_id}",
    )
    print("SHEETS_STAGE_WRITE_VERIFY_COMMIT_REPLAY=PASS")
"""
trash_replacement = """    abort_key = f"sheets-acceptance-abort-stage:{project}:{spreadsheet_id}"
    abort_stage = await client.sheet_stage_begin(
        spreadsheet_id=spreadsheet_id,
        sheet_title="ABORT_TEST",
        idempotency_key=abort_key,
    )
    abort_title = str(abort_stage.get("stage_sheet_title") or "")
    aborted = await client.sheet_abort(
        spreadsheet_id=spreadsheet_id,
        stage_sheet_title=abort_title,
        idempotency_key=f"sheets-acceptance-abort:{project}:{spreadsheet_id}",
    )
    if aborted.get("aborted") is not True:
        raise RuntimeError(f"sheet abort failed: {aborted}")

    await client.trash_by_id(
        spreadsheet_id,
        idempotency_key=f"sheets-acceptance-trash:{project}:{spreadsheet_id}",
    )
    print("SHEETS_STAGE_REPLAY_WRITE_VERIFY_COMMIT_INSPECT_REPLAY_ABORT=PASS")
"""
if 'SHEETS_STAGE_REPLAY_WRITE_VERIFY_COMMIT_INSPECT_REPLAY_ABORT=PASS' not in a:
    if trash_anchor not in a:
        raise SystemExit('acceptance abort insertion point not found')
    a = a.replace(trash_anchor, trash_replacement, 1)
acceptance.write_text(a, encoding='utf-8')

status = root / 'STATUS.md'
st = status.read_text(encoding='utf-8')
st = st.replace('- Google Sheets ensure/stage/chunk/verify/commit/abort;', '- Google Sheets ensure/stage/chunk/verify/commit/inspect/abort;')
st = st.replace('- non-destructive replay of `sheet_stage_begin`;', '- non-destructive replay of `sheet_stage_begin`;\n- independent post-commit canonical-sheet read-back via `sheet_inspect`;')
status.write_text(st, encoding='utf-8')

test = root / 'tests/test_protocol_contract.py'
t = test.read_text(encoding='utf-8')
extra = """

def test_final_sheets_contract_has_post_commit_inspection() -> None:
    root = Path(__file__).resolve().parents[1]
    bridge = (root / 'bridge.gs').read_text(encoding='utf-8')
    client = (root / 'python_client' / 'bridge_client.py').read_text(encoding='utf-8')
    protocol = (root / 'PROTOCOL.md').read_text(encoding='utf-8')
    assert "action === 'sheet_inspect'" in bridge
    assert 'function sheetInspect_' in bridge
    assert 'google_sheets_inspect' in bridge
    assert 'async def sheet_inspect(' in client
    assert '### `sheet_inspect`' in protocol
"""
if 'test_final_sheets_contract_has_post_commit_inspection' not in t:
    t += extra
    test.write_text(t, encoding='utf-8')

print('BRIDGE_V1_SHEET_INSPECT_PATCH=PASS')
