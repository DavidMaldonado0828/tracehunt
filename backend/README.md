# Backend de TraceHunt

API FastAPI con autenticación JWT, autorización por cuenta/rol, administración de usuarios y repositorio DynamoDB. Incluye `GET /health`; las funciones de eventos, alertas y simulaciones siguen pendientes.

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

## Autenticación y administración

Las cuentas se administran con `POST /users`, `GET /users`, `PATCH /users/{email}/role` y `PATCH /users/{email}/status`; todas requieren un bearer token de una cuenta activa con rol `admin`. Las contraseñas se reciben solo al crear la cuenta y se hashean en el backend. Las respuestas usan `UserPublic` y no incluyen hashes.

El login permite 5 intentos consecutivos fallidos por correo normalizado y dirección IP durante una ventana deslizante de 900 segundos. El sexto intento dentro de la ventana recibe `429` y `Retry-After`; un login exitoso borra el contador de esa combinación. Los límites se configuran con `LOGIN_RATE_LIMIT_ATTEMPTS` y `LOGIN_RATE_LIMIT_WINDOW_SECONDS`. El contador guarda únicamente una huella SHA-256 de correo e IP, nunca la contraseña ni el token.

El limitador está en memoria y sincronizado por proceso. Las peticiones concurrentes dentro del mismo proceso comparten el contador; varios workers/instancias no comparten estado y un reinicio lo vacía. Los contadores caducan por ventana y se eliminan en peticiones posteriores. Se eligió este alcance temporal porque `Users` solo permite acceso por correo y guardar contadores para correos inexistentes en esa tabla crearía registros que no son usuarios; un limitador distribuido requiere aprobar y provisionar almacenamiento compartido. No se confían cabeceras `X-Forwarded-For` sin configurar explícitamente un proxy de confianza.

La gestión impide desactivar o degradar al último administrador activo. La comprobación se basa en el listado de usuarios y no es atómica frente a dos modificaciones administrativas simultáneas; una garantía de concurrencia estricta requiere un mecanismo de coordinación aprobado.

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
