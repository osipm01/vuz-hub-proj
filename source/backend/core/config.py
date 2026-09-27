from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


    # для проверки автоизации URL сервера автоизации
    AUTH_CHECK_URL: str = "https://localhost:3100/api/users/check-auth-by-token"
    SECRET_JWT_KEY: str = "qwert"

    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "admin"
    DB_NAME: str = "vuxhubbd"

    @property
    def DATABASE_URL(self) -> str:
        """Автоматически собирает строку подключения для asyncpg"""
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"


# Создаем объект настроек для импорта в другие файлы
settings = Settings()