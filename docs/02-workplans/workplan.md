# TraceHunt — Workplan del MVP

**Estado:** propuesta de implementación; todas las tareas están pendientes.  
**Fuentes:** [SRS](../01-srs/TraceHunt_SRS.md) y [diseño de DynamoDB](../03-database/TraceHunt_Database_Design.md).  
**Prioridad:** todas las tareas listadas son `[MUST]` para el MVP confirmado. Las cuatro reglas forman parte del alcance; AUTH-004 permanecerá apagada hasta contar con la configuración pendiente de horario.

`[MUST]` identifica alcance funcional obligatorio, no orden ni estado. Cada tarea incluye su esfuerzo inicial y responsable sugerido. Todas comienzan en `- [ ]`.

### Regla para cerrar una tarea

Una tarea solo puede marcarse `- [x]` después de implementar su alcance, cumplir sus criterios de aceptación, ejecutar y superar las pruebas indicadas, verificar integración y permisos cuando apliquen, y registrar evidencia suficiente (por ejemplo, referencia a ejecución de pruebas o demostración reproducible). Crear archivos, escribir código, abrir un PR o completar parcialmente una funcionalidad no basta. Una prueba no ejecutada no se considera superada.

### Plazo y capacidad

La estimación inicial de las 50 tareas es **197 horas de ingeniería**, incluyendo verificación local de tarea. Para planificar “menos de dos semanas” se asumen nueve días laborables y dos desarrolladores: capacidad bruta de 144 horas, antes de reuniones, decisiones y contingencias. El trabajo excede esa capacidad en **53 horas**; por tanto, no es realista comprometer el MVP completo en nueve días con el equipo indicado. La tabla de secuencia propone el orden de un objetivo comprimido, no garantiza su fecha. No se excluyen funcionalidades: para mantener el alcance, hace falta ampliar tiempo/capacidad o reducir trabajo técnico no esencial y acabados, no reglas ni flujos funcionales.

Las estimaciones son de planificación y deben recalibrarse al tomar las decisiones pendientes y crear el primer esqueleto (hoy no hay código de aplicación en el repositorio). Con el reparto actual quedan aproximadamente A=100,5 h y B=96,5 h, contando mitad del trabajo compartido: cada persona supera su capacidad bruta de 72 h. Los responsables A/B son propuestas: A prioriza autenticación, persistencia y orquestación; B prioriza interfaz, esquemas locales y algunos flujos de consulta/reglas; ambos hacen integración. “Compartido” requiere coordinación.

**Reducción de complejidad sin recortar alcance:** mantener una sola aplicación FastAPI y ejecución secuencial limitada a 300 eventos; no añadir cola distribuida, servicios externos, tabla nueva, CI/CD, analítica precomputada ni pulido visual; usar pruebas automatizadas dirigidas a permisos, reglas, reintentos, ownership y aceptación integrada. Estas simplificaciones no eliminan reglas ni flujos confirmados y podrían reducir esfuerzo, pero no se estima que compensen por sí solas las 53 horas de diferencia.

## Estado actual del repositorio

El repositorio revisado contiene `README.md`, `docs/arquitectura.md`, el SRS y el diseño de base de datos. No se encontraron estructuras de backend FastAPI, frontend Angular, infraestructura Docker ni pruebas de aplicación. No se encontró `TraceHunt_Requisitos_y_Reglas.md`; el documento de requisitos disponible es `TraceHunt_SRS.md`. Las rutas de código citadas en las tareas son una propuesta inicial de organización, no evidencia de componentes existentes. Antes de crear módulos, validar la estructura con el equipo y conservar la arquitectura aprobada.

### Secuencia objetivo de nueve días laborables (riesgo alto de extensión)

| Día | Desarrollador A | Desarrollador B | Integración/puerta |
|---|---|---|---|
| 1 | Decisiones bloqueantes inmediatas, Docker/DynamoDB, contrato API compartido | Contrato API compartido y shell Angular contra contrato aprobado | No iniciar repositorios que dependan de GSIs aún no aprobados |
| 2 | Configuración/modelos/repositorios iniciales | Cliente API, navegación pública/privada y login con mocks ya contratados | Primer flujo login de extremo a extremo |
| 3 | Login FastAPI, roles y cuentas | Integrar login; consulta Angular de eventos | Prueba API/Angular y DynamoDB Local |
| 4 | Consultas de eventos/paginación | Integrar filtros y cursores; pruebas de acceso | Flujo eventos visible con permisos acordados |
| 5 | Motor y AUTH-001/002 | AUTH-003/004 apagada/configurable y escenarios de prueba | Acordar límites de ventana/episodios antes de deduplicar coincidencias ampliadas |
| 6 | Persistencia de alertas, gestión/auditoría | Lista/detalle de alertas con filtro de propietario | Flujo de investigación vertical; OwnerCreatedIndex debe estar aprobado |
| 7 | Simulador, lease e idempotencia | UI del simulador e historial | Recuperación de interrupción y concurrencia en DynamoDB Local |
| 8 | Integración de detección y contadores/reintentos | Completar UI de gestión y simulador; regresión de flujos | Corregir contrato, permisos y estados parciales |
| 9 | Validación crítica, configuración mínima AWS | Documentación y smoke tests UI/API | Reserva para integración/correcciones; no garantiza cierre de todo el alcance |

La secuencia paralela comienza solo después de acordar contratos y decisiones que afectan a ambos lados. Las interfaces de Angular se integran por flujo desde las fases correspondientes; F8 no es una fase de integración aplazada. Las 197 horas estimadas equivalen a unas 12,3 jornadas laborables de calendario a capacidad plena de dos personas, antes de interrupciones, así que el objetivo de nueve días tiene riesgo alto y no es un compromiso viable sin recortar refinamientos no esenciales o ampliar capacidad/tiempo.

## Dependencias principales

```text
F1 Entorno y tablas
  └─ F2 Base FastAPI, modelos y repositorios
       ├─ F3 Usuarios, autenticación y permisos
       │    ├─ F4 Consultas de eventos
       │    ├─ F6 Gestión de alertas y auditoría
       │    └─ F7 Simulador e historial
       └─ F5 Motor y reglas ──> F6, F7
F2 fija contratos API ──> Angular arranca en paralelo y cierra cada flujo junto a F3–F7
F3–F7 ──> aceptación integrada, documentación y despliegue mínimo (F8)
```

## F1. Entorno de desarrollo y esquema local

**Objetivo:** hacer reproducible el entorno local y crear las cinco tablas aprobadas en DynamoDB Local.

- **Dependencias:** decisiones de índices y campos que cambian el esquema.
- **Entregable:** DynamoDB Local operativo y esquema físico aprobado reproducible.
- **Aceptación/pruebas:** cada tabla/índice se crea y verifica con CLI; no hay divergencias respecto al diseño aprobado.
- **Responsable sugerido:** A con apoyo compartido en revisión.
- **Bloqueos:** aprobación de GSIs propuestos y campos de ownership/checkpoint; no crear índices candidatos como si ya estuvieran aprobados.

### F1-B1. Entorno local

#### F1-B1-T1 — Configuración local de Docker `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 2 h. **Responsable sugerido:** B.

- **Objetivo y alcance:** preparar el arranque local de DynamoDB Local y persistencia de sus datos; documentar endpoint y región local.
- **Archivos/componentes probables:** `docker-compose.yml`, `docker/`, `.env.example`, README de desarrollo.
- **Dependencias:** ninguna.
- **Criterios de aceptación:** Docker levanta DynamoDB Local en la dirección documentada; los datos sobreviven un reinicio del contenedor; los secretos no se incluyen en el repositorio.
- **Pruebas necesarias:** comprobación de disponibilidad, conexión AWS CLI y persistencia tras reiniciar el servicio.
- **Decisiones pendientes:** ninguna.

### F1-B2. Definiciones de tablas

#### F1-B2-T1 — Aprobar y crear `Users` y sus claves `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 1 h. **Responsable sugerido:** B.

- **Objetivo y alcance:** crear la tabla con PK `email_normalized`; evaluar/aprobar primero GSI candidato `UserIdIndex` sobre `user_id` para validación de asignaciones y actoría. El GSI aún no está aprobado por aparecer en un borrador.
- **Archivos/componentes probables:** `infra/dynamodb/create-users.json`.
- **Dependencias:** F1-B1-T1; aprobación del GSI `UserIdIndex` si se decide crearlo.
- **Criterios de aceptación:** PK y tipo coinciden con diseño; GSI solo se crea tras aprobación; `AttributeDefinitions` solo declara claves.
- **Pruebas necesarias:** creación local y `describe-table`; `Query` por correo y por ID si el GSI se aprueba.
- **Decisiones pendientes:** DEC-01 para `UserIdIndex`.

#### F1-B2-T2 — Crear `Events` y sus GSIs `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 1 h. **Responsable sugerido:** B.

- **Objetivo y alcance:** definir PK `event_id` y `DateTimestampIndex`, `SourceIpTimestampIndex` y `UsernameTimestampIndex` con las claves aprobadas.
- **Archivos/componentes probables:** `infra/dynamodb/create-events.json`.
- **Dependencias:** F1-B1-T1.
- **Criterios de aceptación:** tipos, claves y nombres de índices coinciden con el diseño; timestamps y buckets permiten orden lexicográfico UTC.
- **Pruebas necesarias:** creación local y `Query` de ejemplo por cada índice.
- **Decisiones pendientes:** DEC-02 si los eventos requieren visibilidad por propietario.

#### F1-B2-T3 — Aprobar patrón propietario y crear `Alerts` `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 1 h. **Responsable sugerido:** B.

- **Objetivo y alcance:** definir PK `alert_id` y los índices aprobados por estado/severidad; decidir el GSI candidato `OwnerCreatedIndex` para la visibilidad confirmada por propietario y guardar `simulation_owner_user_id` en la alerta.
- **Archivos/componentes probables:** `infra/dynamodb/create-alerts.json`.
- **Dependencias:** F1-B1-T1; aprobación del patrón/GSI `OwnerCreatedIndex` para consulta indexada por propietario.
- **Criterios de aceptación:** índices estado/severidad coinciden con diseño; propietario deriva de la ejecución en backend, nunca del cliente; `OwnerCreatedIndex` solo se crea tras aprobación explícita.
- **Pruebas necesarias:** creación local y consultas de ejemplo por estado y severidad.
- **Decisiones pendientes:** DEC-01 para `OwnerCreatedIndex`.

#### F1-B2-T4 — Crear `AuditLogs` `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 1 h. **Responsable sugerido:** B.

- **Objetivo y alcance:** definir PK `alert_id` y SK `change_key`.
- **Archivos/componentes probables:** `infra/dynamodb/create-audit-logs.json`.
- **Dependencias:** F1-B1-T1.
- **Criterios de aceptación:** consulta por alerta retorna cambios ordenables cronológicamente; no se añade un GSI no aprobado.
- **Pruebas necesarias:** crear elementos de ejemplo y consultar por PK en orden.
- **Decisiones pendientes:** ninguna.

#### F1-B2-T5 — Aprobar acceso por solicitante y crear `Simulations` `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 1 h. **Responsable sugerido:** B.

- **Objetivo y alcance:** definir PK `simulation_id`, `StatusRequestedIndex` y decidir el GSI candidato `RequesterRequestedIndex` para consultas propias de analyst.
- **Archivos/componentes probables:** `infra/dynamodb/create-simulations.json`.
- **Dependencias:** F1-B1-T1; aprobación del GSI `RequesterRequestedIndex` para la lista por solicitante.
- **Criterios de aceptación:** consulta por estado cumple el diseño; GSI por solicitante solo se crea tras aprobación; tipos/proyección/documentación se alinean.
- **Pruebas necesarias:** creación local y consultas de ejemplo en ambos índices.
- **Decisiones pendientes:** DEC-01 para `RequesterRequestedIndex`; DEC-04/05 para atributos de lease/checkpoint.

#### F1-B2-T6 — Verificación integral del esquema `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 2 h. **Responsable sugerido:** Compartido.

- **Objetivo y alcance:** comprobar que las cinco tablas y todos los GSIs se pueden crear desde cero y que las definiciones son coherentes con los documentos fuente.
- **Archivos/componentes probables:** `infra/dynamodb/`, guía local.
- **Dependencias:** F1-B2-T1 a F1-B2-T5 y aprobación de cada GSI/campo candidato.
- **Criterios de aceptación:** creación limpia repetible; solo esquema aprobado está en los JSON; nombres/claves/atributos físicos contrastados; carpeta de datos locales separada.
- **Pruebas necesarias:** ejecución de creación desde entorno limpio y comparación automatizada o documentada de `describe-table` con el diseño.
- **Decisiones pendientes:** DEC-01, DEC-03 a DEC-05 según extensiones de esquema aprobadas.

## F2. Base FastAPI, configuración y persistencia

**Objetivo:** preparar contratos, validación y repositorios reutilizables, sin desplazar lógica de negocio al frontend ni a DynamoDB.

- **Dependencias:** F1; los repositorios por GSI esperan la aprobación del patrón/índice correspondiente.
- **Entregable:** base FastAPI local y contratos de API acordados que permitan integración Angular en paralelo.
- **Aceptación/pruebas:** validación de modelos, consultas y errores contra DynamoDB Local; contrato describe método/ruta, entrada, salida, códigos HTTP, autorización, paginación y error.
- **Responsable sugerido:** A en backend; contrato compartido con B.
- **Bloqueos:** definir contrato antes de trabajo paralelo en UI; no inventar rutas o visibilidad.

### F2-B1. Aplicación y configuración

#### F2-B1-T1 — Esqueleto FastAPI y configuración por entorno `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 3 h. **Responsable sugerido:** A.

- **Objetivo y alcance:** crear el punto de entrada, configuración validada y separación entre entorno local y AWS.
- **Archivos/componentes probables:** `backend/app/main.py`, `backend/app/core/config.py`, `backend/pyproject.toml` o equivalente.
- **Dependencias:** F1-B1-T1.
- **Criterios de aceptación:** la aplicación inicia localmente; falla con error seguro si falta configuración esencial; DynamoDB Local usa credenciales ficticias de desarrollo y AWS usa cadena de proveedor/rol sin credenciales reales en desarrollo.
- **Pruebas necesarias:** pruebas de configuración válida, incompleta y selección del endpoint por entorno.
- **Decisiones pendientes:** selección de librería de cliente Python, a documentar como decisión de implementación sin cambiar la arquitectura.

#### F2-B1-T2 — Modelos y valores controlados `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 3 h. **Responsable sugerido:** A.

- **Objetivo y alcance:** representar usuarios, eventos, alertas, simulaciones y auditoría; validar roles, estados, resultados y severidades.
- **Archivos/componentes probables:** `backend/app/models/`, `backend/app/schemas/`.
- **Dependencias:** F2-B1-T1.
- **Criterios de aceptación:** valores fuera de catálogo se rechazan antes de persistir; fechas se normalizan a ISO 8601 UTC; respuestas no exponen hashes ni secretos.
- **Pruebas necesarias:** validación positiva/negativa de valores, timestamps y campos sensibles.
- **Decisiones pendientes:** ninguna.

### F2-B2. Repositorios y persistencia

#### F2-B2-T1 — Repositorios de usuarios y simulaciones `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 4 h. **Responsable sugerido:** A.

- **Objetivo y alcance:** implementar accesos `GetItem` por correo/ID, lecturas/escrituras condicionales de usuario y acceso a simulaciones por ID e índices aprobados.
- **Archivos/componentes probables:** `backend/app/repositories/users.py`, `simulations.py`.
- **Dependencias:** F1-B2-T1, F1-B2-T5, F2-B1-T2.
- **Criterios de aceptación:** operaciones encapsulan claves e índices correctos; escritura condicional distingue conflicto de error transitorio; no realiza `Scan` en consultas de usuario por ID.
- **Pruebas necesarias:** repositorios contra DynamoDB Local con fixtures aisladas y pruebas de condición concurrente.
- **Decisiones pendientes:** ninguna.

#### F2-B2-T2 — Repositorios de eventos, alertas y auditoría `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 4 h. **Responsable sugerido:** A.

- **Objetivo y alcance:** implementar lecturas/escrituras respetando PK, SK y GSIs aprobados.
- **Archivos/componentes probables:** `backend/app/repositories/events.py`, `alerts.py`, `audit_logs.py`.
- **Dependencias:** F1-B2-T2 a F1-B2-T4, F2-B1-T2.
- **Criterios de aceptación:** los repositorios usan `GetItem`, `Query`, `PutItem`/`UpdateItem` según el patrón; escrituras de alerta/auditoría pueden ser idempotentes donde corresponde.
- **Pruebas necesarias:** integración local de cada patrón definido en AP-04 a AP-16.
- **Decisiones pendientes:** ninguna.

#### F2-B2-T3 — Escrituras por lote, reintentos y límites DynamoDB `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 4 h. **Responsable sugerido:** B.

- **Objetivo y alcance:** encapsular `BatchWriteItem` en grupos de hasta 25, reintentar `UnprocessedItems` con espera progresiva y tope; usarlo solo donde el protocolo aprobado no requiera condiciones/checkpoint atómico. La ruta recuperable del simulador debe acordar si usa transacciones o escrituras condicionales.
- **Archivos/componentes probables:** `backend/app/repositories/batch_writer.py`, `backend/app/core/retry.py`.
- **Dependencias:** F2-B2-T2.
- **Criterios de aceptación:** divide lotes; reintenta solo elementos no procesados; comunica agotamiento sin marcar éxito; nunca se asume que BatchWriteItem ofrece condiciones o transacción.
- **Pruebas necesarias:** lotes de 1, 25 y más de 25; respuesta simulada con elementos no procesados; agotamiento de reintentos.
- **Decisiones pendientes:** fijar constantes de backoff y máximo de reintentos como configuración del backend.

#### F2-B2-T4 — Paginación opaca y combinación ordenada `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 5 h. **Responsable sugerido:** B.

- **Objetivo y alcance:** construir cursors opacos para una o varias consultas DynamoDB, manteniendo orden global para días o estados múltiples.
- **Archivos/componentes probables:** `backend/app/services/pagination.py`, serialización de cursores.
- **Dependencias:** F2-B2-T2.
- **Criterios de aceptación:** límite predeterminado 25, máximo 100; cursores validables, opacos y vinculados al filtro; páginas fusionadas preservan orden y no pierden elementos entre particiones; cursor nulo al finalizar.
- **Pruebas necesarias:** varias páginas en un día, intervalo multi-día, multiestado y empates de timestamp usando claves compuestas.
- **Decisiones pendientes:** definir protección criptográfica del cursor (firma) en la decisión técnica de API; no debe permitir que el cliente manipule claves DynamoDB.

#### F2-B2-T5 — Errores y registros seguros `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 3 h. **Responsable sugerido:** A.

- **Objetivo y alcance:** normalizar errores de API y registros de aplicación sin secretos, hashes ni datos internos innecesarios.
- **Archivos/componentes probables:** `backend/app/core/errors.py`, `logging.py`, manejadores FastAPI.
- **Dependencias:** F2-B1-T1, F2-B1-T2.
- **Criterios de aceptación:** errores previstos tienen respuesta estable; errores inesperados no revelan stack/secretos al cliente; logs omiten contraseñas, tokens y hashes.
- **Pruebas necesarias:** respuestas 4xx/5xx y captura de logs con datos sensibles canario.
- **Decisiones pendientes:** ninguna.

### F2-B3. Contratos de integración y arranque temprano de Angular

#### F2-B3-T1 — Acordar contratos API por flujo `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 5 h. **Responsable sugerido:** Compartido.
- **Objetivo y alcance:** especificar operaciones necesarias para login, usuarios, eventos, alertas/auditoría y simulaciones sin fijar reglas o permisos pendientes. Documentar solicitud, respuesta, validación, códigos HTTP, errores seguros, paginación y autorización.
- **Archivos/componentes probables:** documentación de `docs/` (usar documento existente o acordar uno nuevo antes de crearlo).
- **Dependencias:** SRS y diseño de datos revisados; decisiones de visibilidad se registran como condicionadas.
- **Criterios de aceptación:** Angular y FastAPI acuerdan el mismo contrato; campos corresponden a modelos; los filtros no autorizan acceso por sí solos; operaciones privadas requieren autorización; semántica abierta permanece explícita.
- **Pruebas necesarias:** revisión del contrato contra requisitos, OpenAPI generado al implementar y pruebas de esquema de petición/respuesta.
- **Decisiones pendientes:** visibilidad de eventos, índices de propietario, sesión/token, transiciones/asignación, cursor y clave idempotente. No inventar su semántica.

#### F2-B3-T2 — Arranque de shell Angular y cliente API `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 3 h. **Responsable sugerido:** B.
- **Objetivo y alcance:** iniciar estructura mínima Angular, configuración de base URL y manejo común de errores para que la interfaz avance desde los primeros días.
- **Archivos/componentes probables:** `frontend/src/app/`, configuración de entorno Angular.
- **Dependencias:** F2-B3-T1 para contratos consumidos; no requiere backend completo.
- **Criterios de aceptación:** app arranca; base URL configurable; no contiene secretos de servidor ni credenciales AWS; cliente centraliza llamadas HTTP.
- **Pruebas necesarias:** build local, prueba del cliente/interceptor y revisión de configuración para descartar secretos reales.
- **Decisiones pendientes:** el mecanismo de sesión/token afecta la autenticación HTTP, pero no bloquea el shell público.

## F3. Cuentas, autenticación y autorización

**Objetivo:** entregar el acceso privado y administración de usuarios con controles efectivos en FastAPI.

- **Dependencias:** contrato API F2 y repositorio de usuarios.
- **Entregable:** flujo login Angular–FastAPI–DynamoDB y política de autorización aplicada en backend.
- **Aceptación/pruebas:** matriz anónimo/active analyst/active admin/disabled comprobada desde API y UI.
- **Responsable sugerido:** A backend; B integración de login en paralelo tras congelar el contrato.
- **Bloqueos:** sesión/token, expiración y revocación bloquean el cierre del flujo privado.

### F3-B1. Inicio de sesión y protección

#### F3-B1-T1 — Hash y verificación de contraseñas `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 2 h. **Responsable sugerido:** A.

- **Objetivo y alcance:** encapsular generación/verificación de hashes apropiados; prohibir texto plano y cifrado reversible.
- **Archivos/componentes probables:** `backend/app/services/passwords.py`.
- **Dependencias:** F2-B1-T1, F2-B1-T2.
- **Criterios de aceptación:** credenciales válidas verifican; credenciales inválidas no; el hash nunca forma parte de una respuesta o log.
- **Pruebas necesarias:** hash distinto por sal, verificación correcta/incorrecta y ausencia de hash en serialización.
- **Decisiones pendientes:** escoger algoritmo/parámetros seguros y documentar la configuración.

#### F3-B1-T2 — Sesión/token de autenticación `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 5 h. **Responsable sugerido:** A.

- **Objetivo y alcance:** implementar login por correo normalizado, comprobar estado activo y emitir mecanismo de sesión/token; proteger operaciones privadas y limitar intentos.
- **Archivos/componentes probables:** `backend/app/api/auth.py`, `backend/app/services/auth.py`, `backend/app/core/security.py`.
- **Dependencias:** F2-B2-T1, F3-B1-T1.
- **Criterios de aceptación:** RF-01–RF-04; cuenta disabled no autentica; autenticación inválida no revela si el correo existe; límites de intentos aplicados; credenciales de servidor no llegan a Angular.
- **Pruebas necesarias:** login válido/inválido, cuenta disabled, expiración, revocación según mecanismo y límite de intentos.
- **Decisiones pendientes:** elegir sesión o token, expiración, revocación y almacenamiento seguro; bloquea la implementación de este flujo.

#### F3-B1-T3 — Dependencia de usuario activo y rol `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 3 h. **Responsable sugerido:** A.

- **Objetivo y alcance:** autorizar en cada petición privada el principal autenticado, estado actual de la cuenta y rol requerido.
- **Archivos/componentes probables:** `backend/app/api/dependencies.py`, políticas de autorización.
- **Dependencias:** F3-B1-T2, F2-B2-T1.
- **Criterios de aceptación:** no se confía en rol enviado por navegador; usuario deshabilitado pierde acceso protegido; visitante no puede acceder a rutas privadas.
- **Pruebas necesarias:** matriz anónimo/analyst/admin/disabled en endpoints representativos y pruebas de manipulación de rol cliente.
- **Decisiones pendientes:** ninguna adicional a F3-B1-T2.

### F3-B2. Administración de cuentas

#### F3-B2-T1 — Consulta paginada y gestión de usuarios `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 5 h. **Responsable sugerido:** B.

- **Objetivo y alcance:** ofrecer operaciones de administración que exige SRS solo a `admin`; resolver usuarios por ID mediante `UserIdIndex` y listar con paginación.
- **Archivos/componentes probables:** `backend/app/api/users.py`, `backend/app/services/users.py`.
- **Dependencias:** F3-B1-T3, F2-B2-T1, F2-B2-T4, F2-B3-T1.
- **Criterios de aceptación:** analyst no administra cuentas; roles/estados se validan; secretos y hashes no aparecen en datos listados; asignaciones y referencias usan `user_id`.
- **Pruebas necesarias:** matriz de roles, valores inválidos, paginación y búsqueda por ID.
- **Decisiones pendientes:** definir operaciones administrativas exactas conforme al SRS; no agregar capacidades no requeridas.

## F4. Consulta histórica de eventos

**Objetivo:** permitir investigación por periodo, IP o usuario mediante los índices y cursores aprobados.

- **Dependencias:** autenticación y contrato de eventos; decisión de visibilidad de eventos.
- **Entregable:** búsqueda de eventos utilizable desde Angular con cursores y autorización acordada.
- **Aceptación/pruebas:** consultas indexadas, varias páginas, orden global y permisos validados en DynamoDB Local.
- **Responsable sugerido:** A API/repositorio; B integración Angular.
- **Bloqueos:** resolver si eventos son globales o limitados por simulación antes de exponer consultas.

### F4-B1. API de eventos

#### F4-B1-T1 — Consulta de eventos por periodo `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 5 h. **Responsable sugerido:** A.

- **Objetivo y alcance:** consultar `DateTimestampIndex` para cada día UTC del rango, unir páginas y entregar orden global.
- **Archivos/componentes probables:** `backend/app/api/events.py`, `backend/app/services/event_queries.py`.
- **Dependencias:** F3-B1-T3, F2-B2-T2, F2-B2-T4.
- **Criterios de aceptación:** fechas validadas y normalizadas; paginación 25/100; no usa `Scan`; la respuesta se ordena por `timestamp_event`.
- **Pruebas necesarias:** rango de un día, cruce de meses/año, cursores y límite de página.
- **Decisiones pendientes:** ninguna.

#### F4-B1-T2 — Consulta de eventos por IP `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 3 h. **Responsable sugerido:** A.

- **Objetivo y alcance:** consultar `SourceIpTimestampIndex` con rango temporal y paginación.
- **Archivos/componentes probables:** servicio de consultas y endpoint de eventos.
- **Dependencias:** F4-B1-T1.
- **Criterios de aceptación:** valida IP y rango; usa `Query`; mantiene orden temporal y filtro ligado al cursor.
- **Pruebas necesarias:** entradas válidas/invalidas, rango vacío, varias páginas.
- **Decisiones pendientes:** ninguna.

#### F4-B1-T3 — Consulta de eventos por usuario `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 3 h. **Responsable sugerido:** A.

- **Objetivo y alcance:** normalizar clave de usuario y consultar `UsernameTimestampIndex` por periodo.
- **Archivos/componentes probables:** servicio de consultas y endpoint de eventos.
- **Dependencias:** F4-B1-T1.
- **Criterios de aceptación:** normalización idéntica a la de escritura; consulta indexada, ordenada y paginada.
- **Pruebas necesarias:** equivalencia de variantes de mayúsculas/espacios, filtros de tiempo y páginas.
- **Decisiones pendientes:** ninguna.

## F5. Motor de detección y alertas generadas

**Objetivo:** evaluar eventos históricos en orden de ocurrencia y producir coincidencias reproducibles, trazables e idempotentes.

- **Dependencias:** modelos de evento y reglas detalladas en SRS.
- **Entregable:** AUTH-001–004 implementadas; AUTH-004 sigue apagada hasta configuración válida.
- **Aceptación/pruebas:** umbrales y ventanas cubiertos en límites, datos históricos y replay.
- **Responsable sugerido:** A motor/alert writer; B puede preparar datos de prueba tras acordar contrato de coincidencia.
- **Bloqueos:** episodio entre coincidencias ampliadas y límites inclusivo/exclusivo bloquean deduplicación completa; no impiden reglas puras ni replay exacto.

### F5-B1. Contrato y reglas

#### F5-B1-T1 — Modelo de coincidencia y ventanas temporales `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 4 h. **Responsable sugerido:** A.

- **Objetivo y alcance:** implementar contrato interno de coincidencia con regla, grupo, ventana, severidad, explicación y máximo 20 IDs de evidencia; mantener límites de ventana configurables hasta aprobar inclusividad.
- **Archivos/componentes probables:** `backend/app/detection/models.py`, `windows.py`.
- **Dependencias:** F2-B1-T2.
- **Criterios de aceptación:** ordena por timestamp de ocurrencia UTC; evidencia acotada; un evento puede estar en múltiples coincidencias. No se elige semántica inclusiva/exclusiva sin decisión.
- **Pruebas necesarias:** límites temporales, eventos históricos, orden y truncamiento de evidencia.
- **Decisiones pendientes:** límite inclusivo/exclusivo y política de episodio.

#### F5-B1-T2 — AUTH-001 fallos repetidos `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 4 h. **Responsable sugerido:** A.

- **Objetivo y alcance:** detectar al menos 5 fallos del mismo `username_key` e IP en 5 minutos; hacer idempotente el replay de la misma coincidencia.
- **Archivos/componentes probables:** `backend/app/detection/rules/auth_001.py`.
- **Dependencias:** F5-B1-T1.
- **Criterios de aceptación:** umbral/ventana/severidad `high` del SRS; fallos solamente; replay exacto idempotente; descripción informa patrón, umbral e intervalo.
- **Pruebas necesarias:** debajo/en/sobre umbral, eventos históricos/desordenados, replay; límite temporal después de decidir su semántica.
- **Decisiones pendientes:** límite inclusivo/exclusivo y relación entre coincidencias ampliadas.

#### F5-B1-T3 — AUTH-002 una IP prueba varias cuentas `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 4 h. **Responsable sugerido:** B.

- **Objetivo y alcance:** detectar fallos desde una IP contra al menos 5 `username_key` distintos dentro de 10 minutos.
- **Archivos/componentes probables:** `backend/app/detection/rules/auth_002.py`.
- **Dependencias:** F5-B1-T1.
- **Criterios de aceptación:** severidad `high`; cuentas normalizadas distintas, no número bruto de eventos; replay exacto idempotente; explicación y evidencia acotada.
- **Pruebas necesarias:** cuatro/cinco cuentas distintas, repetición de una cuenta, replay; límite temporal tras decidir inclusividad.
- **Decisiones pendientes:** política de episodios ampliados y límites temporales exactos.

#### F5-B1-T4 — AUTH-003 éxito después de fallos `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 4 h. **Responsable sugerido:** B.

- **Objetivo y alcance:** detectar cinco fallos del mismo usuario normalizado e IP dentro de cinco minutos seguidos de un evento success de esa combinación.
- **Archivos/componentes probables:** `backend/app/detection/rules/auth_003.py`.
- **Dependencias:** F5-B1-T1.
- **Criterios de aceptación:** severidad `medium`; éxito después de al menos cinco fallos en cinco minutos para la misma combinación; alerta no afirma compromiso; evidencia relaciona fallos y éxito.
- **Pruebas necesarias:** menos de cinco fallos, fallo en otra IP/usuario, éxito previo, orden histórico, límite temporal y reintento.
- **Decisiones pendientes:** inclusividad del límite; no se agrega ventana posterior nueva para el éxito.

#### F5-B1-T5 — AUTH-004 horario de referencia `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 3 h. **Responsable sugerido:** B.

- **Objetivo y alcance:** evaluar eventos respecto a horario configurable en zona `America/Bogota`, manteniendo la regla desactivada sin configuración válida.
- **Archivos/componentes probables:** `backend/app/detection/rules/auth_004.py`, `backend/app/core/config.py`.
- **Dependencias:** F5-B1-T1.
- **Criterios de aceptación:** no inventa horario predeterminado; la configuración válida controla activación; conserva timestamp UTC y explica hora local/zona; severidad coincide con configuración aprobada.
- **Pruebas necesarias:** regla apagada por defecto, conversión de zona, límites del horario y evento fuera de horario.
- **Decisiones pendientes:** horario y severidad `low` o `medium`; bloquea habilitar AUTH-004, no su implementación apagada.

### F5-B2. Detección y persistencia de alertas

#### F5-B2-T1 — Ejecutor determinista de reglas `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 4 h. **Responsable sugerido:** A.

- **Objetivo y alcance:** invocar las cuatro reglas en orden estable sobre eventos de la ejecución o conjunto consultado.
- **Archivos/componentes probables:** `backend/app/detection/engine.py`.
- **Dependencias:** F5-B1-T2 a F5-B1-T5.
- **Criterios de aceptación:** Angular no ejecuta detección; resultados repetibles para los mismos eventos/configuración; una coincidencia por regla no impide otras reglas sobre los mismos eventos.
- **Pruebas necesarias:** conjuntos combinados con múltiples reglas y orden de entrada alterado.
- **Decisiones pendientes:** configuración de AUTH-004 para su activación.

#### F5-B2-T2 — Persistencia y deduplicación de alertas `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 5 h. **Responsable sugerido:** A.

- **Objetivo y alcance:** persistir coincidencias en `Alerts` con replay exacto idempotente; no fusionar coincidencias sucesivas en episodio hasta que la regla de episodio se apruebe.
- **Archivos/componentes probables:** `backend/app/services/alert_writer.py`, `backend/app/repositories/alerts.py`.
- **Dependencias:** F5-B2-T1, F2-B2-T2.
- **Criterios de aceptación:** replay exacto no duplica alerta; máximo 20 IDs; estado inicial `open`; errores no se cuentan dos veces. La deduplicación de un mismo episodio no se marca completa hasta resolver DEC-07.
- **Pruebas necesarias:** replay idéntico, regla distinta con evidencia compartida, alerta resuelta; extensión/separación solo según política aprobada.
- **Decisiones pendientes:** DEC-07 bloquea cierre de deduplicación por episodio; DEC-01 determina si la consulta eficiente de propiedad usa GSI candidato.

## F6. Investigación, gestión de alertas y auditoría

**Objetivo:** completar el flujo de revisión de una alerta con autorización, transiciones, asignación y registro cronológico.

- **Dependencias:** creación/deduplicación de alertas, reglas de visibilidad y diseño aprobado para propietario.
- **Entregable:** analyst autorizado ve solo alertas de sus simulaciones; admin ve todas; cambios auditados.
- **Aceptación/pruebas:** lista, filtro, detalle, evidencia, historial y mutaciones comprueban propietario/rol desde FastAPI.
- **Responsable sugerido:** A servicio/API; B UI de lista y detalle en paralelo tras contrato.
- **Bloqueos:** OwnerCreatedIndex propuesto; transiciones y asignación pendientes; atomicidad de auditoría a aprobar.

### F6-B1. Consulta e investigación

#### F6-B1-T1 — Lista paginada de alertas `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 5 h. **Responsable sugerido:** A.

- **Objetivo y alcance:** listar alertas por propietario para analyst y globalmente para admin, luego aplicar filtros por estado/severidad; GSI OwnerCreatedIndex está propuesto, no aprobado.
- **Archivos/componentes probables:** `backend/app/api/alerts.py`, `backend/app/services/alert_queries.py`.
- **Dependencias:** F3-B1-T3, F2-B2-T2, F2-B2-T4.
- **Criterios de aceptación:** analyst solo ve alertas de sus simulaciones; admin ve las de todos; autorización también cubre búsquedas/filtros; página 25/100 y orden estable; no agrega índice combinado estado+severidad.
- **Pruebas necesarias:** ownership analyst, admin global, filtros, cursores, página vacía, GSIs eventualmente consistentes.
- **Decisiones pendientes:** aprobar OwnerCreatedIndex o aceptar Query por status con filtro posterior (correcto pero más costoso); no convertir índice candidato en aprobado unilateralmente.

#### F6-B1-T2 — Detalle de alerta y eventos relacionados `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 4 h. **Responsable sugerido:** B.

- **Objetivo y alcance:** consultar alerta y obtener eventos por IDs, manejando IDs faltantes y respetando autorización.
- **Archivos/componentes probables:** servicios de alerta/eventos y endpoint de detalle.
- **Dependencias:** F6-B1-T1, F4-B1-T1.
- **Criterios de aceptación:** FastAPI valida propietario antes de devolver detalle/evidencia/historial; respuesta contiene regla y explicación, hasta 20 IDs; la consulta de evidencia queda limitada a los IDs del alerta autorizado.
- **Pruebas necesarias:** evidencia completa, ID de evento faltante, acceso cruzado entre propietarios, usuario anónimo y límite de evidencia.
- **Decisiones pendientes:** ninguna.

### F6-B2. Cambios y auditoría

#### F6-B2-T1 — Transiciones de estado `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 4 h. **Responsable sugerido:** A.

- **Objetivo y alcance:** aplicar solo transiciones aprobadas entre `open`, `investigating` y `resolved` en backend y actualizar de forma segura.
- **Archivos/componentes probables:** `backend/app/services/alert_workflow.py`, endpoint de alertas.
- **Dependencias:** F6-B1-T1, F2-B2-T2.
- **Criterios de aceptación:** propietario y rol comprobados; transición no definida no se inventa; `resolved` no se reabre automáticamente; actualización condicional no pisa una versión más reciente.
- **Pruebas necesarias:** transiciones permitidas/prohibidas, concurrencia y reintento.
- **Decisiones pendientes:** matriz de transiciones y reapertura manual; bloquea mutaciones de estado, no listas/detalle.

#### F6-B2-T2 — Asignación de alerta `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 3 h. **Responsable sugerido:** B.

- **Objetivo y alcance:** realizar únicamente política de asignación confirmada; comprobar destinatario, propietario y actor en FastAPI. La política de self-assign versus asignar a otros no está definida.
- **Archivos/componentes probables:** workflow de alertas, repositorios `Users`, `Alerts`.
- **Dependencias:** F3-B2-T1, F6-B1-T1.
- **Criterios de aceptación:** propietario y rol del actor comprobados; el destinatario y la operación se validan según la política aprobada; no se implementa self/other assignment hasta resolver política; mutación repetida no duplica auditoría.
- **Pruebas necesarias:** asignación válida, ID inexistente, rol/estado no aceptable, repetición.
- **Decisiones pendientes:** analyst self-assign solamente o también puede asignar a terceros; confirmar si admin comparte o amplía ese permiso.

#### F6-B2-T3 — Auditoría de cambios de alerta `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 5 h. **Responsable sugerido:** A.

- **Objetivo y alcance:** escribir cambio de alerta y registro de auditoría con una única operación atómica aprobada, con actor/acción/UTC y valores antes/después.
- **Archivos/componentes probables:** `backend/app/services/audit.py`, repositorio de auditoría.
- **Dependencias:** F6-B2-T1, F6-B2-T2.
- **Criterios de aceptación:** mutación + AuditLogs son todo-o-nada; request id estable no aplica dos veces el cambio; reintento recupera resultado ya auditado; lecturas ordenan por `change_key`; el historial no se declara global.
- **Pruebas necesarias:** mutación+log, transacción cancelada, doble solicitud, fallos/replay, conflicto concurrente y rechazo.
- **Decisiones pendientes:** aprobar TransactWriteItems (misma región/cuenta, límites 100 acciones/4 MB) o patrón explícito de recuperación.

## F7. Simulador e historial de ejecuciones

**Objetivo:** completar la ejecución privada y recuperable que genera exactamente el número solicitado de eventos y alimenta el motor.

- **Dependencias:** autenticación, reglas y decisiones aprobadas para lease, checkpoints y clave idempotente.
- **Entregable:** solicitud privada, simulación recuperable, eventos persistidos, alertas y resultados visibles por propietario.
- **Aceptación/pruebas:** concurrencia, caída/reanudación, replay, contadores y páginas se verifican localmente.
- **Responsable sugerido:** A runner/persistencia; B UI e integración incremental.
- **Bloqueos:** lease/checkpoint/idempotencia propuestos; errores parciales aún requieren definición.

### F7-B1. Generación y validación

#### F7-B1-T1 — Generador reproducible de eventos `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 5 h. **Responsable sugerido:** B.

- **Objetivo y alcance:** generar escenarios ficticios temporalmente coherentes con IP reservadas y campos del modelo `Events`.
- **Archivos/componentes probables:** `backend/app/simulation/generator.py`, `scenarios.py`.
- **Dependencias:** F2-B1-T2, F5-B1-T1.
- **Criterios de aceptación:** cantidad exacta; IDs estables derivados de simulación/posición; `data_source=simulator`; seed explícita reproduce contenido; si no se envía, semilla efectiva se genera y persiste para recuperar el mismo contenido; escenarios respetan ventanas aprobadas.
- **Pruebas necesarias:** seed igual produce mismo contenido, seeds distintas, rangos temporales y escenarios/umbrales.
- **Decisiones pendientes:** ninguna.

#### F7-B1-T2 — Validación de solicitud y rate limits `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 4 h. **Responsable sugerido:** A.

- **Objetivo y alcance:** validar cantidad 30–300 (default 100), periodo máximo 30 días, parámetros y frecuencia en FastAPI.
- **Archivos/componentes probables:** modelos de API, `backend/app/api/simulations.py`, políticas de límites.
- **Dependencias:** F3-B1-T3.
- **Criterios de aceptación:** solicitudes inválidas se rechazan antes de crear ejecución; solo analyst/admin activos; límites también aplican a consultas del simulador.
- **Pruebas necesarias:** límites inferior/superior, valores ausentes, periodo excesivo, abuso y permisos.
- **Decisiones pendientes:** fijar umbral de rate limit del producto si no está configurado por ambiente.

### F7-B2. Ejecución recuperable e idempotente

#### F7-B2-T1 — Reserva de una ejecución por usuario `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 5 h. **Responsable sugerido:** A.

- **Objetivo y alcance:** implementar la estrategia atómica aprobada para una sola simulación activa por usuario; la recomendación actual es lease/token con vencimiento en `Users`, aún no aprobada.
- **Archivos/componentes probables:** servicio de simulación y repositorios de users/simulations.
- **Dependencias:** F2-B2-T1, F7-B1-T2.
- **Criterios de aceptación:** dos solicitudes simultáneas para el mismo usuario producen como máximo una reserva; lease vencida puede ser recuperada; token de fencing impide worker viejo liberar/modificar reserva nueva; lease no bloquea indefinidamente.
- **Pruebas necesarias:** carrera concurrente, lease válida/vencida, recuperación, worker obsoleto y release con token equivocado.
- **Decisiones pendientes:** aprobar campos de reserva/lease y protocolo, duración/renovación, frecuencia de recuperación y reglas para distinguir proceso activo abandonado.

#### F7-B2-T2 — Crear ejecución y reclamar clave idempotente `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 5 h. **Responsable sugerido:** A.

- **Objetivo y alcance:** crear registro `pending`, guardar parámetros normalizados, semilla efectiva y huella; resolver replay del cliente al mismo `simulation_id`.
- **Archivos/componentes probables:** `backend/app/services/simulation_runner.py`, repositorio `Simulations`.
- **Dependencias:** F7-B2-T1, F2-B2-T1.
- **Criterios de aceptación:** clave repetida del mismo usuario recupera la ejecución; clave nueva genera otra; misma clave con parámetros distintos se rechaza; solicitante validado server-side y queda atribuido.
- **Pruebas necesarias:** timeout antes/después de creación, mismo usuario/clave, distinto usuario/clave, parámetros alterados y nueva solicitud.
- **Decisiones pendientes:** aprobar campo/derivación de clave, fingerprint y política de retención; no confiar en ID o owner enviado por Angular.

#### F7-B2-T3 — Persistir eventos de simulación `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 6 h. **Responsable sugerido:** B.

- **Objetivo y alcance:** escribir eventos deterministas en chunks; guardar checkpoint recuperable y reconciliar parcialmente escritos sin cambiar contenido lógico ni reutilizar históricos.
- **Archivos/componentes probables:** simulador y repositorio de eventos/batch writer.
- **Dependencias:** F7-B1-T1, F7-B2-T2, F2-B2-T3.
- **Criterios de aceptación:** ejecución nueva crea cantidad exacta; replay regenera mismo payload; IDs existentes se reconcilian y contenido distinto produce error; checkpoint avanza solo tras chunk completo y con lease válida; caída reintenta el chunk sin filas duplicadas.
- **Pruebas necesarias:** `UnprocessedItems`, caída antes/después del checkpoint, payload ya persistido, recuperación de una posición intermedia y conteos.
- **Decisiones pendientes:** DEC-05: aprobar campos/protocolo de checkpoint y lease; BatchWrite no condiciona elementos, por lo que se reconcilian payloads y el cursor no avanza antes de completar el chunk.

#### F7-B2-T4 — Evaluación y contadores de simulación `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 6 h. **Responsable sugerido:** A.

- **Objetivo y alcance:** procesar por timestamp y guardar checkpoint, alertas y contadores de forma idempotente ante reintento o dos workers.
- **Archivos/componentes probables:** `backend/app/services/simulation_runner.py`, repositorio `Simulations`.
- **Dependencias:** F5-B2-T2, F7-B2-T3.
- **Criterios de aceptación:** distingue solicitados/generados/procesados; contador no incrementa doble tras crash; alertas existentes se recuperan/deduplican; worker con lease obsoleta no avanza checkpoint; estados acordados.
- **Pruebas necesarias:** caída entre alerta y cursor, reintento, dos workers, contador reconstruido y error parcial seguro.
- **Decisiones pendientes:** DEC-05/DEC-11; estrategia atómica alert+checkpoint y criterios de `partial`/error recuperable.

#### F7-B2-T5 — Consultar estado, resultados e historial `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 4 h. **Responsable sugerido:** B.

- **Objetivo y alcance:** implementar consulta autorizada por ID, lista de ejecuciones e información de resultados.
- **Archivos/componentes probables:** API de simulaciones y servicio de consulta.
- **Dependencias:** F3-B1-T3, F2-B2-T1, F2-B2-T4, F7-B2-T2.
- **Criterios de aceptación:** analyst solo ve sus ejecuciones; admin puede ver todas; la autorización aplica a estado, resumen, eventos y alertas; índices y cursores respetan el orden global.
- **Pruebas necesarias:** ownership analyst, admin multiestado, acceso cruzado, anónimo, varias páginas y GSI eventualmente consistente.
- **Decisiones pendientes:** DEC-01 para `RequesterRequestedIndex`; tolerar consistencia eventual y recuperar detalle por PK conocida cuando sea posible.

## F8. Angular, flujos integrados, documentación y AWS

**Objetivo:** hacer operables los flujos completos desde la interfaz, verificarlos contra FastAPI y preparar despliegue seguro.

- **Dependencias:** contrato API de F2; cada componente se integra al terminar su flujo backend, no al final del proyecto.
- **Entregable:** aplicación integrada, suite de aceptación local, guía operativa y despliegue mínimo aprobado en AWS.
- **Aceptación/pruebas:** flujo login → eventos → simulación → alerta → auditoría validado; smoke tests de AWS.
- **Responsable sugerido:** B frontend/docs; A backend/AWS; validación compartida.
- **Bloqueos:** AUTH-004 activa solo con horario; decisiones de identidad/propiedad bloquean acciones relacionadas; configuración AWS bloquea solo despliegue real.

### F8-B1. Interfaz privada

#### F8-B1-T1 — Estructura Angular y cliente API `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 3 h. **Responsable sugerido:** B.

- **Objetivo y alcance:** preparar rutas, entorno de API, interceptores y manejo común de respuestas/errores sin secretos de servidor.
- **Archivos/componentes probables:** `frontend/src/app/`, configuración de ambientes.
- **Dependencias:** F2-B3-T1; construir shell/cliente y conectar cada flujo cuando su contrato esté aprobado.
- **Criterios de aceptación:** frontend solo contiene configuración pública de cliente; llamadas privadas adjuntan mecanismo de autenticación aprobado; no accede a DynamoDB.
- **Pruebas necesarias:** pruebas de cliente HTTP, interceptor y configuración sin secretos.
- **Decisiones pendientes:** DEC-03 bloquea autenticación en interceptor, no shell público.

#### F8-B1-T2 — Login y dashboard protegido `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 5 h. **Responsable sugerido:** B.

- **Objetivo y alcance:** implementar formulario de acceso, expiración/salida y protección visual de rutas privadas.
- **Archivos/componentes probables:** componentes Angular `auth`, `dashboard`, guards.
- **Dependencias:** F8-B1-T1, F3-B1-T2.
- **Criterios de aceptación:** visitante ve login; sesión válida permite dashboard; salida o expiración vuelve a pantalla pública; guard no sustituye autorización backend.
- **Pruebas necesarias:** formularios, estados de sesión, navegación directa y errores de login.
- **Decisiones pendientes:** DEC-03.

#### F8-B1-T3 — Consulta de eventos `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 5 h. **Responsable sugerido:** B.

- **Objetivo y alcance:** filtros por periodo/IP/usuario, tabla paginada y navegación por cursor.
- **Archivos/componentes probables:** componentes Angular `events`.
- **Dependencias:** F4-B1-T1 a F4-B1-T3, F8-B1-T1.
- **Criterios de aceptación:** conserva filtros entre páginas, respeta respuesta ordenada, muestra estados de carga/error/vacío y no fabrica cursores.
- **Pruebas necesarias:** integración API simulada para filtros, cursores, error y página final.
- **Decisiones pendientes:** DEC-02; visibilidad de eventos no definida.

#### F8-B1-T4 — Alertas, evidencia y auditoría `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 6 h. **Responsable sugerido:** B.

- **Objetivo y alcance:** listar alertas, abrir evidencia, asignar, cambiar estado y consultar historial.
- **Archivos/componentes probables:** componentes Angular `alerts`, `audit`.
- **Dependencias:** F6-B1-T1, F6-B1-T2, F6-B2-T1 a F6-B2-T3.
- **Criterios de aceptación:** muestra estados/severidades válidos; ofrece acciones según rol; errores de autorización/transición son visibles; backend sigue siendo autoridad.
- **Pruebas necesarias:** flujos de investigación, asignación, resolución, auditoría y permisos.
- **Decisiones pendientes:** DEC-01 para índice de propietario; DEC-09 para transiciones y asignación.

#### F8-B1-T5 — Simulador e historial en dashboard `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 6 h. **Responsable sugerido:** B.

- **Objetivo y alcance:** formulario de parámetros, envío de clave de idempotencia, estado/resultados e historial según rol.
- **Archivos/componentes probables:** componentes Angular `simulations`.
- **Dependencias:** F7-B1-T1 a F7-B2-T5, F8-B1-T1.
- **Criterios de aceptación:** valida para UX pero el servidor revalida; analyst ve solo ejecuciones propias; admin ve todas; muestra parcial/fallo sin secretos; repetir una solicitud conserva clave, iniciar una nueva genera otra.
- **Pruebas necesarias:** límites, rol, replay, nueva ejecución y visualización parcial.
- **Decisiones pendientes:** DEC-04/05/06/11 para lease, recuperación, clave y estados parciales.

### F8-B2. Validación integrada y operación

#### F8-B2-T1 — Pruebas de aceptación de extremo a extremo `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 10 h. **Responsable sugerido:** Compartido.

- **Objetivo y alcance:** validar el recorrido login → simulación → eventos/detección → alerta → asignación/estado → auditoría y consultas.
- **Archivos/componentes probables:** `backend/tests/`, `frontend/`, configuración CI.
- **Dependencias:** integrar por separado login, eventos, alertas y simulaciones a medida que F3–F7/F8-B1 terminan; suite conjunta al final.
- **Criterios de aceptación:** criterios de aceptación del SRS se enlazan a pruebas reproducibles; ninguna prueba depende de AWS real para escenarios locales.
- **Pruebas necesarias:** suite API + Angular con DynamoDB Local; matriz de permisos, reglas, errores y paginación.
- **Decisiones pendientes:** ninguna.

#### F8-B2-T2 — Documentación de desarrollo y operación `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 3 h. **Responsable sugerido:** B.

- **Objetivo y alcance:** documentar arquitectura implementada, configuración local, comandos, contratos, decisiones y resolución de fallos.
- **Archivos/componentes probables:** `README.md`, `docs/arquitectura.md`, `docs/`.
- **Dependencias:** F1–F8-B2-T1.
- **Criterios de aceptación:** una persona nueva puede levantar el entorno y seguir el flujo de aceptación; diagramas coinciden con componentes reales; no hay secretos.
- **Pruebas necesarias:** seguir la guía desde entorno limpio y verificar enlaces/comandos.
- **Decisiones pendientes:** ninguna.

#### F8-B2-T3 — Preparar despliegue AWS `[MUST]`

- [ ] **Pendiente**

- **Estimación inicial (con verificación):** 6 h. **Responsable sugerido:** Compartido.

- **Objetivo y alcance:** desplegar configuración mínima aprobada de DynamoDB y aplicación con permisos mínimos; método/hosting tras decisión.
- **Archivos/componentes probables:** `infra/aws/` y configuración mínima de despliegue (estructura por confirmar; no asumir IaC/CI/CD específicos).
- **Dependencias:** F1-B2-T6, F2-B1-T1, F8-B2-T1.
- **Criterios de aceptación:** no se versionan secretos; permisos IAM mínimos documentados; configuración de producción separada de local; health check y flujo protegido funcionan en entorno acordado.
- **Pruebas necesarias:** validación estática de infraestructura, despliegue a entorno acordado, smoke tests y verificación de logs/respuestas sin secretos.
- **Decisiones pendientes:** cuenta/región AWS, hosting, gestor de secretos, TLS y proceso de publicación; bloquean despliegue real. No se incluye CI/CD como requisito.

## Decisiones, propuestas y bloqueos

Las casillas de tarea rastrean implementación. Los identificadores `DEC-*` rastrean aprobaciones; no son decisiones ya tomadas. Responsable de aprobación no identificado en los documentos: se propone el owner de producto/arquitectura TraceHunt. Los plazos D1–D9 son relativos al inicio del cronograma y no equivalen a fechas acordadas.

| ID / tipo | Pregunta y documentos | Impacto y tareas bloqueadas | Riesgo de decidir mal | Recomendación (no aprobada) | Quién / límite |
|---|---|---|---|---|---|
| DEC-01 — diseño técnico | ¿Aprobar `UserIdIndex`, `RequesterRequestedIndex`, `OwnerCreatedIndex` con `ALL`? Diseño §6–7, Workplan F1. | Creación física y consultas por ID/solicitante/owner; F1-B2-T1/T3/T5/T6, F2-B2-T1, F6-B1-T1. | Sin índices, filtro por propietario/ID puede requerir Scan o leer grandes páginas y filtrar, con latencia/coste; aprobar índices innecesarios añade costo de escritura. | Aprobar solo los tres patrones justificados; `OwnerCreatedIndex` soporta alertas por propietario. Los tres siguen candidatos hasta decisión. | Owner producto/arquitectura; D1, antes de crear tablas. |
| DEC-02 — negocio | ¿Los eventos son visibles globalmente para analyst o restringidos a sus simulaciones? SRS §9; Diseño AP-05–08; Workplan F4. | Autoriza lista/búsqueda por fecha/IP/usuario; F4 y UI de eventos. | Extender propiedad sin decisión puede ocultar datos requeridos; no limitar podría exponer datos si se esperaba aislamiento. | Mantener decisión abierta. Si restringir, replantear claves/GSI de Events con owner; no aplicar el filtro solo en UI. | Owner producto/seguridad; D1 antes de contrato de eventos. |
| DEC-03 — negocio/seguridad | ¿Qué mecanismo de sesión/token, expiración, revocación, hash y rate limits usar? SRS RF-01–04, RNF-01/02/09; Workplan F3. | Bloquea login privado y Angular autenticado: F3-B1-T1/T2/T3, F8-B1-T1/T2. | Debilidad de credenciales/sesión o credenciales expuestas. | Elegir mecanismo ya soportado por el stack y no añadir proveedor externo; secretos solo backend/entorno. | Owner seguridad/arquitectura; D1 antes del endpoint login. |
| DEC-04 — diseño técnico | ¿Aprobar exclusión por lease/token en `Users` o elegir lock alternativo? Diseño §6.1/6.5/11; SRS RNF-15. | Cambios de atributos y reserva/recovery; F1 tablas, F7-B2-T1/T4. | Check-then-write permite carreras; lease vencida mal manejada permite bloqueo indefinido o worker viejo que altera ejecución nueva. | Recomiendo reserva condicional atómica con ID+token+vencimiento; takeover condicional y cada checkpoint cercado por token. TTL no basta; no añadir sexta tabla sin justificar. | Owner arquitectura; D1 antes de simulaciones concurrentes. |
| DEC-05 — diseño técnico | ¿Aprobar checkpoints, semilla efectiva y recuperación? Diseño §6.5/9; SRS RF-19/20/24/25; Workplan F7. | Campos/protocolo de recuperación; F7-B2-T2/T3/T4. | IDs deterministas solos no conservan payload ni progreso; reintentos pueden perder eventos o duplicar contadores/alertas. | Semilla persistida, fingerprint y cursores; `BatchWriteItem` <=25, reintentar elementos no procesados, reconciliar IDs/payload, avanzar cursor solo tras chunk completo. Checkpoints/counters de detección no aditivos a ciegas; transacción para alerta+cursor cuando aplique (100 acciones/4 MB). | Owner arquitectura; D2 antes de runner. |
| DEC-06 — API/técnica | ¿Formato/alcance de Idempotency-Key y mapping a `simulation_id`; cuánto se conserva? SRS RF-19/25; Diseño §6.5/9.2. | Contrato cliente y replay; F2-B3-T1, F7-B2-T2, F8-B1-T5. | Clave reusable con parámetros distintos o no recuperable tras timeout. | Clave aleatoria por usuario+solicitud; mapping determinista a PK y fingerprint de parámetros; respuesta 409 ante reuso con parámetros distintos. | Owner producto/arquitectura; D2 antes de contrato simulator. |
| DEC-07 — negocio | ¿Cómo empiezan/terminan episodios, se amplían alertas, qué límites temporales son inclusivos y qué pasa con nuevos eventos tras `resolved`? SRS §6–8; Diseño §6.3/8. | Alert IDs/deduplicación de coincidencias ampliadas y actualizaciones; F5-B1-T1/T2–T5, F5-B2-T2, F7-B2-T4. | Duplicados o supresión de detecciones distintas; episodio reabierto o duplicado tras resolver. | Implementar primero replay exacto idempotente por coincidencia completa; dejar merge/episode boundary bloqueado hasta acuerdo. `resolved` no se reabre automáticamente ya confirmado. | Owner producto/seguridad; D3 antes de terminar alert writer. |
| DEC-08 — negocio | ¿Horario de referencia y severidad de AUTH-004? SRS §6; Diseño §8. | Regla permanece apagada; F5-B1-T5, habilitación en F5-B2-T1. | Horario arbitrario produce alertas incorrectas. | Conservar `America/Bogota`; configurar horario explícito y aprobar `low` o `medium`; no generar alertas hasta entonces. | Owner producto; D4 para incluir activación. |
| DEC-09 — negocio | ¿Transiciones válidas, reapertura manual y quién puede asignar a quién/cambiar estado? SRS §3/8/14; Diseño Alerts/AuditLogs. | Bloquea mutaciones, no lectura: F6-B2-T1/T2/T3, F8-B1-T4. | Cambios no autorizados, alertas en estado inválido o historial incorrecto. | No inferir transición completa desde nombres de estado; mantener resolved sin reapertura automática. Definir analyst self-assign vs asignación a tercero/admin. | Owner producto/seguridad; D4 antes de gestión. |
| DEC-10 — diseño técnico | ¿Cómo garantizar atomicidad de mutación + AuditLogs? Diseño §6.4; SRS RF-16. | Esquema/protocolo de auditoría y reintentos; F6-B2-T3. | Estado sin log o log de un cambio que no ocurrió. | `TransactWriteItems` con condición sobre estado/`updated_at`, put de log por `change_id` estable; revisar región/cuenta y límites. `BatchWriteItem` no es transaccional. | Owner arquitectura; D4 antes de mutaciones. |
| DEC-11 — negocio/técnica | ¿Qué criterios definen `partial`, recuperación y errores visibles? SRS RF-20/§11; Diseño §6.5/11. | Estado terminal, release de lease y UI; F7-B2-T1/T3/T4/T5, F8-B1-T5. | Éxito reportado con datos faltantes o usuario bloqueado sin recuperación. | Estado se deriva de progreso persistido; errores visibles sin secretos; separar recuperación automática de `failed` definitivo. | Owner producto/arquitectura; D5 antes de cerrar simulador. |
| DEC-12 — técnica | ¿Cómo firmar el cursor opaco y mantener merge estable multi-partición? SRS §9/12; Diseño §7.1/AP-06/AP-24/AP-25. | Paginación de consultas multi-día, estados y propietarios; F2-B2-T4, F4-B1-T1, F6-B1-T1, F7-B2-T5. | Cursor alterable, elementos omitidos/repetidos o reordenados entre páginas. | Codificar consultas/LEK/buffer y filtros; firma autenticada; continuar hasta completar página global. | Owner arquitectura; D2 antes de endpoints paginados. |
| DEC-13 — técnica/operación | ¿Cuenta/región/hosting, IAM, secretos, TLS y método de publicación AWS? Diseño §10/11; SRS RNF-14. | Bloquea únicamente despliegue real, no local; F8-B2-T3. | Despliegue con privilegios excesivos o sin configuración segura. | Despliegue manual mínimo si cabe; no asumir CI/CD ni proveedor de hosting. | Owner infraestructura; D7 para reservar smoke tests. |

### Decisiones confirmadas conservadas

- MVP exige las cuatro reglas; AUTH-004 se mantiene apagada mientras no tenga horario válido en `America/Bogota` y severidad aprobada.
- Simulador privado, analyst/admin activos, 30–300 eventos (default 100), periodo <=30 días, seed opcional, una ejecución activa por usuario.
- Reintentar una ejecución conserva ID y contenido lógico; nueva solicitud genera ejecución y eventos nuevos.
- Analyst ve solo alertas de simulaciones propias; admin ve todas. Esta regla no se extiende a eventos hasta DEC-02.
- Paginación 25/100; evidencia hasta 20 IDs; timestamps UTC; FastAPI valida entradas y permisos.
- Cinco tablas originales se conservan. Índices y atributos candidatos no se consideran aprobados hasta revisión del diseño.

## Criterio de cierre del MVP

El MVP se considera listo únicamente cuando los flujos de aceptación del SRS pasan en entorno local y el despliegue AWS acordado supera sus smoke tests. La existencia de tareas o archivos no equivale a implementación verificada. No se incluyen como parte del MVP ML, fuentes reales/SIEM, editor de reglas ni auditoría global.
