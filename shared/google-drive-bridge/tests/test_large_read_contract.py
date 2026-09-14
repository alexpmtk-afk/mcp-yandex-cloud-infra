import importlib.util
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[1] / "python_client" / "bridge_client.py"
spec = importlib.util.spec_from_file_location("bridge_client_large_read", MODULE)
assert spec and spec.loader
bridge_client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge_client)


def test_sha256_validator():
    assert bridge_client._is_sha256("a" * 64)
    assert bridge_client._is_sha256("0123456789abcdef" * 4)
    assert not bridge_client._is_sha256("a" * 63)
    assert not bridge_client._is_sha256("z" * 64)


@pytest.mark.parametrize(
    "uri",
    [
        "https://www.googleapis.com/download/drive/v3/files/x",
        "https://content.googleapis.com/download/drive/v3/files/x",
        "https://download.googleusercontent.com/download/x",
        "https://drive.usercontent.google.com/download?id=x",
    ],
)
def test_google_download_uri_allowlist(uri):
    bridge_client._validate_google_download_uri(uri)


@pytest.mark.parametrize(
    "uri",
    [
        "http://www.googleapis.com/download/x",
        "https://example.com/download/x",
        "https://googleapis.com.evil.example/download/x",
        "file:///tmp/x",
    ],
)
def test_google_download_uri_rejects_non_google_hosts(uri):
    with pytest.raises(bridge_client.BridgeError) as exc:
        bridge_client._validate_google_download_uri(uri)
    assert exc.value.code == "INVALID_DOWNLOAD_URI"
