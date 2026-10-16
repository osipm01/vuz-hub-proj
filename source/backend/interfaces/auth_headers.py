from typing import Final

AUTH_HEADER: Final[str] = "x-auth-type"
BOT_HEADER: Final[str] = "x-bot-token"
INTEGRATION_HEADER: Final[str] = "x-integration-key"
CLIENT_HEADER: Final[str] = "x-auth-token"

WWW_AUTHENTICATE_BEARER: Final[dict[str, str]] = {"WWW-Authenticate": "Bearer"}
