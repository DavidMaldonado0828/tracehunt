"""Configuración de la aplicación cargada desde el entorno."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centraliza la configuración para mantenerla validada y reutilizable."""

    app_env: str = "local"
    aws_region: str = "us-east-1"
    dynamodb_endpoint_url: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    jwt_secret: str | None = None
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    login_rate_limit_attempts: int = 5
    login_rate_limit_window_seconds: int = 900

    users_table: str = "Users"
    events_table: str = "Events"
    alerts_table: str = "Alerts"
    audit_logs_table: str = "AuditLogs"
    simulations_table: str = "Simulations"

    # Se ignoran claves ajenas a esta aplicación para permitir archivos .env compartidos.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Reutiliza la configuración validada durante la vida del proceso."""
    return Settings()
