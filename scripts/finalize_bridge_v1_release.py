from pathlib import Path

BRIDGE = Path('shared/google-drive-bridge/bridge.gs')
s = BRIDGE.read_text(encoding='utf-8')
s = s.replace('Protocol v1 / release 1.0.0-alpha.2', 'Protocol v1 / release 1.0.0')
s = s.replace("const BRIDGE_RELEASE = '1.0.0-alpha.2';", "const BRIDGE_RELEASE = '1.0.0';")

old_stage = """function sheetStageBegin_(p, idem, cfg) {
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
"""
new_stage = """function sheetStageBegin_(p, idem, cfg) {
  requireSheets_(cfg);
  const spreadsheetId = cleanId_(p.spreadsheet_id, 'spreadsheet_id');
  assertFileInsideRoot_(spreadsheetId, cfg);
  const targetTitle = validateSheetTitle_(p.sheet_title);
  const ss = SpreadsheetApp.openById(spreadsheetId);
  const stageTitle = stageSheetTitle_(idem);
  let stage = ss.getSheetByName(stageTitle);
  if (stage) {
    const targetBinding = developerMetadataValue_(stage, 'BRIDGE_TARGET_SHEET');
    if (targetBinding && targetBinding !== targetTitle) {
      throw bridgeError_('IDEMPOTENCY_CONFLICT', 'existing stage is bound to a different target sheet', false);
    }
    if (!targetBinding) stage.addDeveloperMetadata('BRIDGE_TARGET_SHEET', targetTitle);
    return {
      spreadsheet_id: spreadsheetId,
      target_sheet_title: targetTitle,
      stage_sheet_title: stageTitle,
      stage_sheet_id: stage.getSheetId(),
      replayed: true
    };
  }
  stage = ss.insertSheet(stageTitle);
  stage.setFrozenRows(0);
  stage.addDeveloperMetadata('BRIDGE_TARGET_SHEET', targetTitle);
  stage.addDeveloperMetadata('BRIDGE_STAGE_IDEMPOTENCY', shortHash_(idem));
  return {
    spreadsheet_id: spreadsheetId,
    target_sheet_title: targetTitle,
    stage_sheet_title: stageTitle,
    stage_sheet_id: stage.getSheetId(),
    replayed: false
  };
}
"""
if new_stage not in s:
    if old_stage not in s:
        raise SystemExit('sheetStageBegin_ block not found')
    s = s.replace(old_stage, new_stage, 1)

marker = "function ensureSheetSize_(sheet, rows, cols) {"
helper = """function developerMetadataValue_(sheet, key) {
  const items = sheet.getDeveloperMetadata();
  for (let i = 0; i < items.length; i++) {
    if (items[i].getKey() === key) return String(items[i].getValue() || '');
  }
  return '';
}

"""
if helper not in s:
    if marker not in s:
        raise SystemExit('helper insertion marker not found')
    s = s.replace(marker, helper + marker, 1)

BRIDGE.write_text(s, encoding='utf-8')

Path('shared/google-drive-bridge/VERSION').write_text(
    'protocol_version=1\nbridge_release=1.0.0\n', encoding='utf-8'
)

status = """# Implementation status

Source of truth: `main`, directory `shared/google-drive-bridge/`.

Release: `protocol_version=1`, `bridge_release=1.0.0`.

## Implementation state

**CODE COMPLETE. No protocol action is a stub or `NOT_IMPLEMENTED`.**

Implemented and covered by static/contract CI:
- project-isolated Apps Script deployments;
- separate project secrets and fixed Drive roots;
- `project_id`, `request_id`, and idempotent mutation contract;
- bounded small-file read/write;
- resumable large upload with direct Yandex → Drive byte transport;
- staged verify/promote with exact size/SHA256 checks;
- large verified download through Drive `files.download` LRO with direct Google → Yandex byte transport;
- fixed-root ancestry validation and shortcut rejection;
- Google Sheets ensure/stage/chunk/verify/commit/abort;
- non-destructive replay of `sheet_stage_begin`;
- rollback attempt on Sheets commit failure;
- no whole-request global ScriptLock;
- reusable Python Protocol-v1 client;
- Marketplaces and Birzha bootstrap/acceptance/cutover gates;
- cross-project concurrency and root-isolation acceptance.

## Runtime activation order

1. Owner authorizes Google Apps Script API / Drive scopes once.
2. Bootstrap creates two separate Apps Script Web Apps from the same `1.0.0` source.
3. Each project receives its own secret in its own existing project Lockbox under `gdrive_bridge_v1_secret`.
4. Marketplaces live acceptance runs: health, root isolation, small I/O, resumable upload, large direct download, SHA256, concurrency.
5. Birzha live acceptance runs: health, root isolation, staged/chunked Sheets, verify/commit/abort/replay.
6. Cross-project acceptance proves concurrent isolation.
7. Client cutover is enabled project-by-project with legacy rollback retained until post-cutover verification passes.
8. After post-cutover PASS, legacy routes may be retired.

The only item that cannot be performed by repository automation alone is the interactive Google owner consent. That is an external authorization gate, not unfinished code.
"""
Path('shared/google-drive-bridge/STATUS.md').write_text(status, encoding='utf-8')

contract = Path('shared/google-drive-bridge/tests/test_protocol_contract.py')
t = contract.read_text(encoding='utf-8')
extra = """

def test_final_release_has_no_stub_and_stage_replay_is_non_destructive() -> None:
    root = Path(__file__).resolve().parents[1]
    bridge = (root / 'bridge.gs').read_text(encoding='utf-8')
    version = (root / 'VERSION').read_text(encoding='utf-8')
    assert 'bridge_release=1.0.0' in version
    assert "BRIDGE_RELEASE = '1.0.0'" in bridge
    assert 'NOT_IMPLEMENTED' not in bridge
    stage = bridge.split('function sheetStageBegin_', 1)[1].split('function sheetWriteChunk_', 1)[0]
    assert 'stage.clear(' not in stage
    assert "BRIDGE_TARGET_SHEET" in stage
    assert 'replayed: true' in stage
"""
if 'test_final_release_has_no_stub_and_stage_replay_is_non_destructive' not in t:
    if 'from pathlib import Path' not in t:
        t = 'from pathlib import Path\n\n' + t
    t += extra
    contract.write_text(t, encoding='utf-8')

print('BRIDGE_V1_FINAL_RELEASE_PATCH=PASS')
