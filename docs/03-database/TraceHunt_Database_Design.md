# TraceHunt — Diseño de base de datos

**Documento:** Diseño físico de DynamoDB y patrones de acceso (*Access Patterns*)  
**Versión:** 0.3 — consolidación del modelo y patrones de acceso del MVP
**Fecha:** 2026-10-20
**Estado:** Diseño base actualizado para el MVP; los GSIs/campos marcados como propuestos requieren aprobación de la sección 11.

---

## 1. Propósito

Este documento describe el diseño inicial de la base de datos de **TraceHunt**, un MVP de detección defensiva de eventos de seguridad. Define las tablas de Amazon DynamoDB, sus claves, atributos principales, índices secundarios globales (GSI) y los patrones de acceso que el backend debe soportar.

La intención es validar el modelo de datos y las consultas principales **antes de crear las tablas y desarrollar los endpoints de FastAPI**. El diseño se basa en las necesidades conocidas del MVP y podrá evolucionar cuando las consultas reales y el volumen de datos estén mejor definidos.

## 2. Contexto del sistema

TraceHunt recibirá eventos de autenticación simulados, los almacenará y ejecutará reglas deterministas para identificar patrones sospechosos. Algunas coincidencias producirán alertas que podrán ser investigadas y gestionadas por analistas o administradores.

Componentes principales:

- **Frontend:** Angular.
- **Backend:** Python con FastAPI.
- **Base de datos:** DynamoDB.
- **Entorno de desarrollo local:** DynamoDB Local ejecutado en Docker.
- **Despliegue previsto:** AWS, por configurar más adelante.

En el MVP, las reglas de detección estarán definidas en el backend; no habrá un editor de reglas en la interfaz.

### 2.1 Responsabilidades por componente

- **FastAPI:** autoridad para toda la lógica de negocio y seguridad: autenticación, autorización, validaciones definitivas, simulación y persistencia de eventos, evaluación de reglas, creación y actualización de alertas, control de estados, idempotencia y operaciones de auditoría.
- **Angular:** capa de presentación y cliente de la API. Gestiona navegación, formularios, tablas, filtros visuales, dashboard y representación de resultados. Puede validar campos para mejorar la experiencia, pero esas validaciones no sustituyen las de FastAPI.
- **DynamoDB:** persistencia de los datos según las claves e índices definidos aquí; no sustituye las validaciones ni las decisiones de negocio del backend.

Toda operación protegida debe autorizarse en FastAPI, incluso cuando Angular oculte controles según el rol. El endpoint de inicio de sesión es público; el simulador y sus operaciones son privados.

## 3. Principios de diseño

1. **Diseñar desde las consultas.** Las claves e índices se eligen según los patrones de acceso definidos en este documento.
2. **Evitar `Scan` en consultas frecuentes.** El inicio de sesión y la búsqueda habitual de eventos o alertas deben utilizar claves o índices. Un `Scan` podría aceptarse para una lista administrativa pequeña en el MVP, pero no es la opción preferida para consultas frecuentes.
3. **Separar ocurrencia e ingestión.** `timestamp` representa cuándo ocurrió el evento; `ingested_at`, cuándo se guardó en TraceHunt.
4. **Usar UTC.** Las marcas de tiempo se almacenan como cadenas ISO 8601 en UTC, idealmente con sufijo `Z`.
5. **Normalizar los valores usados para buscar.** Por ejemplo, `username_key` evita que diferencias de mayúsculas o espacios creen agrupaciones inconsistentes.
6. **Mantener el historial.** Los eventos de simulación permanecen almacenados al finalizar la ejecución para permitir análisis históricos.
7. **Limitar los datos embebidos.** Las alertas guardan una lista acotada de identificadores de eventos relacionados, no copias completas de los eventos.
8. **Registrar cambios relevantes.** Las acciones de gestión de alertas generan registros en `AuditLogs`.
9. **Aplicar autorización en el backend.** Ocultar controles en Angular no sustituye la validación de permisos en FastAPI.
10. **Diseñar reintentos de forma idempotente.** Los reintentos no deben crear eventos ni alertas duplicados.

## 4. Convenciones de datos

### 4.1 Identificadores

- `user_id`: identificador interno del usuario.
- `event_id`: identificador único de un evento.
- `alert_id`: identificador único de una alerta.
- `simulation_id`: identificador de una ejecución del simulador.
- `change_id`: identificador único de un cambio de auditoría.
- `requested_by_user_id`: identificador estable del usuario autenticado que solicitó una ejecución.

Los identificadores de eventos simulados deben ser reproducibles dentro de una ejecución, por ejemplo: `SIM-<simulation_id>-EVT-000001`.

### 4.2 Marcas de tiempo

Los atributos de tiempo se almacenarán como cadenas ISO 8601 UTC, por ejemplo `2026-10-19T19:25:00Z`.

Algunos índices necesitan ordenar por tiempo y evitar colisiones cuando varios elementos comparten la misma marca temporal. Para ello se usarán claves compuestas por concatenación:

- `timestamp_event = <timestamp>#<event_id>`
- `created_at_alert = <created_at>#<alert_id>`
- `requested_at_sim = <requested_at>#<simulation_id>`
- `change_key = <changed_at>#<change_id>`

Las cadenas de tiempo deben usar un formato uniforme para que el orden lexicográfico coincida con el orden cronológico.

### 4.3 Valores controlados

- Rol de usuario: `admin`, `analyst`.
- Estado de usuario: `active`, `disabled`.
- Resultado de autenticación: `success`, `failure`.
- Severidad de alerta: `high`, `medium`, `low`.
- Estado de alerta: `open`, `investigating`, `resolved`.
- Estado de simulación: `pending`, `running`, `completed`, `partial`, `failed`.
- Origen de datos inicial: `simulator`.

Estos valores deben validarse en FastAPI. Los nombres son valores de aplicación, no restricciones automáticas de DynamoDB.

## 5. Resumen de tablas

| Tabla | Clave primaria | Uso principal |
|---|---|---|
| `Users` | PK `email_normalized`; GSI propuesto `UserIdIndex` | Autenticación, asignaciones y administración de cuentas |
| `Events` | PK `event_id` | Eventos de autenticación y consultas por fecha, IP o usuario |
| `Alerts` | PK `alert_id`; GSIs `StatusCreatedIndex`, `SeverityCreatedIndex`; GSI propuesto `OwnerCreatedIndex` | Alertas generadas por reglas y filtradas por estado, severidad y propietario |
| `AuditLogs` | PK `alert_id`, SK `change_key` | Historial cronológico de cambios por alerta |
| `Simulations` | PK `simulation_id`; GSI `StatusRequestedIndex`; GSI propuesto `RequesterRequestedIndex` | Estado, parámetros y resumen de cada ejecución del simulador |

En este diseño se mantienen cinco tablas independientes. Las reglas de detección no tienen tabla propia en el MVP porque estarán definidas en el código del backend.

---

## 6. Diseño de tablas

### 6.1 `Users`

**Propósito:** almacenar las cuentas que pueden iniciar sesión en el panel privado.

**Clave primaria**

- PK: `email_normalized` (`String`)

Se usa el correo normalizado como clave para poder buscar directamente la cuenta durante el inicio de sesión sin tener que ejecutar un `Scan`. En el MVP, el correo se considera inmutable; cambiarlo posteriormente requerirá un procedimiento explícito.

**Atributos**

| Atributo | Tipo lógico | Descripción |
|---|---|---|
| `email_normalized` | String | Correo normalizado; clave primaria |
| `user_id` | String | Identificador interno estable |
| `display_name` | String | Nombre visible |
| `password_hash` | String | Hash de contraseña; nunca guardar la contraseña en texto plano |
| `role` | String | `admin` o `analyst` |
| `status` | String | `active` o `disabled` |
| `created_at` | String | Fecha de creación UTC |
| `updated_at` | String | Última actualización UTC |
| `last_login_at` | String, opcional | Último inicio de sesión exitoso |
| `active_simulation_id` | String, propuesta | Parte de una reserva condicional de simulación; no está aprobada |
| `active_simulation_lease_token` | String, propuesta | Token de fencing que impide a un worker obsoleto liberar o modificar una reserva nueva |
| `active_simulation_lease_until` | Number, propuesta | Expiración epoch para recuperación tras caída; un proceso recuperador reclama condicionalmente la lease vencida |

**GSI propuesto, pendiente de aprobación:** `UserIdIndex`, PK `user_id` (S), proyección `ALL`. Permite validar asignaciones y resolver actores/solicitantes por ID con `Query`, evitando `Scan` por cada operación. El ID se generaría en el servidor; DynamoDB GSI no impone unicidad.

**Notas de implementación**

- Normalizar el correo de forma consistente antes de guardarlo y consultarlo.
- Usar un algoritmo de hash de contraseñas apropiado para autenticación; no cifrado reversible ni texto plano.
- Aplicar límites de intentos y protección contra fuerza bruta en el endpoint de login.
- Verificar rol y estado de la cuenta en las operaciones protegidas.
- Listar usuarios puede requerir `Scan` en este MVP si el conjunto es pequeño. Si crece o se vuelve una consulta frecuente, diseñar un índice o mecanismo de listado específico.

### 6.2 `Events`

**Propósito:** guardar eventos de autenticación que serán consultados por el panel y analizados por el motor de detección.

**Clave primaria**

- PK: `event_id` (`String`)

**Atributos principales**

| Atributo | Tipo lógico | Descripción |
|---|---|---|
| `event_id` | String | Identificador único del evento; PK |
| `event_type` | String | Tipo de evento, inicialmente `login` |
| `timestamp` | String | Momento en que ocurrió el evento, UTC |
| `ingested_at` | String | Momento en que TraceHunt lo almacenó, UTC |
| `username` | String | Nombre de usuario tal como se presenta en el evento |
| `username_key` | String | Nombre normalizado para búsquedas; por ejemplo, `USER#carlos` |
| `source_ip` | String | Dirección IP de origen |
| `result` | String | `success` o `failure` |
| `date_bucket` | String | Día UTC del evento, por ejemplo `DATE#2026-10-19` |
| `timestamp_event` | String | `<timestamp>#<event_id>`; clave de orden de índices |
| `simulation_id` | String, opcional | Ejecución del simulador que produjo el evento |
| `data_source` | String | Origen del evento, inicialmente `simulator` |
| `scenario_type` | String, opcional | Escenario que produjo el evento simulado |

Se podrán añadir atributos no usados como claves sin modificar la definición física de la tabla, aunque los cambios de contrato deben documentarse y validarse en la aplicación.

**Índices secundarios globales (GSI)**

| Índice | Partition key | Sort key | Uso |
|---|---|---|---|
| `DateTimestampIndex` | `date_bucket` (S) | `timestamp_event` (S) | Consultar eventos de uno o varios días y ordenarlos por tiempo |
| `SourceIpTimestampIndex` | `source_ip` (S) | `timestamp_event` (S) | Consultar eventos de una IP en un intervalo temporal |
| `UsernameTimestampIndex` | `username_key` (S) | `timestamp_event` (S) | Consultar eventos de un usuario normalizado en un intervalo temporal |

**Decisión sobre intervalos de fechas:** para consultar un periodo que abarque varios días, el backend consulta cada `date_bucket` del intervalo y combina los resultados, aplicando los límites y orden requeridos. Se debe paginar cada consulta cuando DynamoDB devuelva una `LastEvaluatedKey`.

**IPs de simulación:** utilizar rangos reservados para documentación, como `192.0.2.0/24`, `198.51.100.0/24` y `203.0.113.0/24`, en lugar de presentar direcciones de usuarios reales como parte de la simulación.

### 6.3 `Alerts`

**Propósito:** representar los patrones que el motor de detección identifica y que requieren revisión.

**Clave primaria**

- PK: `alert_id` (`String`)

**Atributos**

| Atributo | Tipo lógico | Descripción |
|---|---|---|
| `alert_id` | String | Identificador único de alerta; PK |
| `rule_id` | String | Identificador estable de la regla que produjo la alerta |
| `title` | String | Título breve para el panel |
| `description` | String | Explicación del patrón detectado |
| `severity` | String | `high`, `medium` o `low` |
| `status` | String | `open`, `investigating` o `resolved` |
| `created_at` | String | Momento de creación UTC |
| `created_at_alert` | String | `<created_at>#<alert_id>`; clave de orden de índices |
| `first_event_at` | String | Momento del primer evento asociado |
| `last_event_at` | String | Momento del último evento asociado |
| `related_event_ids` | List<String> | Lista acotada de IDs de eventos relacionados |
| `simulation_id` | String, opcional | Ejecución que originó la alerta, si corresponde |
| `simulation_owner_user_id` | String | `requested_by_user_id` de la simulación de origen; propietario para autorización de alertas |
| `assigned_to` | String, opcional | `user_id` del analista asignado |
| `updated_at` | String | Última actualización UTC |

**Índices secundarios globales (GSI)**

| Índice | Partition key | Sort key | Uso |
|---|---|---|---|
| `StatusCreatedIndex` | `status` (S) | `created_at_alert` (S) | Listar alertas por estado, ordenadas por creación |
| `SeverityCreatedIndex` | `severity` (S) | `created_at_alert` (S) | Listar alertas por severidad, ordenadas por creación |
| `OwnerCreatedIndex` (propuesto) | `simulation_owner_user_id` (S) | `created_at_alert` (S) | Consultar alertas de simulaciones iniciadas por un usuario, ordenadas por creación |

**Notas de consulta y tamaño**

- Para filtrar simultáneamente por estado y severidad se puede consultar uno de los índices y aplicar un `FilterExpression` para el otro atributo. El filtro se aplica después de leer los candidatos y no necesariamente reduce la capacidad consumida.
- Si el filtro combinado se convierte en una consulta frecuente, evaluar un índice compuesto diseñado para ese patrón.
- Mantener `related_event_ids` en un máximo de 20 IDs. Para mostrar los detalles, recuperar los eventos desde `Events` por sus IDs.
- Cada alerta conserva `simulation_owner_user_id` copiado de la simulación que la originó. FastAPI valida la propiedad en listas, filtros, detalle, evidencia, historial y cambios. Analistas consultan por `OwnerCreatedIndex`; administradores usan los índices existentes y combinan páginas en orden global.
- Un replay exacto no debe crear otra alerta. La implementación necesita una identidad determinista de la coincidencia para escritura condicional. La política para combinar coincidencias ampliadas en un episodio y decidir cuándo nace uno nuevo sigue pendiente; no deducirla de una clave permanente ni de una pausa elegida arbitrariamente. Alertas resueltas no se reabren automáticamente.

### 6.4 `AuditLogs`

**Propósito:** conservar el historial de cambios de gestión de cada alerta.

**Claves**

- PK: `alert_id` (`String`)
- SK: `change_key` (`String`), con formato `<changed_at>#<change_id>`

**Atributos**

| Atributo | Tipo lógico | Descripción |
|---|---|---|
| `alert_id` | String | Alerta a la que corresponde el cambio; PK |
| `change_key` | String | Marca de tiempo más ID del cambio; SK |
| `change_id` | String | Identificador único del cambio |
| `actor_type` | String | `user` o `system` |
| `actor_id` | String | ID del usuario o identificador del componente del sistema |
| `actor_email` | String, opcional | Correo capturado como referencia histórica del actor |
| `action` | String | Acción, por ejemplo `status_changed` o `alert_assigned` |
| `previous_status` | String, opcional | Estado anterior, cuando aplique |
| `new_status` | String, opcional | Estado nuevo, cuando aplique |
| `previous_assigned_to` | String, opcional | Usuario asignado antes del cambio |
| `new_assigned_to` | String, opcional | Usuario asignado después del cambio |
| `changed_at` | String | Momento del cambio UTC |
| `comment` | String, opcional | Comentario explicativo |

**Índices secundarios:** ninguno inicialmente.

La consulta principal es recuperar todos los cambios de una alerta ordenados cronológicamente. La aplicación debe tratar estos registros como anexados y no sobrescribirlos en el flujo normal. Esto no constituye una garantía absoluta de inmutabilidad frente a alguien con acceso administrativo directo a la base de datos. Esta tabla no es, en su diseño actual, una solución de auditoría global para todas las acciones del sistema; esa ampliación queda pendiente.

### 6.5 `Simulations`

**Propósito:** registrar cada ejecución privada del simulador, su solicitante, configuración, estado y resumen. FastAPI es responsable de autorizar tanto la creación como las consultas posteriores.

**Clave primaria**

- PK: `simulation_id` (`String`)

**Atributos**

| Atributo | Tipo lógico | Descripción |
|---|---|---|
| `simulation_id` | String | Identificador de ejecución; PK |
| `status` | String | `pending`, `running`, `completed`, `partial` o `failed` |
| `requested_at` | String | Momento de solicitud UTC |
| `requested_at_sim` | String | `<requested_at>#<simulation_id>`; clave de orden del índice |
| `started_at` | String, opcional | Momento de inicio UTC |
| `finished_at` | String, opcional | Momento de finalización UTC |
| `period_start` | String | Inicio del intervalo histórico solicitado |
| `period_end` | String | Fin del intervalo histórico solicitado |
| `requested_event_count` | Number | Cantidad solicitada |
| `generated_event_count` | Number | Eventos generados |
| `processed_event_count` | Number | Eventos procesados por el motor de detección |
| `created_alert_count` | Number | Alertas creadas por la ejecución |
| `scenario_summary` | Map | Resumen por tipo de escenario |
| `requested_by_user_id` | String | `user_id` del usuario autenticado que solicitó la ejecución |
| `requested_by_email` | String, opcional | Snapshot informativo del correo del solicitante en el momento de la solicitud |
| `idempotency_key` | String, propuesta | Clave de idempotencia dentro del usuario solicitante; el `simulation_id` podría derivarse de solicitante+clave sin añadir GSI |
| `request_fingerprint` | String, propuesta | Huella de los parámetros normalizados; detecta reuso de clave con parámetros distintos |
| `last_generated_event_index` | Number, propuesta | Checkpoint del último índice de evento cuya escritura se confirmó |
| `last_processed_event_index` | Number, propuesta | Checkpoint del último índice procesado por detección y contadores |
| `worker_token` | String, propuesta | Token de propiedad del worker para cercar procesos obsoletos durante recuperación |
| `lease_expires_at` | Number, propuesta | Vencimiento epoch de la lease de ejecución para permitir recuperación tras caída |
| `seed` | Number o String, opcional | Semilla para reproducir una simulación cuando se use |
| `error_summary` | String, opcional | Resumen del error si la ejecución falla o queda parcial |

**Notas de integridad y autorización**

- `requested_by_user_id` es obligatorio para las ejecuciones iniciadas por un usuario autenticado; `requested_by_email` es opcional y sirve únicamente como snapshot histórico.
- La tabla registra la atribución de la ejecución, pero no sustituye la autorización de cada endpoint.
- Un analista consulta solo sus propias ejecuciones; un administrador puede consultar todas. `RequesterRequestedIndex` es una propuesta para listar por solicitante. Los administradores consultan `StatusRequestedIndex` para cada estado y el backend combina las páginas en orden global.
- Una simulación activa por usuario requiere exclusión mutua. `Users.active_simulation_id` y campos de lease/token son una propuesta aún no aprobada; véase la sección 11. Comprobar y después escribir sin condición no evita la carrera.
- Para recuperación se recomienda guardar parámetros normalizados, una semilla efectiva (generada y persistida si el cliente no la envía), huella de solicitud, checkpoints y lease. Los eventos se regeneran determinísticamente. Para respetar el flujo de lotes del SRS, `BatchWriteItem` procesa hasta 25 y reintenta cada `UnprocessedItem`; el checkpoint avanza condicionalmente solo después de confirmar el chunk completo. Si el proceso cae antes del checkpoint, reenvía el mismo chunk con IDs y payload idénticos; esto evita filas duplicadas por PK, aunque `BatchWriteItem` puede sobrescribir, por lo que la clave de ejecución/semilla debe permanecer estable. El fencing token condiciona cambios de estado/checkpoint; los writes viejos solo pueden repetir exactamente el mismo contenido. Alertas y contador/checkpoint de detección deben ser atómicos o derivables e idempotentes.
- La clave de idempotencia podría mapear determinísticamente solicitante+clave a `simulation_id`; guardar una huella evita aplicar la misma clave a parámetros diferentes. Esta política de API y sus atributos están pendientes de aprobación.
- `requested_event_count`, `generated_event_count` y `processed_event_count` representan fases distintas y no deben tratarse como equivalentes.
- Para recuperar eventos de una ejecución concreta sin GSI por `simulation_id`, usar IDs deterministas y `BatchGetItem` por las claves conocidas (hasta el máximo 300), dividir lotes según el límite del cliente y manejar `UnprocessedKeys`; ordenar en backend. Si el patrón de resultados por simulación necesitara navegación arbitraria mayor, reabrir el diseño de índice.

**Índice secundario global (GSI)**

| Índice | Partition key | Sort key | Uso |
|---|---|---|---|
| `StatusRequestedIndex` | `status` (S) | `requested_at_sim` (S) | Listar ejecuciones por estado, ordenadas por solicitud |
| `RequesterRequestedIndex` (propuesto) | `requested_by_user_id` (S) | `requested_at_sim` (S) | Listar ejecuciones propias de un solicitante, ordenadas por solicitud |

**Parámetros iniciales del simulador**

- Mínimo por ejecución: **30 eventos**.
- Cantidad predeterminada: **100 eventos**.
- Máximo por ejecución: **300 eventos**.
- Intervalo histórico máximo: **30 días**.
- Intervalo histórico configurable dentro del máximo permitido.
- Mezcla de escenarios con relaciones temporales coherentes.
- `seed` opcional para pruebas reproducibles.

Estos son límites de producto para el MVP, no límites propios de DynamoDB. FastAPI debe validar cantidad, intervalo temporal y demás parámetros antes de iniciar una ejecución. Cada solicitud nueva e independiente debe generar exactamente la cantidad de eventos nuevos solicitada dentro del rango permitido.

---

## 7. Access Patterns

Los *access patterns* describen qué necesita consultar o modificar la aplicación. En DynamoDB son fundamentales porque determinan las claves y los índices que conviene definir antes de crear las tablas.

| ID | Necesidad | Tabla / índice | Estrategia |
|---|---|---|---|
| AP-01 | Buscar una cuenta al iniciar sesión por correo | `Users` PK `email_normalized` | `GetItem` por correo normalizado |
| AP-02 | Consultar un usuario por ID interno | `Users.UserIdIndex` (propuesto) | `Query` por `user_id` para validar asignación y resolver actoría; alternativa: `Scan` solo si se acepta el coste/latencia en el pequeño conjunto MVP |
| AP-03 | Listar cuentas para administración | `Users` | `Scan` aceptable solo para un conjunto pequeño en el MVP; revisar si crece |
| AP-04 | Obtener un evento por ID | `Events` PK `event_id` | `GetItem` |
| AP-05 | Listar eventos de un día | `Events.DateTimestampIndex` | `Query` por `date_bucket`, ordenado por `timestamp_event` |
| AP-06 | Listar eventos en un intervalo de varios días | `Events.DateTimestampIndex` | Consultar cada día del intervalo, paginar y combinar resultados por tiempo |
| AP-07 | Consultar eventos de una IP en un intervalo | `Events.SourceIpTimestampIndex` | `Query` por `source_ip` con condición de rango en `timestamp_event` |
| AP-08 | Consultar eventos de un usuario en un intervalo | `Events.UsernameTimestampIndex` | `Query` por `username_key` con condición de rango en `timestamp_event` |
| AP-09 | Listar alertas abiertas | `Alerts.StatusCreatedIndex` | `Query` por `status = open`, ordenar por creación |
| AP-10 | Listar alertas en investigación | `Alerts.StatusCreatedIndex` | `Query` por `status = investigating` |
| AP-11 | Listar alertas resueltas | `Alerts.StatusCreatedIndex` | `Query` por `status = resolved` |
| AP-12 | Listar alertas por severidad | `Alerts.SeverityCreatedIndex` | `Query` por `severity`, ordenar por creación |
| AP-13 | Filtrar alertas por estado y severidad a la vez | `Alerts` | Consultar por uno de los índices y aplicar filtro al otro; evaluar índice compuesto si se vuelve frecuente |
| AP-14 | Obtener detalle de una alerta | `Alerts` PK `alert_id` | `GetItem` |
| AP-15 | Recuperar los eventos relacionados con una alerta | `Events` PK `event_id` | Obtener eventos por sus IDs; para varios IDs, usar lecturas por lotes y manejar elementos faltantes |
| AP-16 | Ver historial de cambios de una alerta | `AuditLogs` PK `alert_id`, SK `change_key` | `Query` por `alert_id`, orden cronológico por sort key |
| AP-17 | Obtener detalle de una simulación | `Simulations` PK `simulation_id` | `GetItem` |
| AP-18 | Listar simulaciones por estado | `Simulations.StatusRequestedIndex` | `Query` por `status`, ordenar por solicitud |
| AP-19 | Reintentar una ejecución sin duplicar eventos | `Simulations` + `Events` | Mantener identidad estable de ejecución y eventos; usar escrituras condicionales donde aplique y controlar el estado del proceso |
| AP-20 | Consultar tendencias históricas | `Events` y `Alerts` | Consultar por intervalos usando índices y agregar resultados en backend; evitar depender de un `Scan` amplio |
| AP-21 | Obtener el resumen de una simulación | `Simulations` | Leer contadores y `scenario_summary` guardados en el elemento de ejecución |
| AP-22 | Mostrar los resultados de una ejecución solicitada por un usuario autorizado | `Simulations`, `Events`, `Alerts` | Autorizar en FastAPI cada consulta; limitarla por `simulation_id` y comprobar que el solicitante tiene permiso para acceder a esos resultados |
| AP-23 | Registrar quién solicitó una ejecución | `Simulations` | Guardar `requested_by_user_id` y, opcionalmente, `requested_by_email` como snapshot informativo |
| AP-24 | Listar ejecuciones para el panel autorizado | `Simulations.RequesterRequestedIndex` (propuesto) y `StatusRequestedIndex` | Analista consulta por solicitante; admin consulta los cinco estados y fusiona resultados en orden global con cursor opaco |
| AP-25 | Listar alertas con restricción de visibilidad por actor | `Alerts.OwnerCreatedIndex` (propuesto), `StatusCreatedIndex`, `SeverityCreatedIndex` | Analista hace `Query` por su propietario; estado/severidad se aplican como filtros posteriores. Admin consulta por estado/severidad y fusiona páginas en orden global. FastAPI autoriza también detalle y mutaciones. |

### 7.1 Consultas temporales de eventos

Para consultar eventos por fecha, el backend calcula los días UTC incluidos en el intervalo. Por cada día consulta `DateTimestampIndex` usando `date_bucket` y un rango de `timestamp_event`. Los resultados se combinan y ordenan antes de devolver la respuesta.

Para consultar por IP o usuario, se usa el índice correspondiente y se limita el rango de tiempo sobre la sort key. Todas las consultas deben soportar paginación y límites máximos de resultados.

### 7.2 Consultas de alertas

Los índices permiten listar por estado o por severidad, no ambas dimensiones simultáneamente como claves. Un `FilterExpression` puede completar el filtro, pero no evita leer los elementos candidatos. La decisión de añadir un índice adicional dependerá de que el filtro combinado sea frecuente y de su coste medido.

### 7.3 Consultas históricas y agregaciones

DynamoDB no realiza automáticamente las agregaciones analíticas que el dashboard podría necesitar (por ejemplo, cantidad de eventos por día o alertas por severidad durante una semana). Para el MVP, FastAPI puede consultar los datos necesarios y agregarlos, aplicando límites y paginación. Si el volumen crece, habrá que evaluar una estrategia de agregaciones precomputadas o un servicio analítico, en lugar de recorrer todo el historial en cada carga del dashboard.

---

## 8. Reglas de detección iniciales

Las reglas viven en el backend durante el MVP. Estos ejemplos son umbrales iniciales para validar con pruebas; una coincidencia es una **señal sospechosa**, no una prueba concluyente de ataque.

| ID ilustrativo | Patrón | Severidad inicial ilustrativa |
|---|---|---|
| `AUTH-001` | 5 fallos para el mismo usuario desde la misma IP dentro de 5 minutos | `high` |
| `AUTH-002` | Fallos desde la misma IP contra 5 usuarios distintos dentro de 10 minutos | `high` |
| `AUTH-003` | 5 fallos del mismo usuario e IP en 5 minutos seguidos de éxito | `medium` |
| `AUTH-004` | Evento fuera del horario explícitamente configurado en `America/Bogota` | `low` o `medium` |

Las cuatro reglas forman parte del MVP. `AUTH-004` permanece desactivada hasta que exista una configuración válida del horario de referencia. Las reglas temporales procesan los eventos por `timestamp` (ocurrencia), incluso con datos históricos.

Los eventos que forman un patrón deben quedar dentro de la ventana temporal definida por la regla. Por eso, el generador debe producir escenarios coherentes y no elegir cada campo de forma totalmente independiente.

---

## 9. Simulador, persistencia e idempotencia

### 9.1 Flujo propuesto

1. El usuario inicia sesión mediante el mecanismo normal de autenticación.
2. Entra al dashboard privado y selecciona el simulador.
3. Angular envía los parámetros de la solicitud a FastAPI.
4. FastAPI valida el token o la sesión, comprueba que la cuenta esté activa y autoriza el rol `analyst` o `admin`. Esta comprobación se aplica a todos los endpoints del simulador, incluidas las consultas de estado y resultados.
5. FastAPI valida la cantidad de eventos (30–300, predeterminado 100), el intervalo histórico (máximo 30 días), la semilla opcional y los demás parámetros.
6. Se crea una ejecución con `simulation_id` único y estado `pending`, registrando `requested_by_user_id` y, opcionalmente, `requested_by_email`; luego pasa a `running`.
7. El backend genera exactamente la cantidad solicitada de eventos nuevos, con IDs estables derivados de la ejecución, y los persiste en `Events`.
8. El motor de detección procesa los eventos según su timestamp de ocurrencia y aplica las reglas.
9. Se guardan las alertas correspondientes y se actualizan los contadores, el resumen de escenarios y el estado de la simulación.
10. FastAPI devuelve un resumen de esa ejecución. Las consultas posteriores de estado o resultados requieren autenticación, cuenta activa y autorización.

Los eventos permanecen en la base de datos después de finalizar la simulación para poder consultar tendencias históricas.

### 9.2 Reintentos

La ejecución debe tener una identidad estable durante los reintentos. Se recomienda aceptar una clave de idempotencia para la solicitud y asociarla de forma determinista con `simulation_id`. Un reintento de una ejecución ya creada conserva ese `simulation_id`, los IDs de evento y el contenido generado; no constituye una ejecución nueva. Una nueva solicitud independiente obtiene otro `simulation_id` y otro conjunto de eventos.

- Generar IDs de evento estables a partir de la ejecución y el número de evento, por ejemplo `SIM-<simulation_id>-EVT-000001`.
- Mantener estables los datos generados cuando se reintente la misma ejecución; una `seed` puede ayudar a reproducir la generación, pero por sí sola no sustituye la persistencia o recuperación del contenido de una ejecución ya iniciada.
- No contar registros históricos existentes como parte de la cantidad solicitada para una nueva ejecución.
- Usar escrituras condicionales cuando sea necesario impedir que un elemento existente se sobrescriba por accidente.
- Deduplicar alertas por regla, agrupación y episodio detectado. No asumir que la combinación permanente de regla, usuario e IP basta para identificar todas las alertas.
- Registrar contadores y estados de forma que un reintento no incremente dos veces los resultados.
- Procesar eventos por su timestamp de ocurrencia, no suponiendo que los datos históricos son recientes.
- Los eventos relacionados con un patrón deben quedar dentro de la ventana temporal de la regla correspondiente.

**Importante:** `BatchWriteItem` permite hasta 25 operaciones por llamada y no admite condiciones individuales por elemento. Además, puede devolver elementos no procesados. Por tanto, el backend debe dividir lotes de escritura, reintentar `UnprocessedItems` hasta un límite definido con espera incremental, registrar los fallos agotados y diseñar la idempotencia explícitamente; no se debe asumir que un lote equivale a una transacción.

### 9.3 Acceso privado y autorización del simulador

- El simulador está disponible únicamente dentro del dashboard privado.
- Para iniciar una ejecución, consultar su estado, recuperar sus resultados o realizar cualquier otra operación del simulador, FastAPI debe comprobar una sesión/token válido, cuenta activa y rol `analyst` o `admin`.
- No se permite generar eventos anónimamente ni consultar resultados sin autorización.
- Ocultar o deshabilitar controles en Angular es una mejora de interfaz, no un control de seguridad suficiente.
- Aplicar límites de frecuencia, límites de cantidad de eventos y límites de intervalo temporal en FastAPI.
- Limitar las respuestas al `simulation_id` solicitado y comprobar autorización antes de devolver eventos, alertas o resúmenes.
- Mantener públicos únicamente los endpoints necesarios para el inicio de sesión y otros mecanismos de entrada que se definan expresamente.
- No incluir secretos de autenticación en Angular ni versionarlos en Git.

---

## 10. Definición física: AttributeDefinitions y creación

En las definiciones de tabla de DynamoDB, `AttributeDefinitions` debe incluir **solo los atributos que se usan como claves de la tabla o de sus índices**. No se deben declarar ahí todos los atributos normales del elemento.

Todas las claves de este diseño son cadenas (`S`), excepto los contadores de `Simulations`, que son atributos normales de tipo número (`N`) y no aparecen en `AttributeDefinitions` mientras no se utilicen como claves.

| Tabla | Clave primaria | Claves de índices que deben declararse |
|---|---|---|
| `Users` | `email_normalized` (S) | `user_id` (S) para GSI propuesto `UserIdIndex` |
| `Events` | `event_id` (S) | `date_bucket` (S), `timestamp_event` (S), `source_ip` (S), `username_key` (S) |
| `Alerts` | `alert_id` (S) | `status` (S), `created_at_alert` (S), `severity` (S), `simulation_owner_user_id` (S) para GSI propuesto |
| `AuditLogs` | `alert_id` (S) + `change_key` (S) | Ninguna |
| `Simulations` | `simulation_id` (S) | `status` (S), `requested_at_sim` (S), `requested_by_user_id` (S) para GSI propuesto |

Configuración inicial propuesta:

- Modo de capacidad: `PAY_PER_REQUEST`.
- Proyección de los GSI: `ALL` para simplificar el MVP y evitar lecturas adicionales al principio.
- Endpoint local de desarrollo: `http://localhost:8000`.
- Región de pruebas usada con AWS CLI local: `us-east-1`.

`PAY_PER_REQUEST` en la instancia local no significa que se esté pagando por capacidad de AWS. La configuración real de producción debe revisarse antes de desplegar.

### 10.1 Organización de archivos

Mantener los archivos de definición separados de la carpeta donde DynamoDB Local persiste sus datos. Por ejemplo:

```text
C:\TraceHunt\
├── docker\
│   └── dynamodb\              # Datos persistidos de DynamoDB Local
└── infra\
    └── dynamodb\              # JSON de creación de tablas y documentación
        ├── create-users.json
        ├── create-events.json
        ├── create-alerts.json
        ├── create-audit-logs.json
        └── create-simulations.json
```

Se pueden crear las tablas con archivos JSON y `aws dynamodb create-table --cli-input-json file://...`, añadiendo `--endpoint-url http://localhost:8000 --region us-east-1` para dirigir los comandos a DynamoDB Local.

Antes de ejecutar la creación, revisar cada JSON y verificar que los nombres de los índices, las claves, los tipos y las proyecciones coincidan con este documento.

---

## 11. Consideraciones y decisiones pendientes

1. **Aprobación de GSI propuestos:** `UserIdIndex`, `RequesterRequestedIndex` y `OwnerCreatedIndex` responden a patrones de acceso confirmados y evitan scans o filtro ineficiente. La recomendación es aprobarlos con proyección `ALL`; hasta decisión, son candidatos, no índices aprobados. Bloquea la creación final del esquema y repositorios que los requieren.
2. **Reserva y lease de simulación:** alternativa recomendada: actualización condicional atómica en el elemento `Users`, guardando `active_simulation_id`, token único y vencimiento; un worker solo modifica datos si el token coincide. La recuperación toma una lease vencida mediante condición y reemplaza el token; la liberación condiciona por ID+token para no borrar una reserva nueva. DynamoDB TTL no debe usarse como mecanismo de exclusión porque su borrado es eventual. Alternativa: una tabla/partición de locks aparte, que cambiaría el conjunto aprobado de cinco tablas. Decidir si se aprueba la extensión de atributos en `Users`; bloquea F7-B2-T1.
3. **Checkpoint y recuperación:** se recomienda guardar semilla efectiva, huella de parámetros, clave de idempotencia y cursores de generación/procesamiento en `Simulations`. Reintentar `UnprocessedItems` de `BatchWriteItem` hasta el límite definido; mover el checkpoint solo tras completar el chunk; tras caída, regenerar/reintentar el mismo chunk con payload idéntico. El avance del worker requiere token vigente. Alertas y contador/checkpoint de detección deben ser transaccionales o recuperables sin doble conteo; transacciones están sujetas a 100 acciones/4 MB. Estos atributos/protocolo son propuestos y bloquean la recuperación de F7 hasta aprobación.
4. **Reintento del cliente:** se recomienda derivar `simulation_id` de `requested_by_user_id` y una clave idempotente aleatoria de la solicitud, guardar huella de parámetros y rechazar la misma clave con parámetros distintos. La clave almacenada no necesita GSI si el ID se deriva; decidir formato/retención/contrato HTTP. Bloquea cierre de F7-B2-T2, no generación local.
5. **Propietario de alertas:** está confirmado que analyst ve solo alertas de sus ejecuciones y admin todas. Recomendación: persistir `simulation_owner_user_id` al crear alerta y aprobar `OwnerCreatedIndex` (`simulation_owner_user_id`, `created_at_alert`, proyección `ALL`). El backend debe validar propietario también en detalle, evidencia, historial y mutaciones. Bloquea endpoints/listados hasta aprobar índice y atributo.
6. **Visibilidad de eventos:** los documentos no confirman si el analista ve todos los eventos o solo los de sus simulaciones. Si se limita por propietario, el patrón por fecha/IP/usuario requiere añadir owner al evento y diseñar GSIs compatibles; si se permite global, los índices actuales sirven. No extender la regla de visibilidad de alertas a eventos sin decisión. Bloquea autorización de F4, no la lectura interna para el motor.
7. **Deduplicación de episodios:** se confirma que el replay exacto no duplica alertas y una alerta `resolved` no se reabre automáticamente; falta definir cuándo un episodio se amplía/termina, cuándo nace otro, los límites exactos inclusivo/exclusivo y qué hacer con eventos nuevos tras resolución. No usar una clave permanente por regla/grupo ni la pausa de una ventana sin aprobación. Bloquea deduplicación entre coincidencias distintas; la idempotencia del replay exacto puede implementarse por huella determinista de coincidencia.
8. **Atomicidad de alerta/auditoría:** recomendación: `TransactWriteItems` con actualización condicional de `Alerts` y `Put` de `AuditLogs` en una transacción; ID de cambio estable por petición, validación de estado/`updated_at`, y lectura del cambio existente al reintentar. Límite 100 acciones/4 MB. Alternativa: outbox/recuperación requeriría atributos y lógica adicional. `AuditLogs` solo cubre cambios de alertas, no auditoría global. Aprobar estrategia antes de F6-B2-T3.
9. **Estados y asignación:** están confirmados los estados y que resolved no se reabre automáticamente; la matriz de transiciones, reapertura manual, si analistas solo se asignan a sí mismos o pueden asignar a otros, y permisos precisos de estado siguen pendientes. Bloquean F6-B2-T1/T2 y UI de acciones.
10. **AUTH-004:** zona `America/Bogota` confirmada; horario de referencia y severidad `low`/`medium` pendientes. La regla permanece apagada; bloquea su activación, no el resto del motor.
11. **Autenticación y secretos:** elegir sesión/token, expiración, revocación, algoritmo de hash y protección de secretos antes de exponer panel; bloquea F3 y Angular privado.
12. **Resultados parciales y lease abandonada:** acordar los criterios visibles de `partial`/`failed`, reanudación y frecuencia de recuperación de leases vencidas; bloquea cierre de F7.
13. **Despliegue:** cuenta/región/hosting AWS, IAM mínimo, gestor de secretos y TLS pendientes; bloquean despliegue real, no desarrollo local.
14. **Otras consideraciones:** GSI son eventualmente consistentes; estado+severidad usa filtro posterior; retención conserva históricos; tendencias se agregan en backend con consultas paginadas. Auditoría global y agregaciones precomputadas quedan fuera del MVP.

## 12. Glosario breve

- **PK (Partition Key):** clave que determina la partición lógica donde se organiza el elemento.
- **SK (Sort Key):** clave opcional que ordena elementos dentro de una misma clave de partición.
- **GSI (Global Secondary Index):** índice que permite consultar los elementos usando otra combinación de claves.
- **`Query`:** operación que consulta elementos por una clave de partición y, opcionalmente, una condición sobre la sort key.
- **`Scan`:** operación que recorre una tabla o índice; puede resultar costosa a medida que crecen los datos.
- **`FilterExpression`:** filtro aplicado a los elementos leídos por una consulta; no elimina el coste de leer los candidatos.
- **Idempotencia:** propiedad por la que repetir una solicitud no produce duplicados ni efectos adicionales no deseados.
- **Access pattern:** operación de lectura o escritura que la aplicación necesita ejecutar de forma habitual.
- **DynamoDB Local:** versión de desarrollo de DynamoDB que se ejecuta localmente, por ejemplo en Docker.

---

## 13. Checklist de validación antes de crear tablas

- [ ] Los cinco nombres de tabla están acordados.
- [ ] Las claves primarias y las sort keys coinciden con este documento.
- [ ] Los nombres de los GSIs son consistentes en los archivos JSON y en el código backend.
- [ ] `AttributeDefinitions` contiene solo claves de tabla e índices.
- [ ] Todos los atributos de tiempo se generan en UTC y con formato uniforme.
- [ ] `timestamp_event`, `created_at_alert`, `requested_at_sim` y `change_key` se construyen de forma estable.
- [ ] Las consultas por intervalos implementan paginación.
- [ ] La lógica de simulación controla reintentos e IDs duplicados.
- [ ] El simulador solo está disponible en el dashboard privado y FastAPI valida sesión/token, estado de cuenta y rol `analyst` o `admin` en todos sus endpoints.
- [ ] No hay generación anónima de eventos ni consultas anónimas de resultados.
- [ ] `Simulations` registra `requested_by_user_id` y, si se configura, `requested_by_email`.
- [ ] Los límites del simulador son 30–300 eventos, con 100 por defecto y un máximo de 30 días históricos.
- [ ] Cada ejecución nueva genera eventos nuevos; los reintentos mantienen identidad, IDs y contenido sin duplicados.
- [ ] La aplicación no confía en el frontend para validar roles o permisos.
- [ ] Se probarán los access patterns principales con datos de ejemplo antes de continuar con los endpoints.

**Siguiente paso sugerido:** convertir las definiciones de las cinco tablas en archivos JSON de AWS CLI, crear primero las tablas en DynamoDB Local y verificar cada una con `describe-table` antes de comenzar la integración con FastAPI.
