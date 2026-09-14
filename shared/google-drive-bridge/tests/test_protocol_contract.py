import hashlib

from shared.google_drive_bridge.python_client.bridge_client import _confirmed_offset


def test_confirmed_offset():
    assert _confirmed_offset("bytes=0-0") == 1
    assert _confirmed_offset("bytes=0-1048575") == 1048576
    assert _confirmed_offset("") is None
    assert _confirmed_offset("bytes=10-20") is None


def test_sha256_fixture():
    assert hashlib.sha256(b"bridge-v1").hexdigest() == "640d275d9cc66e1cb45d0fb1f16af16fcbe8ed67320b5830566dd42c5bdcd8c0"
