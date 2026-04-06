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
    db_pool_size: int = 5
    db_max_overflow: int = 10

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

    # OAuth 2.0 — GitHub
    oauth_github_client_id: str = ""
    oauth_github_client_secret: str = ""
    oauth_redirect_base_url: str = "http://localhost:3000"

    # OAuth 2.0 — 企微 (WeCom)
    oauth_wecom_corp_id: str = ""
    oauth_wecom_agent_id: str = ""
    oauth_wecom_secret: str = ""

    # OAuth 2.0 — 钉钉 (DingTalk)
    oauth_dingtalk_client_id: str = ""
    oauth_dingtalk_client_secret: str = ""

    # OAuth 2.0 — 飞书 (Feishu)
    oauth_feishu_app_id: str = ""
    oauth_feishu_app_secret: str = ""

    # OAuth 2.0 — OIDC (Keycloak / Casdoor / 通用 OIDC Provider)
    oauth_oidc_issuer: str = ""
    oauth_oidc_client_id: str = ""
    oauth_oidc_client_secret: str = ""
    oauth_oidc_scope: str = "openid profile email"

    # OAuth 2.0 — Google
    oauth_google_client_id: str = ""
    oauth_google_client_secret: str = ""
    oauth_google_scope: str = "openid profile email"

    model_config = {"env_prefix": "CKYCLAW_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
