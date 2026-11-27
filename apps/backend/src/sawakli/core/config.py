"""Application configuration."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _repo_env_file() -> Path | None:
    for parent in Path(__file__).resolve().parents:
        if (parent / "docker-compose.yml").is_file():
            env_path = parent / ".env"
            return env_path if env_path.is_file() else None
    return None


_ENV_FILE = _repo_env_file()


class Settings(BaseSettings):
    jwt_secret: str = "change-this-to-a-real-secret"
    jwt_expire_minutes: int = 30
    sync_check_every_seconds: int = 60
    sync_refresh_every_seconds: int = 3600

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE if _ENV_FILE is not None else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
