"""应用配置 — 通过环境变量注入。"""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置。"""

    # 应用
    app_name: str = "CkyClaw"
    debug: bool = True

    # 数据库
    database_url: str = "postgresql+asyncpg://ckyclaw:ckyclaw_dev@localhost:5432/ckyclaw"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # JWT
    secret_key: str = "dev-secret-key-change-in-production"
    access_token_expire_minutes: int = 60 * 24  # 24 小时

    # OpenTelemetry
    otel_enabled: bool = False
    otel_service_name: str = "ckyclaw-backend"
    otel_exporter_endpoint: str = "http://localhost:4317"

    # OAuth 2.0
    oauth_github_client_id: str = ""
    oauth_github_client_secret: str = ""
    oauth_redirect_base_url: str = "http://localhost:3000"

    model_config = {"env_prefix": "CKYCLAW_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
