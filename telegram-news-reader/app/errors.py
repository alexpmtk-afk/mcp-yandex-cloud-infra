class TelegramReaderError(Exception):
    """Base application error."""


class AuthorizationRequired(TelegramReaderError):
    """The local Telegram session is not authorized yet."""


class AccessDenied(TelegramReaderError):
    """The requested chat is not in the read whitelist."""
