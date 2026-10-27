from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    database_url: str = "sqlite:///./b2toc1.sqlite3"
    jwt_secret: str = Field(min_length=32)
    jwt_expire_minutes: int = Field(default=1440, gt=0)
    openai_api_key: str = ""
    openai_model: str = Field(default="gpt-4o-mini", min_length=1)
    openai_timeout_seconds: float = Field(default=300, gt=0, le=1800)
    demo_seed_enabled: bool = False
    demo_username: str = Field(default="demo", min_length=3, max_length=50)
    demo_email: str = Field(default="demo@example.com", min_length=5, max_length=255)
    demo_name: str = Field(default="Usuario Demo", min_length=2, max_length=100)
    demo_password: str = Field(default="LevelUpDemo2026!", min_length=8, max_length=128)
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    @property
    def origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

