import os
from dataclasses import dataclass
from dotenv import load_dotenv

# 1. Явно загружаем переменные из файла .env
load_dotenv()

from dotenv import load_dotenv

# Загружаем .env из папки, где лежит config.py (надёжнее, чем cwd)
load_dotenv()


@dataclass(frozen=True)
class BotConfig:
    api_base_url: str
    api_timeout: float
    bot_token: str

    @classmethod
    def from_env(cls) -> "BotConfig":
        api_base_url = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api").rstrip("/")
        api_timeout = float(os.getenv("API_TIMEOUT", "10"))
        bot_token = os.getenv("TOKEN", "")

        # 2. Добавляем строгую проверку: если токена нет или он без двоеточия, падаем сразу с понятной ошибкой
        if not bot_token or ":" not in bot_token:
            raise ValueError(
                "❌ Ошибка конфигурации: Переменная окружения 'TOKEN' не найдена или некорректна.\n"
                "Проверьте файл .env. Токен должен выглядеть как '123456:ABCDEF...' и переменная должна называться именно TOKEN."
            )

        return cls(
<<<<<<< Updated upstream
            api_base_url=os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api").rstrip("/"),
            api_timeout=float(os.getenv("API_TIMEOUT", "10")),
            bot_token=os.getenv("BOT_TOKEN", ""),
=======
            api_base_url=api_base_url,
            api_timeout=api_timeout,
            bot_token=bot_token
>>>>>>> Stashed changes
        )


config = BotConfig.from_env()
