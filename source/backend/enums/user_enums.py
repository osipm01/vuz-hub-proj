from enum import Enum


class SocialNetworkLinkType(str, Enum):
    VK = "vk"
    MAX_id = "max_id"
    TG_ID = "tg_id"


class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"
    MANAGER = "manager"   # убери/добавь по необходимости