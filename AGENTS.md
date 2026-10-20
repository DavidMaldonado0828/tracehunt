# Guía de trabajo para TraceHunt

## A. Fuentes de verdad

- `docs/01-srs/TraceHunt_SRS.md` define los requisitos funcionales, no funcionales y las reglas de negocio.
- `docs/03-database/TraceHunt_Database_Design.md` define el esquema DynamoDB aprobado y sus patrones de acceso.
- `docs/02-workplans/workplan.md` define las tareas, dependencias y criterios de aceptación.
- Este archivo define cómo trabajar. No cambia requisitos ni aprueba decisiones pendientes.
- Si hay contradicción entre fuentes, detén la tarea afectada, documenta el conflicto y solicita resolución; no elijas silenciosamente.

## B. Flujo de trabajo

- Trabaja en una tarea verificable del Workplan a la vez.
- Antes de editar, revisa sus dependencias y criterios de aceptación.
- Implementa únicamente el alcance de la tarea seleccionada.
- Ejecuta las pruebas pertinentes y revisa los cambios.
- Al informar, enumera archivos modificados, pruebas ejecutadas y resultados, y bloqueos que sigan vigentes.
- Marca una tarea `- [x]` únicamente después de implementar su alcance y verificar sus criterios de aceptación y pruebas. Crear archivos o escribir código no basta.
- No marques tareas dependientes como completadas por adelantado.

## C. Arquitectura y calidad

- Conserva la separación entre endpoints, servicios, esquemas y repositorios.
- No pongas lógica de negocio en los routers.
- Usa FastAPI y Pydantic v2.
- Mantén tipado explícito, funciones pequeñas y nombres claros.
- Evita abstracciones, refactorizaciones y dependencias innecesarias.
- Valida los datos en el servidor.
- No ocultes errores con bloques `except` genéricos que impidan identificar fallos.

## D. DynamoDB

- No inventes claves, índices secundarios, atributos ni patrones de acceso.
- No uses `Scan` para resolver consultas habituales que tengan un patrón de acceso definido.
- Distingue las escrituras por lotes de las transacciones atómicas.
- Diseña operaciones idempotentes cuando lo exijan los requisitos.
- Trata explícitamente la consistencia eventual de los índices secundarios globales.
- No modifiques el diseño aprobado sin documentar y aprobar el cambio correspondiente.

## E. Seguridad

- No guardes secretos, credenciales ni claves reales en el repositorio.
- No expongas secretos en respuestas, mensajes de error o logs.
- Aplica autenticación, autorización por rol y comprobación de propiedad en el backend.
- Ocultar un botón o una pantalla no constituye autorización.
- No inventes una estrategia de autenticación mientras siga pendiente de aprobación.

## F. Pruebas

- Añade pruebas proporcionales a cada funcionalidad.
- Separa las pruebas unitarias, de integración y de API.
- Prueba casos negativos, permisos e idempotencia cuando corresponda.
- No afirmes que una prueba pasó si no se ejecutó.
- Si no es posible ejecutar una prueba, explica por qué y qué queda sin verificar.

## G. Gestión del alcance

- Conserva las funcionalidades del MVP y sus cuatro reglas de detección.
- No elimines requisitos para compensar la diferencia entre las 197 horas estimadas y las 144 horas disponibles.
- Prioriza flujos funcionales completos según el Workplan.
- No implementes frontend Angular fuera de las tareas que lo contemplan.
- No despliegues en AWS ni modifiques recursos remotos sin una tarea y autorización explícitas.
- No modifiques documentos fuente o contratos sin identificar el motivo y el impacto.

## H. Decisiones pendientes

El Workplan vigente registra decisiones pendientes. Antes de implementar una tarea afectada, comprueba los documentos actualizados; no consideres pendiente una decisión que ya tenga resolución explícita y coherente. Entre las decisiones actualmente abiertas están:

- Visibilidad de eventos por propietario (DEC-02).
- Autenticación, estrategia de sesión o token, expiración, revocación, hash y límites de intentos (DEC-03).
- Política de episodios, límites temporales y deduplicación de coincidencias ampliadas (DEC-07).
- Transiciones de estado y permisos de asignación de alertas (DEC-09).
- Reserva, lease y recuperación de simulaciones (DEC-04, DEC-05 y DEC-11).
- Clave de idempotencia y recuperación de ejecuciones (DEC-05 y DEC-06).
- Atomicidad y recuperación de auditoría (DEC-10).
- Aprobación de índices secundarios propuestos (DEC-01).
- Horario y severidad para activar AUTH-004 (DEC-08).
- Firma y continuidad del cursor de paginación (DEC-12).
- Cuenta, región, IAM, secretos, TLS y método de despliegue AWS (DEC-13).

La elección de la biblioteca cliente de DynamoDB y los parámetros de reintentos también deben documentarse en sus tareas del Workplan antes de que afecten a la implementación.



## IMPORTANTE

No realices ningún git commit, git push, merge ni publicación de cambios. Trabaja únicamente en el repositorio local, conserva todos los cambios existentes y no sobrescribas ni reviertas modificaciones ajenas a esta tarea. Al terminar, muestra los archivos creados o modificados y el resultado de las pruebas, dejando todos los cambios pendientes para que yo los revise y decida cuándo confirmarlos.