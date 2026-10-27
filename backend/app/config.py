from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    database_url: str = "sqlite:///./b2toc1.sqlite3"
    jwt_secret: str = Field(min_length=32)
    jwt_expire_minutes: int = Field(default=1440, gt=0)
    ollama_base_url: str = Field(default="http://host.docker.internal:11434", min_length=8)
    ollama_model: str = Field(default="qwen3.8", min_length=1)
    ollama_timeout_seconds: float = Field(default=300, gt=0, le=1800)
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    @property
    def origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

