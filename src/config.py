"""Project configuration from environment variables."""

import os
from pydantic_settings import BaseSettings
from pydantic import Field


class RedisSettings(BaseSettings):
    """Redis configuration."""
    host: str = Field(default="localhost")
    port: int = Field(default=6379)
    db: int = Field(default=0)
    password: str = Field(default="")


class CelerySettings(BaseSettings):
    """Celery configuration."""
    broker_url: str = Field(default="redis://localhost:6379/1")
    result_backend: str = Field(default="redis://localhost:6379/2")
    task_serializer: str = Field(default="json")
    result_serializer: str = Field(default="json")
    accept_content: list = Field(default=["json"])
    timezone: str = Field(default="UTC")
    enable_utc: bool = Field(default=True)
    task_track_started: bool = Field(default=True)
    task_time_limit: int = Field(default=3600)
    task_soft_time_limit: int = Field(default=3300)


class SyncSettings(BaseSettings):
    """Data source sync configuration."""

    # Polling intervals (seconds)
    slack_poll_interval: int = Field(default=900)  # 15 minutes
    github_poll_interval: int = Field(default=3600)  # 1 hour
    jira_poll_interval: int = Field(default=3600)
    logs_poll_interval: int = Field(default=300)  # 5 minutes
    metrics_poll_interval: int = Field(default=900)  # 15 minutes
    error_traces_poll_interval: int = Field(default=600)  # 10 minutes
    business_data_poll_interval: int = Field(default=3600)  # 1 hour

    # Retry settings
    max_retries: int = Field(default=3)
    retry_backoff_seconds: int = Field(default=60)

    # Monitored services for log aggregation
    monitored_services: list = Field(default=["api-backend", "worker-queue", "scheduler"])


class IntegrationSettings(BaseSettings):
    """Integration credentials and endpoints."""

    # Slack
    slack_bot_token: str = Field(default="")
    slack_signing_secret: str = Field(default="")

    # GitHub
    github_token: str = Field(default="")
    github_webhook_secret: str = Field(default="")

    # Jira
    jira_instance_url: str = Field(default="")
    jira_username: str = Field(default="")
    jira_api_token: str = Field(default="")

    # Web scraping
    web_scraper_timeout: int = Field(default=30)
    web_scraper_max_content_size: int = Field(default=10 * 1024 * 1024)  # 10MB
    user_agent: str = Field(default="Godspeed-Bot/1.0")

    # Logging
    log_file_paths: dict = Field(default={"api": "/var/log/api.log", "worker": "/var/log/worker.log"})

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


class Settings(BaseSettings):
    """Root configuration object."""

    # App
    app_name: str = Field(default="Godspeed")
    debug: bool = Field(default=False)

    # Supabase (shared with ingestion layer; leave blank for local-only dev)
    supabase_url: str = Field(default="")
    supabase_key: str = Field(default="")

    # Flat Redis URL used by health check and async Redis clients
    redis_url: str = Field(default="redis://localhost:6379/0")

    # Qdrant — local: leave qdrant_url empty and use host+port.
    # Hosted (Qdrant Cloud): set qdrant_url=https://xyz.cloud.qdrant.io:6333
    # and qdrant_api_key to your cluster API key.
    qdrant_host:    str = Field(default="localhost")
    qdrant_port:    int = Field(default=6333)
    qdrant_url:     str = Field(default="")       # overrides host+port when non-empty
    qdrant_api_key: str = Field(default="")       # required for Qdrant Cloud

    # Auth (dev credentials — override in .env)
    demo_email:    str  = Field(default="demo@godspeed.local")
    demo_password: str  = Field(default="demo")
    admin_email:   str  = Field(default="admin@godspeed.local")
    admin_password: str = Field(default="admin")
    # Set True when running behind HTTPS so session cookies are Secure
    cookie_secure: bool = Field(default=False)

    # Google OAuth2 / SSO
    google_oauth_client_id:     str = Field(default="")
    google_oauth_client_secret: str = Field(default="")
    google_oauth_redirect_uri:  str = Field(default="http://localhost:8000/api/auth/google/callback")
    frontend_url:               str = Field(default="http://localhost:3000")

    # CORS — comma-separated list of allowed origins.
    # NOTE: cannot be "*" when allow_credentials=True (CORS spec requirement).
    cors_origins: str = Field(default="http://localhost:5173,http://localhost:3000")

    # Services
    redis: RedisSettings = Field(default_factory=RedisSettings)
    celery: CelerySettings = Field(default_factory=CelerySettings)
    sync: SyncSettings = Field(default_factory=SyncSettings)
    integrations: IntegrationSettings = Field(default_factory=IntegrationSettings)

    class Config:
        env_file = ".env"
        nested_delimiter = "__"
        case_sensitive = False
        extra = "ignore"


# Load settings
settings = Settings()
