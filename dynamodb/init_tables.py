"""Inicializa las tablas de DynamoDB definidas en los JSON del proyecto."""
import json
import os
import sys
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError, EndpointConnectionError


DYNAMODB_ENDPOINT_URL = os.getenv(
    "DYNAMODB_ENDPOINT_URL",
    "http://dynamodb-local:8000",
)
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "local")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "local")

MAX_RETRIES = 30
RETRY_DELAY_SECONDS = 2

SCRIPT_DIRECTORY = Path(__file__).resolve().parent

SCHEMA_FILES = [
    "create-users.json",
    "create-events.json",
    "create-alerts.json",
    "create-audit-logs.json",
    "create-simulations.json",
]


def get_dynamodb_client():
    """Construye el cliente de DynamoDB usando la configuración del entorno."""
    return boto3.client(
        "dynamodb",
        endpoint_url=DYNAMODB_ENDPOINT_URL,
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )


def wait_for_dynamodb(client):
    """Espera a que DynamoDB responda, aplicando reintentos limitados."""
    print(f"Esperando a DynamoDB en {DYNAMODB_ENDPOINT_URL}...", flush=True)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            client.list_tables()
            print("DynamoDB está disponible.", flush=True)
            return
        except EndpointConnectionError:
            pass
        except ClientError as error:
            code = error.response.get("Error", {}).get("Code", "")
            if code not in {
                "InternalServerError",
                "ServiceUnavailable",
                "RequestTimeout",
            }:
                raise

        if attempt < MAX_RETRIES:
            print(
                f"Intento {attempt}/{MAX_RETRIES}: "
                f"DynamoDB todavía no está disponible. "
                f"Reintentando en {RETRY_DELAY_SECONDS} segundos...",
                flush=True,
            )
            time.sleep(RETRY_DELAY_SECONDS)

    raise TimeoutError(
        f"DynamoDB no estuvo disponible después de "
        f"{MAX_RETRIES} intentos."
    )


def load_schema(filename):
    """Lee y valida que el JSON contenga una definición de tabla."""
    schema_path = SCRIPT_DIRECTORY / filename

    if not schema_path.is_file():
        raise FileNotFoundError(
            f"No se encontró el archivo de esquema: {schema_path}"
        )

    try:
        with schema_path.open("r", encoding="utf-8-sig") as schema_file:
            schema = json.load(schema_file)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"El JSON {filename} no es válido: {error}"
        ) from error

    if not isinstance(schema, dict) or not schema.get("TableName"):
        raise ValueError(
            f"El archivo {filename} debe contener una definición "
            f"de tabla con el campo TableName."
        )

    return schema


def create_missing_tables(client):
    """Crea las tablas ausentes utilizando sus definiciones JSON originales."""
    existing_tables = set()
    paginator = client.get_paginator("list_tables")

    for page in paginator.paginate():
        existing_tables.update(page.get("TableNames", []))

    for filename in SCHEMA_FILES:
        schema = load_schema(filename)
        table_name = schema["TableName"]

        if table_name in existing_tables:
            print(
                f"[OMITIDA] La tabla {table_name} ya existe.",
                flush=True,
            )
            continue

        print(
            f"[CREANDO] Tabla {table_name} desde {filename}...",
            flush=True,
        )

        try:
            client.create_table(**schema)
        except ClientError as error:
            code = error.response.get("Error", {}).get("Code", "")

            # Protege ante una tabla creada concurrentemente.
            if code == "ResourceInUseException":
                print(
                    f"[OMITIDA] La tabla {table_name} ya existe.",
                    flush=True,
                )
                continue

            raise RuntimeError(
                f"No se pudo crear la tabla {table_name}: "
                f"{code} - "
                f"{error.response.get('Error', {}).get('Message', '')}"
            ) from error

        existing_tables.add(table_name)

    print("Esperando a que todas las tablas estén disponibles...", flush=True)

    for filename in SCHEMA_FILES:
        schema = load_schema(filename)
        table_name = schema["TableName"]

        try:
            client.get_waiter("table_exists").wait(
                TableName=table_name,
                WaiterConfig={
                    "Delay": 2,
                    "MaxAttempts": 30,
                },
            )
        except Exception as error:
            raise RuntimeError(
                f"La tabla {table_name} no estuvo disponible "
                f"a tiempo o no pudo verificarse."
            ) from error

        description = client.describe_table(TableName=table_name)
        status = description["Table"]["TableStatus"]

        if status != "ACTIVE":
            raise RuntimeError(
                f"La tabla {table_name} terminó con estado {status}, "
                "en lugar de ACTIVE."
            )

        print(
            f"[LISTA] Tabla {table_name}: {status}.",
            flush=True,
        )

    print(
        "Inicialización de DynamoDB completada correctamente.",
        flush=True,
    )


def main():
    client = get_dynamodb_client()
    wait_for_dynamodb(client)
    create_missing_tables(client)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(
            f"ERROR: Falló la inicialización de DynamoDB: {error}",
            file=sys.stderr,
            flush=True,
        )
        sys.exit(1)
