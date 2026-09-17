from app.formatting import public_message_url


def test_public_url_only_for_public_username():
    assert public_message_url("channel_name", 42) == "https://t.me/channel_name/42"
    assert public_message_url(None, 42) is None
