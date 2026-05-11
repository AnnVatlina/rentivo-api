from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    APP_ENV: str = "development"


def _make_settings() -> Settings:
    s = Settings()
    # Railway provides postgresql:// — normalize to asyncpg driver
    if s.DATABASE_URL.startswith("postgresql://"):
        object.__setattr__(s, "DATABASE_URL", s.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1))
    return s

settings = _make_settings()
