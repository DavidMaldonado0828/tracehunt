# TraceHunt

TraceHunt es un laboratorio defensivo para explorar cómo se detectan patrones sospechosos en eventos de autenticación. Genera actividad ficticia, la analiza con reglas deterministas y presenta alertas que un analista puede investigar.

Una alerta es una señal para revisión; por sí sola no confirma que haya ocurrido un ataque. TraceHunt no ejecuta ataques, no bloquea cuentas y no se conecta a fuentes reales de logs o a otros SIEM.

## ¿Para qué sirve?

El proyecto busca ofrecer un entorno práctico para:

- Simular eventos de autenticación controlados y reproducibles.
- Detectar patrones como intentos fallidos repetidos, pruebas de varias cuentas y un inicio exitoso después de fallos.
- Revisar alertas y la evidencia de eventos que las originaron.
- Aprender y validar el flujo de un SIEM pequeño sin depender de una cuenta de AWS.

El MVP contempla cuatro reglas: `AUTH-001` (fallos repetidos), `AUTH-002` (una IP prueba varias cuentas), `AUTH-003` (éxito después de fallos) y `AUTH-004` (actividad fuera del horario configurado). AUTH-004 permanece desactivada hasta que se aprueben un horario de referencia y su severidad.

## Estado del proyecto

El repositorio contiene una implementación local en desarrollo. Actualmente incluye una API en FastAPI, interfaz web básica servida por la API, simulador y motor de detección en Python, y persistencia con DynamoDB Local. El Workplan registra trabajo pendiente para completar y verificar los flujos del MVP; por eso este README no presenta el proyecto como terminado ni como desplegado en AWS.

## Arquitectura local

Docker Compose coordina los servicios de desarrollo:

| Componente | Responsabilidad |
| --- | --- |
| Interfaz web | Permite interactuar con TraceHunt desde el navegador; FastAPI sirve sus archivos estáticos. |
| API FastAPI | Expone la API y concentra autenticación, validación, lógica de negocio, simulaciones y detección. |
| DynamoDB Local | Almacena usuarios, eventos, alertas, auditoría y ejecuciones de simulación. |
| Inicializador | Crea las tablas locales a partir de sus definiciones JSON antes de iniciar la API. |

La aplicación usa Python, FastAPI y Boto3 en el backend, y HTML, CSS y JavaScript en la interfaz actual. La arquitectura local no representa una configuración de producción.

## Inicio rápido

Requisitos: Docker y Docker Compose.

1. Configura el archivo local de variables de entorno siguiendo [`backend/README.md`](backend/README.md) y la plantilla [`backend/.env.example`](backend/.env.example). No compartas ni agregues credenciales al repositorio.
2. Desde la raíz del proyecto, inicia los servicios:

   ```bash
   docker compose up --build
   ```

3. Abre la interfaz en [http://localhost:8080/ui](http://localhost:8080/ui). La documentación interactiva de la API está en [http://localhost:8080/docs](http://localhost:8080/docs).
4. Para detener los servicios, usa `Ctrl+C` y luego:

   ```bash
   docker compose down
   ```

La API se publica en el puerto `8080` y DynamoDB Local en `8000`. La inicialización automática de las tablas está descrita en [`docs/INICIALIZACION_DYNAMODB.md`](docs/INICIALIZACION_DYNAMODB.md).

## Documentación del proyecto

- [Requisitos y reglas de detección](docs/01-srs/TraceHunt_SRS.md)
- [Diseño de base de datos](docs/03-database/TraceHunt_Database_Design.md)
- [Workplan, dependencias y decisiones pendientes](docs/02-workplans/workplan.md)
- [Contexto del sistema](docs/architecture/c4-context.md)
- [Contenedores de la arquitectura local](docs/architecture/c4-containers-local.md)
- [Stack tecnológico local](docs/technology-stack/local.md)
- [Inicialización de DynamoDB Local](docs/INICIALIZACION_DYNAMODB.md)

Consulta esos documentos antes de asumir que una decisión pendiente o una funcionalidad prevista ya está aprobada o implementada.

## Alcance y límites

TraceHunt está pensado para análisis y aprendizaje defensivo. Los eventos del simulador son ficticios y usan datos reservados para documentación. El MVP no incluye aprendizaje automático, acciones ofensivas, respuesta automática, editor de reglas, fuentes reales de logs ni integración con SIEM externos. El despliegue en AWS también queda fuera del entorno local y requiere completar las decisiones y tareas correspondientes.
