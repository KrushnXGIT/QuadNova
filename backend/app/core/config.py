"""
Central configuration loaded from environment / .env file.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent.parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: str = "development"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Model
    MODEL_PATH: str = ""
    MODEL_ENABLED: bool = False
    AI_MODEL_PATH: str = "../ai_model/models/hb_regressor_best.pt"
    AI_DEVICE: str = "cpu"

    # CORS — comma-separated string parsed below
    ALLOWED_ORIGINS: str = "http://localhost:8000,http://10.0.2.2:8000"

    # Upload limits
    MAX_UPLOAD_SIZE_MB: int = 10

    # Quality/confidence
    CONFIDENCE_THRESHOLD: float = 0.70

    # Logging
    LOG_LEVEL: str = "INFO"

    # Derived
    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def backend_root(self) -> Path:
        return Path(__file__).resolve().parents[2]

    @property
    def project_root(self) -> Path:
        return self.backend_root.parent

    @property
    def ai_model_root(self) -> Path:
        return self.project_root / "ai_model"

    @property
    def resolved_ai_model_path(self) -> Path:
        path = Path(self.AI_MODEL_PATH)
        if path.is_absolute():
            return path
        return (self.backend_root / path).resolve()


@lru_cache()
def get_settings() -> Settings:
    return Settings()
