"""Construcción diferida del recurso DynamoDB usado por los repositorios."""

from functools import lru_cache

import boto3

from app.core.config import get_settings


@lru_cache
def get_dynamodb_resource():
    """Crea el recurso al solicitarlo; boto3 no conecta hasta ejecutar operaciones."""
    settings = get_settings()
    options: dict[str, str] = {"region_name": settings.aws_region}

    if settings.dynamodb_endpoint_url:
        # El endpoint explícito dirige el cliente a DynamoDB Local cuando está configurado.
        options["endpoint_url"] = settings.dynamodb_endpoint_url

    if settings.aws_access_key_id and settings.aws_secret_access_key:
        # Solo se fijan claves cuando ambas están configuradas; de otro modo boto3 usa su cadena estándar.
        options["aws_access_key_id"] = settings.aws_access_key_id
        options["aws_secret_access_key"] = settings.aws_secret_access_key

    return boto3.resource("dynamodb", **options)
