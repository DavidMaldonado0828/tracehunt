# Backend de TraceHunt

Esqueleto inicial de la API FastAPI. Incluye configuración mínima, router raíz y `GET /health`. Todavía no implementa autenticación, lógica de negocio ni conexión a DynamoDB.

## Desarrollo local

Desde `backend/`, crea un entorno virtual e instálalo con sus dependencias de prueba:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Inicia la API y ejecuta las pruebas:

```bash
uvicorn app.main:app --reload
pytest
```

La comprobación de salud está disponible en `http://127.0.0.1:8000/health`. Ese endpoint confirma que responde el proceso HTTP; no comprueba DynamoDB.

## Estructura prevista

- `app/api/`: router raíz y endpoints HTTP; sin reglas de negocio.
- `app/core/`: configuración y responsabilidades transversales de seguridad y errores.
- `app/schemas/`: futuros contratos de entrada y salida con Pydantic v2.
- `app/models/`: futuros modelos de dominio internos, solo cuando estén justificados.
- `app/repositories/`: futura persistencia DynamoDB conforme al diseño aprobado.
- `app/services/`: futuros casos de uso y reglas de negocio.
- `app/detectors/`: futuras reglas deterministas de detección.
- `app/simulator/`: futura generación y recuperación de simulaciones.
- `app/api/endpoints/`: módulos previstos para autenticación, usuarios, eventos, alertas y simulaciones; todavía no implementados.
- `tests/api/`, `tests/unit/` y `tests/integration/`: pruebas por nivel.

Los módulos que solo contienen una descripción señalan responsabilidades previstas y no indican que la funcionalidad esté implementada.
