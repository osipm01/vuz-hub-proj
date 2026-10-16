from enum import Enum


class AuthType(str, Enum):
    BOT = "BOT"
    INTEGRATION = "INTEGRATION"
    CLIENT = "client"