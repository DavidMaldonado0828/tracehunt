"""Configuración mínima del proceso, cargada desde variables de entorno."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Valores generales; todavía no configura clientes de AWS o DynamoDB."""

    app_env: str = "local"
    aws_region: str = "us-east-1"
    dynamodb_endpoint_url: str | None = "http://localhost:8000"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
