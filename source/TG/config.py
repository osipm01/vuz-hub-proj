import os
from dataclasses import dataclass


@dataclass(frozen=True)
class BotConfig:
    api_base_url: str
    api_timeout: float
    bot_token: str

    @classmethod
    def from_env(cls) -> "BotConfig":
        return cls(
            api_base_url=os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api").rstrip("/"),
            api_timeout=float(os.getenv("API_TIMEOUT", "10")),
            bot_token=os.getenv("TOKEN", ""),
        )


config = BotConfig.from_env()