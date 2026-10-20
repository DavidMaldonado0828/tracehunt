# TraceHunt --- Reglas de detección y requisitos del sistema

**Documento:** Requisitos funcionales, reglas de alertamiento y flujo de
ejecución\
**Versión:** 0.3 --- consolidación de requisitos del MVP\
**Fecha:** 2026-10-20\
**Relacionado con:** `TraceHunt_Database_Design.md`\
**Estado:** Requisitos consolidados del MVP; no implica que la implementación ya exista.

------------------------------------------------------------------------

## 1. Propósito

Este documento define qué debe hacer TraceHunt, cómo se identifican
patrones sospechosos, cuándo se crean alertas, cómo se evitan duplicados
y cuál es el recorrido de una solicitud desde Angular hasta DynamoDB.

TraceHunt es un laboratorio de **detección defensiva**. En el MVP
trabajará con eventos de autenticación simulados y reglas deterministas
implementadas en FastAPI. Las alertas indican que una regla observó un
patrón que merece revisión; **no demuestran por sí solas que ocurrió un
ataque real**.

Este documento complementa el diseño de base de datos. El diseño de
datos explica dónde se guarda la información y cómo se consulta; este
documento explica qué comportamiento debe producir el sistema.

## 2. Alcance del MVP

### Incluido

-   Inicio de sesión para cuentas de `admin` y `analyst`.
-   Autorización aplicada en el backend según rol y estado de cuenta.
-   Simulador de eventos disponible únicamente dentro del dashboard privado.
-   Generación controlada de eventos ficticios de autenticación por usuarios activos con rol `analyst` o `admin`.
-   Persistencia de eventos y del historial de ejecuciones.
-   Evaluación de reglas deterministas en el backend.
-   Creación, consulta, asignación y cambio de estado de alertas.
-   Consulta de eventos históricos por periodo, usuario e IP.
-   Historial de auditoría de acciones relevantes.
-   Los analistas solo podrán consultar alertas generadas por simulaciones que iniciaron; los administradores podrán consultar alertas de todos los analistas. El acceso se comprobará en FastAPI para listas, búsquedas, detalles, evidencia, historial y mutaciones.
-   Límites de uso, validación de parámetros y protección básica contra
    abuso.
-   Pruebas de reglas, persistencia, reintentos y permisos.

### Fuera del alcance inicial

-   IA o aprendizaje automático para clasificar eventos.
-   Ejecución de acciones ofensivas, explotación o malware.
-   Editor de reglas desde la interfaz.
-   Integración con fuentes reales de logs o SIEM externos.
-   Garantía de que una alerta representa un ataque confirmado.
-   Arquitectura distribuida compleja o procesamiento en tiempo real de
    alto volumen.
-   Administración avanzada de reglas por organización/tenant.

## 3. Actores y permisos

  -----------------------------------------------------------------------
  Actor                               Acceso esperado
  ----------------------------------- -----------------------------------
  Visitante                           Puede acceder al inicio de sesión y
                                      a las funciones públicas necesarias
                                      para autenticarse. No puede usar el
                                      dashboard, ejecutar simulaciones ni
                                      consultar resultados.

  Analista (`analyst`)                Puede consultar eventos y alertas,
                                      investigar una alerta, asignarse
                                      alertas y cambiar su estado según
                                      las reglas de autorización
                                      definidas.

  Administrador (`admin`)             Puede realizar las acciones del
                                      analista y administrar cuentas de
                                      usuario.

  Sistema (`system`)                  Genera eventos simulados, ejecuta
                                      reglas, crea alertas y escribe
                                      auditoría técnica cuando
                                      corresponde. No es una cuenta
                                      humana.
  -----------------------------------------------------------------------

La interfaz Angular puede ocultar botones según el rol para mejorar la
experiencia, pero **FastAPI debe comprobar el permiso en cada endpoint
protegido**. No se debe confiar en el rol enviado por el navegador.

## 4. Requisitos funcionales

Los identificadores sirven para convertir estos requisitos en tareas y
pruebas.

  -----------------------------------------------------------------------
  ID                                  Requisito
  ----------------------------------- -----------------------------------
  RF-01                               El sistema permitirá iniciar sesión
                                      con correo y contraseña.

  RF-02                               Las contraseñas se almacenarán como
                                      hashes apropiados, nunca en texto
                                      plano.

  RF-03                               Las cuentas deshabilitadas no
                                      podrán iniciar sesión ni ejecutar
                                      acciones protegidas.

  RF-04                               El backend verificará autenticación
                                      y permisos en cada operación
                                      privada.

  RF-05                               Solo usuarios autenticados, activos
                                      y con rol `analyst` o `admin`
                                      podrán ejecutar el simulador desde
                                      el dashboard privado.

  RF-06                               FastAPI validará cantidad de eventos
                                      (mínimo 30, predeterminado 100,
                                      máximo 300), intervalo histórico
                                      máximo de 30 días y parámetros.

  RF-07                               El sistema generará escenarios
                                      controlados con relaciones
                                      temporales coherentes entre
                                      eventos.

  RF-08                               Los eventos usarán IP reservadas
                                      para documentación y se
                                      identificarán como simulados.

  RF-09                               Los eventos se guardarán en
                                      `Events` y permanecerán disponibles
                                      después de finalizar la ejecución.

  RF-10                               Cada ejecución tendrá un registro
                                      en `Simulations`, con estado,
                                      parámetros, contadores y resumen.

  RF-11                               El backend evaluará reglas
                                      deterministas contra los eventos;
                                      Angular no ejecutará el motor de
                                      detección.

  RF-12                               Una coincidencia podrá producir una
                                      alerta con regla, severidad,
                                      explicación y eventos relacionados.

  RF-13                               El motor evitará crear alertas
                                      duplicadas al procesar el mismo
                                      patrón por un reintento.

  RF-14                               Un evento podrá estar relacionado
                                      con más de una alerta si satisface
                                      reglas diferentes.

  RF-15                               Los usuarios autorizados podrán
                                      consultar alertas, investigar,
                                      asignar responsables y cambiar
                                      estados.

  RF-16                               Los cambios relevantes de una
                                      alerta generarán registros en
                                      `AuditLogs`.

  RF-17                               El sistema permitirá consultar
                                      eventos por periodo, IP o usuario y
                                      paginar los resultados.

  RF-18                               Las respuestas de ejecución y las
                                      consultas posteriores de estado o
                                      resultados exigirán autorización y
                                      se limitarán a los datos permitidos.

  RF-19                               Los reintentos de una misma
                                      solicitud no deberán multiplicar
                                      eventos o alertas.

  RF-20                               El sistema distinguirá entre
                                      ejecución completa, parcial y
                                      fallida, e informará un resumen de
                                      errores sin filtrar secretos.

  RF-21                               El sistema validará los valores
                                      controlados (roles, estados,
                                      resultados y severidades) en
                                      FastAPI.

  RF-22                               Las fechas se almacenarán en UTC
                                      con formato uniforme ISO 8601.

RF-23                               Cada simulación registrará
                                      `requested_by_user_id` y, de forma
                                      opcional, `requested_by_email` como
                                      snapshot informativo.

RF-24                               Cada ejecución nueva generará
                                      exactamente la cantidad solicitada
                                      de eventos nuevos, sin reutilizar
                                      eventos históricos ni de otras
                                      ejecuciones.

RF-25                               Las ejecuciones nuevas tendrán un
                                      `simulation_id` único; los
                                      reintentos conservarán identidad,
                                      IDs y contenido sin duplicar efectos.

RF-26                               El simulador aceptará una `seed`
                                      opcional para reproducibilidad de
                                      pruebas.

RF-27                               Un `analyst` solo podrá consultar y
                                      gestionar alertas originadas por
                                      simulaciones que inició; un `admin`
                                      podrá consultar alertas de todos
                                      los analistas. FastAPI aplicará la
                                      restricción en listas, búsquedas,
                                      filtros, detalle, evidencia,
                                      auditoría y mutaciones.

## 5. Requisitos no funcionales

  -----------------------------------------------------------------------
  ID                                  Requisito
  ----------------------------------- -----------------------------------
  RNF-01                              **Seguridad:** no almacenar
                                      contraseñas ni claves secretas en
                                      texto plano dentro de la base de
                                      datos o del frontend.

  RNF-02                              **Limitación de abuso:** limitar
                                      intentos de autenticación y
                                      solicitudes del simulador; aplicar
                                      límites de cantidad y periodo.

  RNF-03                              **Consistencia de datos:** validar
                                      y normalizar atributos antes de
                                      escribirlos.

  RNF-04                              **Trazabilidad:** poder explicar
                                      qué regla creó una alerta y qué
                                      eventos la sustentan.

  RNF-05                              **Resiliencia:** reintentar errores
                                      transitorios y elementos no
                                      procesados por operaciones de lote,
                                      sin duplicar registros.

  RNF-06                              **Mantenibilidad:** mantener
                                      reglas, generador, persistencia y
                                      endpoints en módulos separados.

  RNF-07                              **Rendimiento razonable:** usar
                                      `Query` e índices para las
                                      consultas habituales; evitar `Scan`
                                      en caminos frecuentes.

  RNF-08                              **Paginación:** devolver resultados
                                      por páginas y no intentar cargar
                                      todo el historial en una sola
                                      respuesta.

  RNF-09                              **Privacidad:** no incluir
                                      secretos, hashes de contraseña ni
                                      información interna innecesaria en
                                      respuestas de API o logs de
                                      aplicación.

  RNF-10                              **Pruebas:** cubrir umbrales,
                                      límites temporales, duplicados,
                                      permisos y errores parciales.

  RNF-11                              **Claridad:** la descripción de una
                                      alerta explicará el patrón
                                      detectado, el umbral y el intervalo
                                      observado.

  RNF-12                              **Límites de tamaño:** las listas
                                      embebidas, especialmente
                                      `related_event_ids`, tendrán un
                                      tamaño máximo definido.

  RNF-13                              **Autorización:** toda operación
                                      protegida, incluidas las del
                                      simulador, se autorizará en FastAPI.

  RNF-14                              **Separación de entornos:** el
                                      desarrollo utilizará Docker y
                                      DynamoDB Local; el despliegue previsto
                                      utilizará recursos y configuración
                                      segura de AWS.

  RNF-15                              **Concurrencia:** cada usuario puede
                                      tener como máximo una simulación
                                      activa; el backend debe reservarla
                                      de forma segura ante concurrencia.


                                      
  -----------------------------------------------------------------------

## 6. Reglas iniciales de detección

Las cuatro reglas siguientes forman parte del MVP y sus umbrales acordados se deben validar con pruebas y escenarios simulados. Son señales defensivas; no son valores universales ni pruebas concluyentes de ataque.

### Convenciones de evaluación

-   El motor procesa eventos en orden de `timestamp` de ocurrencia, no
    solo por `ingested_at`.
-   Las ventanas se calculan con el tiempo del evento en UTC.
-   Las ventanas temporales se deben definir explícitamente como
    inclusivas/exclusivas en el código para evitar ambigüedades en el
    límite.
-   Una coincidencia debe producir evidencia: regla, intervalo, valores
    agrupados y una lista acotada de IDs de eventos relacionados.
-   El motor no debe considerar un evento aislado como ataque
    confirmado.
-   Un mismo evento puede satisfacer reglas diferentes.
-   Los eventos de una simulación deben estar diseñados para que los
    patrones intencionales realmente caigan dentro de la ventana de la
    regla.
-   Si se procesan eventos históricos, el motor debe evaluar el tiempo
    histórico de los eventos, no compararlos ingenuamente solo con la
    hora actual.

### Reglas propuestas

| ID | Alerta / Descripción | Condición de Activación | Severidad | Datos Registrados | 
| ----- | ----- | ----- | ----- | ----- | 
| **AUTH-001** | Fallos repetidos de autenticación | 5 o más fallos del mismo `username_key` y `source_ip` dentro de 5 minutos | High | IDs de los fallos, usuario, IP, inicio y fin de ventana | 
| **AUTH-002** | Una IP prueba varias cuentas | Fallos desde la misma IP contra 5 o más `username_key` distintos dentro de 10 minutos | High | IP, cuentas distintas y eventos relacionados | 
| **AUTH-003** | Acceso exitoso después de fallos | 5 fallos del mismo `username_key` e IP dentro de 5 minutos, seguidos de un éxito de esa combinación | Medium | Fallos previos y evento exitoso | 
| **AUTH-004** | Actividad fuera de horario de referencia | Evento fuera del horario configurado en `America/Bogota`; permanece desactivada mientras no exista configuración válida | Low o Medium | Hora local calculada, zona horaria y evento | 
  -----------------------------------------------------------------------------

`AUTH-004` forma parte del MVP. Usa la zona horaria `America/Bogota`, pero permanece desactivada hasta configurar explícitamente un horario de referencia válido. No se debe asumir un horario normal.

### Detalles de las reglas

**AUTH-001 --- Fallos repetidos de autenticación**

1.  Agrupar eventos de resultado `failure` por usuario normalizado e IP.
2.  Mantener una ventana móvil de cinco minutos.
3.  Cuando haya cinco o más fallos dentro de la ventana, producir una
    coincidencia.
4.  Evitar emitir una nueva alerta por cada fallo adicional mientras se
    trate del mismo episodio de detección.
5.  Si hay un nuevo episodio claramente separado, permitir una alerta
    nueva.

**AUTH-002 --- Una IP prueba varias cuentas**

1.  Agrupar los fallos por IP.
2.  Contar cuentas normalizadas distintas en una ventana de diez
    minutos.
3.  Activar la regla al llegar a cinco cuentas diferentes.
4.  No contar cinco fallos de una sola cuenta como cinco cuentas
    distintas.

**AUTH-003 --- Acceso exitoso después de fallos**

1.  Buscar al menos cinco fallos recientes para el mismo usuario normalizado e IP dentro de cinco minutos.
2.  Comprobar que luego existe un evento `success` de esa combinación.
3.  Relacionar el éxito y una cantidad acotada de fallos anteriores.
4.  No afirmar que hubo compromiso de cuenta: se trata de una secuencia
    que puede merecer revisión.

**AUTH-004 --- Fuera de horario**

La zona horaria es `America/Bogota`. La regla permanece desactivada hasta configurar un horario de referencia válido. El timestamp se conserva en UTC; la conversión local solo se usa para evaluar y explicar la alerta.

## 7. ¿Puede un evento generar varias alertas?

**Sí.** Un evento puede participar en varias alertas cuando satisface
condiciones de reglas diferentes.

Ejemplo: una IP falla repetidamente al autenticarse contra una cuenta y,
además, prueba muchas cuentas. Los eventos de esa IP podrían contribuir
tanto a `AUTH-001` como a `AUTH-002`. No es necesariamente un duplicado:
cada regla describe un patrón distinto.

### Modelo recomendado para el MVP

-   **Una alerta representa una coincidencia de una regla sobre un
    patrón o episodio**, no simplemente un evento.
-   La alerta identifica la regla mediante `rule_id`.
-   `related_event_ids` contiene los IDs de los eventos que sustentan la
    coincidencia.
-   Un evento puede aparecer en las listas de varias alertas.
-   La misma coincidencia no debe crear una alerta nueva cada vez que se
    reintenta el procesamiento.
-   Si llegan más eventos y amplían el mismo episodio, el motor puede
    actualizar la alerta existente (por ejemplo, `last_event_at` y la
    lista acotada de evidencia) en lugar de abrir una alerta por cada
    evento.
-   Si se detecta un episodio nuevo separado, puede crearse una alerta
    nueva, aunque use la misma regla.
### Simulador privado, persistencia e idempotencia

El simulador está dentro del dashboard privado. No existe un endpoint público para iniciar simulaciones, una clave independiente del simulador ni generación anónima de eventos. FastAPI debe autorizar cada endpoint de inicio, estado, recuperación de resultados y cualquier acción adicional del simulador. Solo una cuenta activa con sesión/token válido y rol `analyst` o `admin` puede ejecutarlo. Un analista consulta únicamente sus ejecuciones; un administrador puede consultar todas. Cada usuario puede tener como máximo una ejecución activa.

Flujo de una ejecución:

1. El usuario autenticado abre el simulador en el dashboard.
2. Angular envía los parámetros a FastAPI; Angular no decide permisos ni ejecuta reglas.
3. FastAPI valida cuenta, rol, cantidad (30–300, predeterminada 100), intervalo histórico (máximo 30 días) y `seed` opcional.
4. Se registra una ejecución con `simulation_id` único, estado `pending` y `requested_by_user_id`. `requested_by_email` puede guardarse como snapshot informativo.
5. El backend genera exactamente la cantidad solicitada de eventos nuevos. Cada evento tiene un ID único y estable, por ejemplo `SIM-<simulation_id>-EVT-000001`, y no se reutilizan eventos de ejecuciones previas.
6. Los eventos se persisten en `Events` con `simulation_id`, `data_source=simulator`, `timestamp` de ocurrencia, `ingested_at`, `date_bucket` y `timestamp_event`, según el modelo de datos.
7. El motor evalúa los eventos generados en orden temporal, aplicando las reglas y creando alertas idempotentemente.
8. Se actualizan contadores, resumen de escenarios, alertas creadas y estado final.
9. FastAPI devuelve el resumen de esa ejecución. Las consultas posteriores de estado y resultados requieren autorización.

Una ejecución nueva e independiente crea otro `simulation_id` y otro conjunto de eventos. Un reintento de una solicitud ya iniciada conserva su identidad, IDs y contenido y no duplica eventos, alertas ni contadores. Una `seed` opcional facilita reproducir pruebas; no sustituye la clave de idempotencia de la solicitud.

### Idempotencia de eventos y alertas

- Asociar una clave de idempotencia estable de la solicitud con un `simulation_id`.
- Derivar los IDs de eventos del `simulation_id` y de una posición o clave determinista.
- Mantener estables los datos generados cuando se reintente la misma ejecución.
- Identificar alertas por regla, agrupación afectada y episodio/ventana; no usar permanentemente solo `rule_id + usuario + IP`.
- Usar escrituras condicionales donde corresponda. `BatchWriteItem` admite hasta 25 operaciones por llamada, no permite condiciones individuales por elemento y puede devolver `UnprocessedItems`; dividir lotes, reintentar elementos no procesados con espera progresiva y límite de intentos.
- Registrar contadores y estados de forma que los reintentos no incrementen dos veces los resultados.
- No marcar `completed` mientras queden escrituras o detecciones pendientes. Si ocurre un error después de guardar parte de los datos, reflejar el resultado como `partial` cuando corresponda y permitir reanudación sin duplicados.

### Identidad de episodios y deduplicación

La identidad de un episodio debe incluir `rule_id`, agrupación e identidad de la ventana/episodio. La identidad debe ser estable entre reintentos y permitir episodios nuevos separados. La política exacta para determinar inicio, fin y ampliación de un episodio continúa pendiente. Reprocesar exactamente la misma coincidencia no debe duplicar alertas; un evento puede sustentar reglas distintas. Una alerta `resolved` no se reabre automáticamente.

**Pendiente antes de implementar la deduplicación entre coincidencias ampliadas:** especificar formalmente cuándo empieza y termina un episodio, cómo se determina uno nuevo y cómo se relacionan nuevos eventos con alertas existentes. No se debe asumir una política de ventana fija ni inventar transiciones. Una alerta `resolved` no se reabre automáticamente; el tratamiento de un patrón posterior requiere decisión explícita.

### Alcance de auditoría

`AuditLogs` es, para este MVP, el historial de cambios relevantes de alertas (incluidos cambio de estado y asignación), con actor, fecha y valores anteriores/nuevos cuando corresponda. No es auditoría global de acciones administrativas o técnicas.

## 8. Estados y ciclo de vida de una alerta

Estados permitidos:

-   `open`: la alerta acaba de crearse y espera revisión.
-   `investigating`: un analista la está revisando.
-   `resolved`: el analista concluyó la revisión según el proceso del
    MVP.

Flujo recomendado:

1.  El motor detecta una coincidencia y crea la alerta con estado
    `open`.
2.  Un analista abre la alerta y consulta la evidencia.
3.  Si empieza la investigación, cambia el estado a `investigating` y se
    registra la acción.
4.  El analista puede asignar la alerta a un responsable; esa acción
    también se registra.
5.  Cuando termina la revisión, cambia a `resolved`, opcionalmente con
    comentario.
6.  Cada cambio relevante genera un registro de auditoría con actor,
    fecha, acción y valores anteriores/nuevos cuando corresponda.

El backend debe comprobar que la transición de estado es válida y que el
usuario tiene permiso. Angular no debe decidir por sí solo si una
transición está autorizada.

## 9. Access patterns, índices y paginación: relación con los requisitos

El diseño de DynamoDB parte de las preguntas que la aplicación necesita
contestar. Los *Access Patterns* son esas consultas expresadas de manera
concreta: por ejemplo, "obtener eventos de una IP entre dos tiempos" o
"listar alertas abiertas de más recientes a más antiguas".

Las claves primarias permiten recuperar elementos directamente. Los
índices secundarios globales (GSI) habilitan consultas por otras
dimensiones sin tener que recorrer toda la tabla. Una `Query` exige una
clave de partición y puede restringir la clave de ordenamiento; un
`FilterExpression` elimina resultados después de leer los candidatos y
no sustituye un índice bien diseñado.

La paginación evita cargar todo el historial de una vez. El tamaño predeterminado es 25 elementos y el máximo es 100. DynamoDB puede
devolver una página de hasta 1 MB de datos evaluados, y una consulta
también puede configurarse con `Limit`. Si la respuesta contiene
`LastEvaluatedKey`, el cliente/backend debe continuar usando esa clave
como `ExclusiveStartKey` en la siguiente petición. El `Limit` indica
cuántos elementos se evalúan como máximo, no garantiza esa cantidad de
resultados finales cuando hay filtros.

La API expone `limit` predeterminado de 25 y máximo de 100, y un cursor
opaco que codifica el estado de paginación de todas las particiones consultadas. En consultas multi-día o multi-estado, el backend debe conservar el estado de cada consulta y el buffer necesario para mantener el orden global entre páginas. El frontend devuelve ese
cursor para pedir la siguiente página; no debe fabricar la clave de
DynamoDB. La respuesta debe incluir los elementos y un cursor siguiente,
que será nulo cuando no haya más páginas. El orden y la consistencia de
resultados entre páginas deben documentarse, especialmente si se
insertan nuevos eventos mientras se navega.

Los GSI de DynamoDB tienen consistencia eventual: inmediatamente después
de escribir un elemento, una consulta a un GSI puede tardar un poco en
reflejarlo. El backend no debe asumir que un elemento recién escrito
aparecerá instantáneamente en todas las consultas de índice.

La visibilidad de eventos por propietario no está definida. No se debe extender automáticamente a eventos la restricción de visibilidad definida para alertas; debe acordarse si los analistas pueden consultar todos los eventos o solo los asociados con sus simulaciones.

## 10. Flujo completo del programa en ejecución

### A. Inicio de la aplicación

1.  Angular carga la aplicación y muestra la pantalla pública de acceso.
2.  FastAPI arranca, carga configuración y prepara los componentes de
    autenticación, simulación, persistencia y detección.
3.  El backend valida que su configuración esencial esté presente. Los
    secretos se leen desde variables de entorno en desarrollo y desde un
    gestor de secretos apropiado en despliegue.
4.  DynamoDB Local está disponible en desarrollo; el backend utiliza el
    endpoint configurado para el entorno local.

### B. Camino del simulador privado

1. El usuario inicia sesión y entra al dashboard privado.
2. Un usuario con rol `analyst` o `admin` selecciona el simulador.
3. Angular envía los parámetros permitidos a FastAPI.
4. FastAPI valida sesión/token, estado activo de la cuenta y rol autorizado.
5. FastAPI valida cantidad (30–300; predeterminada 100), intervalo histórico
   (máximo 30 días), `seed` opcional y demás parámetros.
6. Se crea un `simulation_id` único y se registra la ejecución en
   `Simulations` con estado `pending`, `requested_by_user_id` y, si se
   configura, `requested_by_email`; luego cambia a `running`.
7. El generador crea exactamente la cantidad solicitada de eventos nuevos.
   Los timestamps caen dentro del intervalo solicitado y los eventos de
   patrones intencionales caen dentro de las ventanas de sus reglas.
8. Los IDs son estables durante reintentos, por ejemplo
   `SIM-<simulation_id>-EVT-000001`. Se establecen `simulation_id`,
   `data_source=simulator`, `timestamp`, `ingested_at`, `date_bucket` y
   `timestamp_event`, según el modelo de datos.
9. FastAPI persiste eventos en lotes de hasta 25 operaciones y reintenta
   `UnprocessedItems` con espera progresiva y límite de intentos.
10. El motor evalúa los eventos generados en orden temporal, sin depender
    de una lectura inmediata de un GSI recién actualizado.
11. El gestor de alertas deduplica por regla, agrupación y episodio.
12. Se actualizan contadores, distribución de escenarios, alertas creadas
    y estado final: `completed`, `partial` o `failed`.
13. FastAPI devuelve el resumen de esa ejecución. Las consultas posteriores
    de estado y resultados también requieren autorización.
### C. Camino del usuario privado

1.  El analista o administrador envía sus credenciales a FastAPI por una
    conexión segura en despliegue.
2.  FastAPI busca la cuenta por `email_normalized`, verifica el hash de
    la contraseña y comprueba que el usuario esté activo.
3.  El backend entrega una sesión o token seguro con una política de
    expiración adecuada. Las rutas privadas validan la sesión/token en
    cada petición.
4.  Angular consulta el dashboard y solicita páginas de eventos o
    alertas según los filtros elegidos.
5.  FastAPI selecciona el patrón de acceso adecuado y consulta la tabla
    o GSI correspondiente; si hay más resultados, devuelve un cursor de
    paginación.
6.  Al abrir una alerta, el backend obtiene la alerta y sus eventos
    relacionados, valida los permisos y entrega la evidencia.
7.  Al cambiar estado o asignar responsable, FastAPI valida la
    transición y el rol, actualiza la alerta y agrega un registro a
    `AuditLogs`.
8.  El dashboard actualiza su vista usando las respuestas del backend.
    El frontend no accede directamente a DynamoDB.

### D. Camino de una detección

1.  El motor recibe un conjunto de eventos ordenado por `timestamp`.
2.  Las reglas agrupan y evalúan los eventos dentro de ventanas
    temporales.
3.  Cada coincidencia genera una estructura interna con `rule_id`,
    agrupación, ventana, severidad y evidencia.
4.  El gestor de alertas calcula la identidad estable de la coincidencia
    y comprueba si ya existe.
5.  Si es nueva, crea una alerta `open`; si es la misma coincidencia
    reintentada, evita el duplicado y puede actualizar la evidencia
    según la política definida.
6.  Si una coincidencia satisface otra regla, esa regla puede generar
    una alerta distinta.
7.  La ejecución registra cuántas coincidencias y alertas únicas
    produjo.

## 11. Idempotencia, lotes y errores parciales

La idempotencia significa que repetir una misma solicitud por un error
de red o un reintento no debe multiplicar sus efectos.

-   Una solicitud de simulación debe tener una clave de idempotencia
    estable.
-   Los reintentos de esa solicitud deben recuperar el mismo
    `simulation_id`, no generar uno nuevo.
-   Los IDs de eventos se derivan de la ejecución y de su posición o
    clave determinista.
-   Las alertas se identifican por regla y episodio, no por cada intento
    de escritura.
-   Para crear elementos únicos se debe considerar una escritura
    condicional; `BatchWriteItem` no permite condiciones por elemento.
-   `BatchWriteItem` admite hasta 25 operaciones por solicitud y puede
    devolver `UnprocessedItems`; el backend debe reintentarlos con
    backoff y un límite definido.
-   No se debe marcar una simulación `completed` mientras queden
    escrituras o detecciones pendientes.
-   Si se produce un error después de guardar algunos eventos, se
    registra el resultado parcial y se diseña la reanudación para que no
    duplique datos.
-   Las actualizaciones de una alerta existente deben ser seguras ante
    reintentos y evitar sobrescribir cambios más recientes sin control.

## 12. Límites iniciales de producto

Estos valores son límites iniciales del MVP, ajustables tras pruebas:

  -----------------------------------------------------------------------
  Parámetro                                       Valor inicial propuesto
  ------------------------------ ----------------------------------------
  Eventos mínimos por ejecución                                      30

  Eventos predeterminados por ejecución                              100

  Máximo de eventos por ejecución                                    300

  Intervalo histórico máximo                                      30 días

  Tamaño máximo de página de API                            100 elementos

  Tamaño de lote de escritura                              25 operaciones
  DynamoDB                       

  Evidencia embebida por alerta        Máximo de 20 `related_event_ids`

  Ventana de `AUTH-001`                                         5 minutos

  Umbral de `AUTH-001`                                           5 fallos

  Ventana de `AUTH-002`                                        10 minutos

  Umbral de `AUTH-002`                                5 cuentas distintas  

  -----------------------------------------------------------------------

Los límites de producto no son límites técnicos máximos de DynamoDB.
Deben validarse en FastAPI. La página predeterminada es de 25 elementos y
el máximo es 100; `related_event_ids` admite como máximo 20 IDs. Ambos
valores se cubren con pruebas.

## 13. Responsabilidades por componente

  -----------------------------------------------------------------------
  Componente                          Responsabilidad
  ----------------------------------- -----------------------------------
  Angular                             Formular solicitudes, mostrar
                                      estados y resultados, aplicar
                                      filtros de interfaz y enviar
                                      cursores de paginación. No contiene
                                      secretos ni ejecuta reglas.

  FastAPI / endpoints                 Validar entradas, autenticar,
                                      autorizar, limitar uso, coordinar
                                      servicios y construir respuestas
                                      públicas/privadas.

  Servicio de simulación              Construir escenarios y eventos
                                      reproducibles, asignar IDs estables
                                      y producir un resumen.

  Repositorio DynamoDB                Encapsular `GetItem`, `PutItem`,
                                      `UpdateItem`, `Query`, índices,
                                      paginación, lotes y reintentos.

  Motor de detección                  Evaluar reglas sobre eventos
                                      ordenados y producir coincidencias
                                      con evidencia.

  Gestor de alertas                   Deduplicar coincidencias,
                                      crear/actualizar alertas y aplicar
                                      política de episodio.

  Servicio de auditoría               Añadir registros de acciones
                                      relevantes con actor y fecha.

  DynamoDB                            Persistir usuarios, eventos,
                                      alertas, auditoría y ejecuciones.
                                      No ejecuta las reglas de negocio
                                      por sí mismo.  

  -----------------------------------------------------------------------

## 14. Criterios de aceptación antes de considerar listo el MVP

-   [ ] Un visitante no autenticado no puede ejecutar el simulador ni consultar sus resultados.
-   [ ] Solo cuentas activas con rol `analyst` o `admin` pueden ejecutar simulaciones.
-   [ ] Todos los endpoints del simulador validan autenticación, estado de cuenta y autorización.
-   [ ] FastAPI rechaza cantidades inferiores a 30 o superiores a 300 y periodos mayores de 30 días.
-   [ ] Cada ejecución completa genera exactamente la cantidad solicitada de eventos nuevos.
-   [ ] La cantidad predeterminada es 100 eventos y se aplica en FastAPI.
-   [ ] La generación produce los escenarios esperados con timestamps
    coherentes.
-   [ ] Los eventos se guardan y siguen consultables después de
    finalizar la ejecución.
-   [ ] Los lotes reintentan elementos no procesados sin duplicar
    eventos.
-   [ ] `AUTH-001` se activa al alcanzar el umbral dentro de la ventana
    y no se activa por debajo del umbral.
-   [ ] `AUTH-002` cuenta usuarios distintos, no solamente el número de
    eventos.
-   [ ] `AUTH-003` relaciona los fallos previos con el acceso exitoso.
-   [ ] Una coincidencia reintentada no crea una alerta duplicada.
-   [ ] Un evento puede estar relacionado con alertas de reglas
    distintas.
-   [ ] El analista no puede administrar cuentas si esa acción se
    reserva a `admin`.
-   [ ] Cada cambio de estado o asignación genera auditoría.
-   [ ] La paginación funciona con varias páginas y finaliza cuando no
    hay cursor siguiente.
-   [ ] Las consultas de estado y resultados requieren autorización y no exponen información a usuarios no autorizados.
-   [ ] Cada ejecución registra el usuario solicitante.
-   [ ] Una ejecución nueva produce eventos nuevos; un reintento no duplica eventos ni alertas.
-   [ ] La `seed` opcional permite reproducir escenarios de prueba.
-   [ ] Los errores parciales quedan reflejados en el estado de la
    ejecución.

