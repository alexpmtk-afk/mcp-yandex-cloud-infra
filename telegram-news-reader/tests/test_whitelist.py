from pathlib import Path

import pytest

from app.errors import AccessDenied
from app.whitelist import Whitelist


def test_whitelist_allows_only_enabled(tmp_path: Path):
    path = tmp_path / "allowed.yaml"
    path.write_text(
        "allowed_chats:\n"
        "  - chat_id: -1001\n    name: One\n    enabled: true\n"
        "  - chat_id: -1002\n    name: Two\n    enabled: false\n",
        encoding="utf-8",
    )
    whitelist = Whitelist(path)
    assert whitelist.assert_allowed(-1001).name == "One"
    with pytest.raises(AccessDenied, match="ACCESS_DENIED"):
        whitelist.assert_allowed(-1002)
    with pytest.raises(AccessDenied, match="ACCESS_DENIED"):
        whitelist.assert_allowed(-9999)
