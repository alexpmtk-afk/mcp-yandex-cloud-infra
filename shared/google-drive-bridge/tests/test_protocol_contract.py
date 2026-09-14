import hashlib
import importlib.util
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "python_client" / "bridge_client.py"
spec = importlib.util.spec_from_file_location("bridge_client", MODULE)
assert spec and spec.loader
bridge_client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge_client)
_confirmed_offset = bridge_client._confirmed_offset


def test_confirmed_offset():
    assert _confirmed_offset("bytes=0-0") == 1
    assert _confirmed_offset("bytes=0-1048575") == 1048576
    assert _confirmed_offset("") is None
    assert _confirmed_offset("bytes=10-20") is None


def test_sha256_fixture():
    assert hashlib.sha256(b"bridge-v1").hexdigest() == "83a3608e5baeb253b1670222090007d078fc84ef96fc6ce51e49de40986a332c"
