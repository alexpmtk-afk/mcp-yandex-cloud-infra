import hashlib
import sys
from pathlib import Path

PYTHON_CLIENT = Path(__file__).resolve().parents[1] / "python_client"
sys.path.insert(0, str(PYTHON_CLIENT))

from bridge_client import _confirmed_offset  # noqa: E402


def test_confirmed_offset():
    assert _confirmed_offset("bytes=0-0") == 1
    assert _confirmed_offset("bytes=0-1048575") == 1048576
    assert _confirmed_offset("") is None
    assert _confirmed_offset("bytes=10-20") is None


def test_sha256_fixture():
    assert hashlib.sha256(b"bridge-v1").hexdigest() == "83a3608e5baeb253b1670222090007d078fc84ef96fc6ce51e49de40986a332c"


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
