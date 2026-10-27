# TraceHunt — Inicialización automática de DynamoDB

## 1. Objetivo del cambio

El objetivo de esta implementación es automatizar la inicialización de las tablas de DynamoDB utilizadas por TraceHunt, evitando que los desarrolladores tengan que crearlas manualmente cada vez que preparan el entorno de desarrollo.

Para conseguirlo, se incorporó el script `dynamodb/init_tables.py` y se modificó `docker-compose.yml` para integrarlo en el proceso de arranque de la aplicación.

Con esta implementación, Docker Compose coordina tres servicios:

1. `dynamodb-local`: ejecuta una instancia local de DynamoDB.
2. `dynamodb-init`: ejecuta el script que comprueba e inicializa las tablas.
3. `api`: ejecuta el backend de TraceHunt mediante FastAPI.

El objetivo es que la API no comience a ejecutarse hasta que la inicialización de DynamoDB haya finalizado correctamente.

### 1.1. Problema que resuelve

Antes de esta automatización, el desarrollador debía asegurarse de que las tablas necesarias existieran antes de utilizar la aplicación.

Esto podía generar problemas cuando:

* Se preparaba el proyecto en un equipo nuevo.
* Se utilizaba una instancia de DynamoDB Local sin tablas.
* Se reconstruía el entorno de desarrollo.
* Se incorporaban nuevos integrantes al equipo.
* Se necesitaba reproducir el entorno de otro desarrollador.

La automatización reduce estas tareas manuales y hace que el proceso de preparación del entorno sea más reproducible.

### 1.2. Alcance de la implementación

Esta funcionalidad se encarga de:

* Comprobar la disponibilidad de DynamoDB.
* Consultar qué tablas existen.
* Crear las tablas que falten utilizando sus archivos JSON de definición.
* Esperar a que las tablas creadas alcancen el estado `ACTIVE`.
* Finalizar con un código de salida que permite a Docker Compose determinar si la inicialización fue exitosa.
* Coordinar el inicio de la API con el resultado de la inicialización.

**Importante:** este componente no se encarga de crear el primer administrador ni de implementar los mecanismos de autenticación. Esas responsabilidades permanecen separadas.

---

# 2. Archivo `dynamodb/init_tables.py`

## 2.1. ¿Qué hace este archivo?

`init_tables.py` es un script de Python responsable de preparar las tablas de DynamoDB necesarias para el funcionamiento de TraceHunt.

El script se conecta a una instancia de DynamoDB, comprueba si las tablas definidas en los archivos JSON existen y crea las que todavía no están disponibles.

También verifica que las tablas estén listas para utilizarse antes de finalizar su ejecución.

En lugar de crear las tablas directamente dentro del código Python, utiliza archivos JSON como fuente de sus definiciones.

Esto permite mantener separadas dos responsabilidades:

* Los archivos JSON definen la estructura de las tablas.
* El script Python ejecuta el proceso de inicialización.

### 2.2. Tablas que administra

El inicializador utiliza los siguientes archivos JSON:

| Archivo JSON                       | Tabla de DynamoDB |
| ---------------------------------- | ----------------- |
| `dynamodb/create-users.json`       | `Users`           |
| `dynamodb/create-events.json`      | `Events`          |
| `dynamodb/create-alerts.json`      | `Alerts`          |
| `dynamodb/create-audit-logs.json`  | `AuditLogs`       |
| `dynamodb/create-simulations.json` | `Simulations`     |

Estos archivos contienen las definiciones utilizadas para crear las tablas.

El script no debe tratarse como una fuente alternativa de la estructura de las tablas. Cuando se necesite modificar una definición, se debe revisar el archivo JSON correspondiente y comprobar que la modificación sea compatible con la lógica de la aplicación.

### 2.3. ¿Por qué se utilizan archivos JSON?

Los archivos JSON permiten declarar la configuración necesaria para crear las tablas mediante las operaciones de DynamoDB.

Esto aporta varias ventajas:

* Las definiciones de las tablas están separadas de la lógica Python.
* Es más sencillo revisar los cambios en Git.
* Se puede identificar qué tabla corresponde a cada archivo.
* El inicializador puede reutilizar las definiciones sin duplicarlas dentro del código.
* Los cambios en la estructura de una tabla se pueden revisar de forma independiente del mecanismo de inicialización.

El contenido de los archivos JSON debe mantenerse compatible con las operaciones de creación de tablas de DynamoDB.

---

## 3. ¿Cómo funciona `init_tables.py`?

El script sigue un proceso secuencial.

### Paso 1. Carga las dependencias

El archivo utiliza bibliotecas de Python para leer archivos, obtener variables de entorno, comunicarse con DynamoDB y controlar los tiempos de espera.

Entre sus importaciones se encuentran:

| Biblioteca o módulo       | Función                                                                                    |
| ------------------------- | ------------------------------------------------------------------------------------------ |
| `json`                    | Leer las definiciones JSON de las tablas.                                                  |
| `os`                      | Consultar variables de entorno.                                                            |
| `sys`                     | Finalizar el proceso con códigos de salida.                                                |
| `time`                    | Controlar las pausas entre reintentos.                                                     |
| `pathlib.Path`            | Trabajar con rutas de archivos.                                                            |
| `boto3`                   | Comunicarse con DynamoDB mediante el SDK de AWS para Python.                               |
| `ClientError`             | Gestionar errores devueltos por los servicios de AWS compatibles con el cliente utilizado. |
| `EndpointConnectionError` | Identificar problemas de conexión con el endpoint.                                         |

El uso de estas herramientas permite que el inicializador controle tanto la comunicación con DynamoDB como los errores que pueden ocurrir durante el proceso.

### Paso 2. Obtiene la configuración

Antes de conectarse a DynamoDB, el script consulta determinadas variables de entorno.

Estas variables permiten establecer:

* La dirección del servicio DynamoDB.
* La región de AWS.
* Las credenciales que utiliza el cliente de Boto3.
* La cantidad máxima de intentos para comprobar la disponibilidad.
* El tiempo de espera entre intentos.

Los valores y sus mecanismos de configuración se explican en la sección 4.

### Paso 3. Espera a que DynamoDB esté disponible

Que un contenedor aparezca como iniciado no significa necesariamente que DynamoDB ya esté preparado para recibir solicitudes.

Por esta razón, el script contempla reintentos para comprobar la disponibilidad del servicio.

La configuración utilizada establece:

* `MAX_RETRIES = 30`
* `RETRY_DELAY_SECONDS = 2`

Esto permite realizar hasta 30 intentos de comprobación, con una pausa de dos segundos entre intentos cuando corresponde.

El tiempo total puede variar según el momento en que DynamoDB responda y según la implementación de los reintentos.

Si el servicio no está disponible después de agotar los intentos, la inicialización debe finalizar con un error.

### Paso 4. Comprueba qué tablas existen

Una vez que DynamoDB responde, el script consulta las tablas existentes.

Para cada tabla definida en los archivos JSON, determina si ya existe.

Este comportamiento evita intentar crear nuevamente una tabla que ya está presente.

Por ejemplo, si DynamoDB ya contiene la tabla `Users`, el inicializador reconoce su existencia y continúa con el proceso sin crearla de nuevo.

Esto hace que el proceso pueda ejecutarse repetidamente sin intentar recrear todas las tablas en cada arranque.

**Importante:** detectar una tabla existente no significa que el inicializador compare y actualice automáticamente toda su estructura para hacerla coincidir con el archivo JSON. La finalidad de esta implementación es comprobar la existencia, crear las tablas ausentes y verificar su disponibilidad.

### Paso 5. Crea las tablas que falten

Cuando una tabla no existe, el inicializador utiliza el archivo JSON correspondiente para obtener su definición y solicitar su creación.

Por ejemplo:

* Si falta `Users`, utiliza `create-users.json`.
* Si falta `Events`, utiliza `create-events.json`.
* Si falta `Alerts`, utiliza `create-alerts.json`.

El mismo procedimiento se aplica a `AuditLogs` y `Simulations`.

De esta manera, el inicializador puede preparar una instancia nueva sin requerir que todas las tablas se creen manualmente.

### Paso 6. Espera a que las tablas estén activas

Después de solicitar la creación de una tabla, DynamoDB puede necesitar un tiempo para completar la operación.

Por eso, el script verifica que las tablas alcancen el estado `ACTIVE`.

Este estado indica que la tabla está activa y disponible para las operaciones que admite DynamoDB.

La comprobación evita considerar finalizada la inicialización inmediatamente después de enviar una solicitud de creación.

### Paso 7. Finaliza con un código de salida

Al terminar, el script devuelve un resultado mediante el código de salida del proceso.

En términos generales:

* Código `0`: la inicialización finalizó correctamente.
* Código distinto de `0`: se produjo un error que impidió completar la inicialización.

Este resultado es importante porque Docker Compose lo utiliza para determinar si puede continuar con el inicio de la API.

---

# 4. Variables de entorno de `init_tables.py`

El inicializador utiliza variables de entorno para obtener la configuración de conexión con DynamoDB.

Estas variables permiten separar la configuración del código y adaptar el comportamiento del script a diferentes entornos.

## 4.1. `DYNAMODB_ENDPOINT_URL`

**Valor predeterminado utilizado:**

```text
http://dynamodb-local:8000
```

Esta variable indica la dirección del endpoint al que se conecta Boto3.

En Docker Compose, `dynamodb-local` es el nombre del servicio que ejecuta DynamoDB Local.

Los contenedores que comparten la red de Compose pueden utilizar el nombre del servicio para comunicarse entre sí.

Por ejemplo, desde el contenedor del inicializador, la dirección:

```text
http://dynamodb-local:8000
```

apunta al servicio DynamoDB Local en el puerto `8000`.

### ¿Por qué no se utiliza `localhost`?

Dentro de un contenedor, `localhost` hace referencia al propio contenedor.

Por eso, si el inicializador intentara conectarse a:

```text
http://localhost:8000
```

estaría buscando el servicio en su propio contenedor, no en el contenedor `dynamodb-local`.

Por el contrario, cuando se ejecuta una herramienta directamente desde el equipo anfitrión, normalmente se utiliza:

```text
http://localhost:8000
```

Esto es posible porque Docker publica el puerto del contenedor en el equipo anfitrión.

**Regla práctica:**

* Desde otro contenedor de Compose: `http://dynamodb-local:8000`.
* Desde el equipo anfitrión: `http://localhost:8000`.

## 4.2. `AWS_REGION`

**Valor predeterminado utilizado:**

```text
us-east-1
```

Esta variable indica la región que utiliza el cliente de Boto3.

Aunque DynamoDB Local no necesita conectarse a una región real de AWS para ejecutar sus operaciones locales, Boto3 requiere una región para configurar el cliente.

El valor `us-east-1` se utiliza aquí como configuración de desarrollo.

Esto no significa que las tablas se estén creando en DynamoDB de producción en esa región.

## 4.3. `AWS_ACCESS_KEY_ID`

**Valor predeterminado utilizado:**

```text
local
```

Esta variable proporciona al cliente de Boto3 el identificador de acceso que utiliza para firmar las solicitudes.

En este entorno local, se emplea un valor de desarrollo porque DynamoDB Local no requiere credenciales reales de AWS para su uso normal.

Este valor no debe interpretarse como una credencial válida para acceder a una cuenta real de AWS.

## 4.4. `AWS_SECRET_ACCESS_KEY`

**Valor predeterminado utilizado:**

```text
local
```

Esta variable proporciona al cliente de Boto3 la clave secreta asociada al identificador de acceso.

Al igual que la variable anterior, el valor utilizado es una configuración de desarrollo para DynamoDB Local.

**Advertencia:** no se deben utilizar credenciales reales de AWS como valores de ejemplo ni guardar secretos de producción en el repositorio.

Si el proyecto se conecta posteriormente a un servicio real de AWS, la gestión de credenciales debe adaptarse al entorno y a las prácticas de seguridad correspondientes.

## 4.5. `MAX_RETRIES`

**Valor utilizado:**

```python
MAX_RETRIES = 30
```

Esta constante establece el límite de intentos que se utilizan para comprobar la disponibilidad de DynamoDB.

Permite que el inicializador tolere un retraso en el arranque del servicio.

No es una variable de entorno en la configuración descrita, sino una constante definida en el código Python.

## 4.6. `RETRY_DELAY_SECONDS`

**Valor utilizado:**

```python
RETRY_DELAY_SECONDS = 2
```

Esta constante establece el intervalo de espera entre intentos de comprobación, expresado en segundos.

Tampoco es una variable de entorno en la configuración descrita: es una constante del script.

## 4.7. ¿Cómo obtiene el script estos valores?

El script utiliza el módulo `os` para consultar las variables de entorno y establecer valores predeterminados cuando no están definidas.

Conceptualmente, el mecanismo es similar al siguiente:

```python
import os

endpoint_url = os.getenv(
    "DYNAMODB_ENDPOINT_URL",
    "http://dynamodb-local:8000"
)

region = os.getenv(
    "AWS_REGION",
    "us-east-1"
)
```

Este fragmento ilustra el mecanismo general de lectura de variables; no sustituye al código existente en `init_tables.py`.

El comportamiento es el siguiente:

1. Python busca la variable de entorno.
2. Si está definida, obtiene su valor.
3. Si no está definida, utiliza el valor predeterminado indicado.
4. El script utiliza la configuración resultante para preparar el cliente de DynamoDB.

En Docker Compose, estas variables se pueden proporcionar en la sección `environment` de un servicio.

Por ejemplo:

```yaml
environment:
  DYNAMODB_ENDPOINT_URL: http://dynamodb-local:8000
  AWS_REGION: us-east-1
  AWS_ACCESS_KEY_ID: local
  AWS_SECRET_ACCESS_KEY: local
```

Este ejemplo representa la configuración utilizada por el servicio inicializador.

---

# 5. Cambios realizados en `docker-compose.yml`

## 5.1. ¿Qué función cumple ahora este archivo?

`docker-compose.yml` define los servicios, sus configuraciones y las relaciones necesarias para ejecutar TraceHunt en un entorno de desarrollo basado en Docker.

Con la automatización implementada, no solamente define cómo iniciar DynamoDB y la API, sino también cómo ejecutar el proceso de inicialización de las tablas antes de iniciar la aplicación.

La secuencia prevista es:

```text
                 docker compose up
                         |
                         v
                 dynamodb-local
                         |
                         v
                  dynamodb-init
                         |
              Inicialización correcta
                         |
                         v
                        api
                         |
                         v
                  FastAPI disponible
```

La relación entre los servicios evita que la API comience a ejecutarse antes de que el inicializador haya finalizado correctamente.

## 5.2. Servicio `dynamodb-local`

Este servicio ejecuta la imagen de DynamoDB Local.

Su función es proporcionar una instancia de DynamoDB para el desarrollo y las pruebas locales.

La configuración utiliza:

* Imagen `amazon/dynamodb-local`.
* Puerto `8000` del contenedor.
* Modo de base de datos compartida mediante `-sharedDb`.
* Directorio de datos `/home/dynamodblocal/data` dentro del contenedor.
* Volumen asociado a `./docker/dynamodb` en el repositorio.

La relación del volumen es importante:

```text
Repositorio:
./docker/dynamodb

          |
          v

Contenedor DynamoDB Local:
/home/dynamodblocal/data
```

El volumen permite conservar los datos locales fuera del ciclo de vida del contenedor.

Por eso, eliminar o recrear el contenedor no implica necesariamente eliminar las tablas o los datos almacenados en ese directorio.

Esta característica también explica por qué, durante las pruebas, el inicializador encontró tablas existentes en lugar de crearlas nuevamente.

## 5.3. Nuevo servicio `dynamodb-init`

Este es el servicio incorporado para ejecutar la inicialización automática.

Su configuración utiliza:

* La imagen construida a partir de `./backend`.
* El comando `python /dynamodb/init_tables.py`.
* Un montaje de `./dynamodb` en `/dynamodb`, en modo de solo lectura.
* Las variables de entorno necesarias para conectarse a DynamoDB Local.
* Una dependencia del servicio `dynamodb-local`.

### ¿Por qué se monta la carpeta en modo de solo lectura?

La configuración:

```yaml
volumes:
  - ./dynamodb:/dynamodb:ro
```

permite que el contenedor lea los archivos JSON y el script desde la carpeta `dynamodb` del repositorio.

El sufijo `:ro` indica que el montaje es de solo lectura desde la perspectiva del contenedor.

Esto es adecuado porque el inicializador necesita consultar las definiciones de las tablas, no modificar los archivos del repositorio.

### ¿Por qué utiliza la imagen de `./backend`?

El inicializador necesita un entorno Python que tenga instaladas las dependencias requeridas por el script, incluido Boto3.

Al utilizar la imagen construida para el backend, se aprovecha ese entorno en lugar de tener que mantener una imagen independiente exclusivamente para la inicialización.

Esto también implica que la imagen del backend debe contener las dependencias y la configuración necesarias para ejecutar el script.

## 5.4. Cambio en el servicio `api`

El servicio de la API continúa ejecutando el backend de TraceHunt.

La configuración incluye:

* Construcción a partir de `./backend`.
* Archivo de variables de entorno `./backend/.env`.
* Publicación del puerto `8080` del equipo anfitrión hacia el puerto `8000` del contenedor.
* Endpoint de DynamoDB Local configurado mediante `DYNAMODB_ENDPOINT_URL`.
* Dependencia del servicio `dynamodb-init`.

El cambio fundamental es la dependencia con condición de finalización exitosa:

```yaml
depends_on:
  dynamodb-init:
    condition: service_completed_successfully
```

Esta condición indica que Docker Compose debe esperar a que el servicio inicializador termine correctamente antes de iniciar la API.

No basta con que el contenedor del inicializador exista o haya comenzado a ejecutarse: debe finalizar con éxito.

Si la inicialización falla, Compose no debe iniciar la API a través de esta dependencia.

### ¿Por qué es importante esta condición?

Sin una condición que espere la finalización exitosa del inicializador, la API podría intentar conectarse a DynamoDB antes de que las tablas estuvieran disponibles.

Esto podría ocasionar errores durante el arranque o al realizar las primeras operaciones de la aplicación.

Con la condición implementada, se establece una secuencia de inicio más controlada.

**Importante:** esta condición coordina el arranque inicial. No sustituye la gestión de errores de conexión que la aplicación pueda necesitar durante su funcionamiento posterior.

---

# 6. Resumen de las modificaciones de Docker Compose

| Elemento                         | Función                                                                    |
| -------------------------------- | -------------------------------------------------------------------------- |
| `dynamodb-local`                 | Ejecuta DynamoDB Local.                                                    |
| `dynamodb-init`                  | Ejecuta el inicializador de tablas.                                        |
| `api`                            | Ejecuta el backend FastAPI.                                                |
| `./docker/dynamodb`              | Almacena los datos locales de DynamoDB mediante un volumen.                |
| `./dynamodb:/dynamodb:ro`        | Permite al inicializador leer el script y los archivos JSON.               |
| `DYNAMODB_ENDPOINT_URL`          | Define el endpoint al que se conecta el cliente de DynamoDB.               |
| `AWS_REGION`                     | Define la región configurada para Boto3.                                   |
| `AWS_ACCESS_KEY_ID`              | Define el identificador de acceso utilizado por el cliente.                |
| `AWS_SECRET_ACCESS_KEY`          | Define la clave secreta utilizada por el cliente.                          |
| `service_completed_successfully` | Exige que la inicialización termine correctamente antes de iniciar la API. |
| `./backend/.env`                 | Proporciona las variables de entorno configuradas para el backend.         |
| `8080:8000`                      | Publica la API en el puerto `8080` del equipo anfitrión.                   |

---

# 7. Variables de entorno de Docker Compose y FastAPI

Es importante distinguir entre las variables utilizadas por `init_tables.py` y las que utiliza el backend.

Aunque ambos servicios se comunican con DynamoDB, no necesariamente obtienen su configuración de la misma fuente.

## 7.1. Variables del inicializador

El servicio `dynamodb-init` recibe su configuración mediante la sección `environment` de Docker Compose.

La configuración utilizada incluye:

```yaml
environment:
  DYNAMODB_ENDPOINT_URL: http://dynamodb-local:8000
  AWS_REGION: us-east-1
  AWS_ACCESS_KEY_ID: local
  AWS_SECRET_ACCESS_KEY: local
```

Estas variables se entregan al proceso Python cuando Docker Compose ejecuta el contenedor.

El script las consulta mediante `os.getenv()` y utiliza los valores predeterminados establecidos en el propio código cuando corresponde.

## 7.2. Variables del backend

El servicio `api` utiliza:

```yaml
env_file:
  - ./backend/.env
```

Esta configuración indica a Docker Compose que cargue las variables definidas en `backend/.env` y las proporcione al contenedor de la API.

Además, el servicio configura el endpoint de DynamoDB Local:

```yaml
environment:
  DYNAMODB_ENDPOINT_URL: http://dynamodb-local:8000
```

La configuración efectiva del backend depende de las variables declaradas en su archivo `.env` y de cualquier valor que se defina explícitamente en `environment`.

Cuando una misma variable está presente en ambas fuentes, las reglas de precedencia de Docker Compose determinan cuál se utiliza.

### ¿Por qué no debe asumirse que ambos servicios usan las mismas variables?

Porque cada servicio tiene su propia configuración.

* El inicializador recibe las variables declaradas en su servicio.
* La API recibe las variables del archivo `.env` y las que se configuran explícitamente en Compose.

Si se modifica la configuración de uno de los servicios, no se debe asumir que el otro cambiará automáticamente.

Para conocer todas las variables requeridas por FastAPI, se debe revisar `backend/.env.example`, `backend/.env` y el código del backend que las consulta.

No deben copiarse credenciales reales en la documentación ni compartirse archivos `.env` que contengan secretos.

---

# 8. Tutorial: cómo preparar el entorno de TraceHunt

Esta sección explica cómo reproducir el proceso de inicialización en otro equipo.

## 8.1. Requisitos previos

Antes de comenzar, el compañero debe contar con:

* Git.
* Docker Desktop instalado y en ejecución.
* Docker Compose disponible mediante el comando `docker compose`.
* Python y las dependencias requeridas dentro de la imagen del backend.
* Acceso al repositorio de TraceHunt.
* Los archivos JSON de definición de las tablas.
* La configuración de entorno necesaria para ejecutar FastAPI.

En Windows se pueden ejecutar los comandos de las siguientes secciones desde PowerShell.

### Verificar Git

```powershell
git --version
```

Este comando muestra la versión de Git instalada.

### Verificar Docker

```powershell
docker --version
```

Este comando muestra la versión del cliente Docker.

### Verificar Docker Compose

```powershell
docker compose version
```

Este comando comprueba que Docker Compose está disponible.

Si alguno de estos comandos falla, se debe resolver el problema de instalación antes de continuar.

---

## 8.2. Obtener el repositorio

Si el compañero todavía no tiene el repositorio, puede clonarlo:

```powershell
git clone git@github.com:DavidMaldonado0828/tracehunt.git
```

Este comando descarga el repositorio utilizando SSH.

Para que funcione, el usuario debe tener acceso al repositorio y una clave SSH configurada en GitHub.

Si no tiene acceso SSH, puede utilizar el método de clonación autorizado por el equipo.

Después, debe entrar en la carpeta del proyecto:

```powershell
cd tracehunt
```

Este comando cambia el directorio actual al repositorio.

Si ya tiene el repositorio clonado, no necesita ejecutar nuevamente `git clone`.

## 8.3. Seleccionar la rama que contiene la implementación

La funcionalidad se desarrolló en la rama:

```text
feat/automate-dynamodb-inicializacion
```

Si el equipo todavía no ha integrado el Pull Request en su rama principal de desarrollo, el compañero puede consultar y cambiar a esa rama:

```powershell
git fetch origin
git switch --track origin/feat/automate-dynamodb-inicializacion
```

El primer comando actualiza la información de las ramas remotas.

El segundo crea una rama local que sigue a la rama remota indicada.

Si la rama local ya existe, no debe utilizarse ciegamente el segundo comando: primero hay que comprobar el estado de la rama actual.

Si el Pull Request ya fue fusionado, lo recomendable es utilizar la rama de integración que indique el equipo y actualizarla desde el repositorio remoto.

No se debe asumir que la rama correcta es `main` o `develop` sin confirmar el flujo de trabajo del equipo.

## 8.4. Comprobar los archivos necesarios

Desde la raíz del repositorio, se pueden consultar los archivos relevantes:

```powershell
Get-ChildItem .\dynamodb
```

Este comando muestra el contenido de la carpeta `dynamodb`.

Se deben encontrar el inicializador y los archivos JSON correspondientes.

Para comprobar específicamente el script:

```powershell
Test-Path .\dynamodb\init_tables.py
```

El resultado esperado es:

```text
True
```

Para comprobar uno de los archivos de definición:

```powershell
Test-Path .\dynamodb\create-users.json
```

El resultado esperado también es:

```text
True
```

Se debe comprobar que existan los cinco archivos JSON descritos en la sección 2.2.

## 8.5. Revisar la configuración del backend

Antes de iniciar la API, el compañero debe revisar las instrucciones del proyecto y comprobar si necesita crear su propio archivo:

```text
backend/.env
```

El servicio `api` utiliza ese archivo mediante `env_file`.

No se debe copiar directamente un archivo `.env` con secretos de otro desarrollador.

Si el repositorio proporciona un archivo de ejemplo, debe utilizarse como referencia y completar los valores que correspondan al entorno local.

Las variables necesarias para el backend dependen de su implementación actual. La configuración de `init_tables.py` no reemplaza las demás variables que pueda requerir FastAPI.

---

# 9. Tutorial de ejecución paso a paso

## Paso 1. Validar la configuración de Docker Compose

Desde la raíz del repositorio, ejecutar:

```powershell
docker compose config --quiet
```

Este comando valida la configuración de Compose.

Si no muestra errores, la configuración pudo interpretarse correctamente.

Esto ayuda a detectar problemas de sintaxis o de configuración antes de iniciar los contenedores.

Sin embargo, que este comando termine correctamente no garantiza que la aplicación vaya a funcionar: todavía deben comprobarse la construcción de la imagen, las dependencias, las conexiones y la inicialización.

## Paso 2. Construir las imágenes

Ejecutar:

```powershell
docker compose build
```

Este comando construye las imágenes definidas en el archivo de Compose que requieren construcción.

En esta implementación, el inicializador y la API utilizan la imagen construida desde `./backend`.

Durante la construcción, Docker procesa el Dockerfile del backend y prepara el entorno de ejecución.

Si el backend instala sus dependencias durante la construcción, este proceso también prepara las bibliotecas que necesita el inicializador, incluido Boto3.

La construcción puede tardar más la primera vez porque Docker necesita descargar imágenes base e instalar dependencias.

**Resultado esperado:** el comando finaliza sin errores de construcción.

## Paso 3. Iniciar los servicios

Ejecutar:

```powershell
docker compose up
```

Este comando inicia los servicios definidos en Compose.

El proceso previsto es:

1. Docker Compose inicia `dynamodb-local`.
2. Se ejecuta `dynamodb-init` cuando su dependencia está disponible.
3. El inicializador espera a que DynamoDB responda.
4. Comprueba qué tablas existen.
5. Crea las tablas ausentes y espera a que estén activas.
6. El inicializador termina con código `0` si el proceso finaliza correctamente.
7. Docker Compose permite iniciar `api` porque la condición `service_completed_successfully` se ha satisfecho.

La terminal mostrará los registros de los servicios.

Si se ejecuta en primer plano, los registros permanecerán visibles mientras los servicios continúen ejecutándose.

Para detener los servicios iniciados en primer plano, se puede utilizar `Ctrl + C`. Después, se debe comprobar el estado de los contenedores.

### ¿Qué se debe observar en los registros?

En el servicio inicializador, se deben buscar mensajes que indiquen:

* Que DynamoDB está disponible.
* Que las tablas existentes fueron detectadas.
* Que las tablas necesarias están en estado `ACTIVE`.
* Que el inicializador terminó correctamente.

Si una tabla no existe, el registro debe reflejar el intento de creación correspondiente.

En el servicio `api`, se deben buscar los mensajes que indiquen que FastAPI terminó su proceso de inicio y que Uvicorn está escuchando en el puerto configurado.

## Paso 4. Ejecutar los servicios en segundo plano

Si se prefiere recuperar inmediatamente la terminal, se puede utilizar:

```powershell
docker compose up -d
```

El parámetro `-d` indica que los contenedores se ejecuten en segundo plano.

Esto permite continuar utilizando PowerShell sin mantener los registros ocupando la terminal.

Si se utiliza este modo, se recomienda ejecutar los siguientes comandos para verificar el estado de los servicios.

## Paso 5. Comprobar el estado de los contenedores

Ejecutar:

```powershell
docker compose ps
```

Este comando muestra el estado de los contenedores administrados por Compose.

Se espera que:

* `dynamodb-local` permanezca en ejecución.
* `api` permanezca en ejecución si el arranque fue exitoso.
* `dynamodb-init` aparezca como finalizado correctamente cuando la inicialización termine.

**Importante:** que `dynamodb-init` aparezca como finalizado no significa que haya fallado.

Este servicio está diseñado para ejecutar una tarea puntual. Su objetivo no es permanecer en ejecución, sino terminar después de inicializar las tablas.

Un contenedor inicializador que termina correctamente es el comportamiento esperado.

## Paso 6. Consultar los registros

Para revisar los registros de los servicios:

```powershell
docker compose logs
```

Este comando muestra los registros disponibles de los servicios administrados por Compose.

Para observarlos en tiempo real:

```powershell
docker compose logs -f
```

El parámetro `-f` permite seguir los registros a medida que se generan.

Para revisar únicamente los registros del inicializador:

```powershell
docker compose logs dynamodb-init
```

Para revisar los registros de FastAPI:

```powershell
docker compose logs api
```

Estos comandos ayudan a identificar en qué parte del proceso ocurre un problema.

## Paso 7. Comprobar la documentación de FastAPI

Con la API en ejecución, abrir en el navegador:

```text
http://localhost:8080/docs
```

Esta dirección corresponde a la documentación interactiva de FastAPI publicada en el puerto `8080` del equipo anfitrión.

Si la documentación se muestra correctamente, significa que la API está respondiendo en esa dirección.

Esto no garantiza por sí solo que todos los endpoints funcionen ni que todas las operaciones de DynamoDB estén correctamente configuradas. Es una comprobación inicial del servicio HTTP.

También se puede realizar una comprobación básica desde PowerShell:

```powershell
Invoke-RestMethod http://localhost:8080/docs
```

Este comando envía una solicitud HTTP al endpoint y muestra la respuesta si la solicitud tiene éxito.

## Paso 8. Comprobar las tablas de DynamoDB

Durante las pruebas de esta implementación, las cinco tablas ya existían en la instancia local y el inicializador las detectó.

Para reproducir una comprobación similar, se puede utilizar AWS CLI si está instalado y configurado para conectarse a DynamoDB Local.

Por ejemplo:

```powershell
aws dynamodb list-tables --endpoint-url http://localhost:8000 --region us-east-1
```

Este comando solicita la lista de tablas al endpoint local.

Los argumentos cumplen estas funciones:

| Argumento                              | Función                                    |
| -------------------------------------- | ------------------------------------------ |
| `aws dynamodb list-tables`             | Solicita la lista de tablas.               |
| `--endpoint-url http://localhost:8000` | Dirige la solicitud a DynamoDB Local.      |
| `--region us-east-1`                   | Establece la región utilizada por AWS CLI. |

La salida debe incluir las tablas que existan en esa instancia, entre ellas las cinco administradas por el inicializador.

El comando utiliza el endpoint del equipo anfitrión. No debe confundirse con la dirección `http://dynamodb-local:8000`, que se utiliza para la comunicación entre contenedores.

Si AWS CLI no está instalado, esta comprobación no podrá realizarse con ese comando. En ese caso, se pueden revisar los registros del inicializador y utilizar las herramientas de desarrollo disponibles en el proyecto.

---

# 10. ¿Cómo se comporta el inicializador en diferentes situaciones?

## 10.1. Todas las tablas ya existen

El inicializador consulta las tablas y reconoce que ya están presentes.

No necesita solicitar su creación nuevamente.

Después de verificar que se encuentran en el estado requerido, termina correctamente.

Este fue el escenario observado durante la validación de esta implementación.

## 10.2. Falta una o varias tablas

El inicializador utiliza los archivos JSON para solicitar la creación de las tablas que faltan.

Después, espera a que alcancen el estado `ACTIVE`.

Si todas las operaciones finalizan correctamente, el inicializador termina con código `0` y Compose puede iniciar la API.

## 10.3. DynamoDB tarda en iniciar

El inicializador realiza reintentos de comprobación según los límites configurados.

Esto permite tolerar retrasos normales en el arranque.

Si DynamoDB no está disponible después de agotar los intentos, el inicializador debe finalizar con un error.

En ese caso, no se cumple la condición requerida para iniciar la API.

## 10.4. Un archivo JSON no está disponible

Si el script no puede leer uno de los archivos JSON requeridos, no podrá obtener la definición correspondiente.

Esto debe considerarse un error de inicialización.

Se debe comprobar que:

* El archivo exista.
* El nombre coincida con el utilizado por el script.
* El archivo esté montado correctamente en el contenedor.
* El JSON tenga una estructura válida.
* La definición sea compatible con la operación de creación de tablas.

## 10.5. Una tabla no puede crearse

La creación puede fallar por problemas de conexión, definiciones inválidas u otros errores de DynamoDB.

En ese escenario, se deben revisar los registros del inicializador.

No se debe asumir que la API se ha inicializado correctamente si el servicio `dynamodb-init` terminó con un código de salida distinto de `0`.

---

# 11. ¿Cómo comprobar que la automatización funciona?

La validación debe distinguir entre comprobar que el inicializador detecta tablas existentes y comprobar que crea tablas ausentes.

Son dos escenarios diferentes.

## 11.1. Validación de tablas existentes

En la sesión de desarrollo se ejecutaron los servicios con:

```powershell
docker compose up
```

Los registros mostraron que las cinco tablas siguientes ya existían:

* `Users`
* `Events`
* `Alerts`
* `AuditLogs`
* `Simulations`

El inicializador informó que las tablas estaban en estado `ACTIVE` y terminó con código `0`.

Después, la API inició correctamente.

También se comprobó la disponibilidad de la documentación en:

```text
http://localhost:8080/docs
```

Esta prueba valida el reconocimiento de tablas existentes, la finalización exitosa del inicializador y la coordinación del arranque de la API.

## 11.2. Validación de creación de tablas ausentes

**Limitación de las pruebas documentadas:** durante la validación descrita, las cinco tablas ya existían.

Por tanto, no se debe afirmar que se comprobó de forma independiente la creación de una tabla ausente.

Para validar ese comportamiento en el futuro, se debe preparar un entorno de prueba aislado en el que falte una de las tablas y comprobar que:

1. El inicializador detecta su ausencia.
2. Lee el archivo JSON correspondiente.
3. Solicita la creación de la tabla.
4. Espera a que la tabla alcance el estado `ACTIVE`.
5. Finaliza con código `0`.
6. La API inicia correctamente.

La prueba debe realizarse de manera controlada para no borrar datos importantes del entorno de desarrollo compartido.

No se deben eliminar tablas ni modificar el archivo local de datos de DynamoDB sin confirmar primero qué información contiene y qué impacto tendría la operación.

---

# 12. Problemas frecuentes y diagnóstico

## 12.1. La API no inicia

Comprobar los registros:

```powershell
docker compose logs api
```

Este comando permite revisar los errores que se hayan producido durante el arranque de FastAPI.

Si el inicializador falló, consultar también:

```powershell
docker compose logs dynamodb-init
```

La API puede no iniciar porque la inicialización previa no finalizó correctamente.

## 12.2. DynamoDB no responde

Comprobar el estado de los servicios:

```powershell
docker compose ps
```

Después, revisar los registros de DynamoDB Local:

```powershell
docker compose logs dynamodb-local
```

Si el servicio no está disponible, se deben revisar los errores de Docker y comprobar la configuración del puerto.

## 12.3. El inicializador no encuentra los archivos JSON

Comprobar que los archivos estén presentes en el repositorio:

```powershell
Get-ChildItem .\dynamodb
```

Después, revisar el montaje configurado en el servicio `dynamodb-init`:

```yaml
volumes:
  - ./dynamodb:/dynamodb:ro
```

El script se ejecuta en el contenedor utilizando la ruta:

```text
/dynamodb/init_tables.py
```

Por tanto, el montaje debe permitir que esa ruta y los archivos JSON requeridos estén disponibles.

## 12.4. El inicializador se ejecuta, pero no crea tablas

Que el inicializador no cree tablas no significa necesariamente que haya un error.

Si las tablas ya existen, el comportamiento esperado es reconocerlas y continuar sin intentar crearlas nuevamente.

Se deben revisar los registros para distinguir entre:

* Tablas detectadas como existentes.
* Tablas creadas durante la ejecución.
* Errores durante la creación.
* Errores al verificar el estado de las tablas.

## 12.5. `docker compose config --quiet` muestra un error

Comprobar:

* La sintaxis YAML.
* La indentación.
* Los nombres de los servicios.
* La ubicación de los archivos referenciados.
* Las condiciones de `depends_on`.
* Las rutas de los volúmenes.
* Las variables y archivos de entorno configurados.

Este comando es útil para detectar problemas de configuración antes de iniciar los servicios.

---

# 13. Comandos principales de referencia

Todos los comandos de esta sección deben ejecutarse desde la raíz del repositorio, salvo que se indique lo contrario.

| Comando                                                                            | Propósito                                                 |
| ---------------------------------------------------------------------------------- | --------------------------------------------------------- |
| `docker compose config --quiet`                                                    | Validar la configuración de Docker Compose.               |
| `docker compose build`                                                             | Construir las imágenes necesarias.                        |
| `docker compose up`                                                                | Iniciar los servicios y mostrar los registros.            |
| `docker compose up -d`                                                             | Iniciar los servicios en segundo plano.                   |
| `docker compose ps`                                                                | Consultar el estado de los contenedores.                  |
| `docker compose logs`                                                              | Consultar los registros.                                  |
| `docker compose logs -f`                                                           | Seguir los registros en tiempo real.                      |
| `docker compose logs dynamodb-init`                                                | Consultar los registros del inicializador.                |
| `docker compose logs dynamodb-local`                                               | Consultar los registros de DynamoDB Local.                |
| `docker compose logs api`                                                          | Consultar los registros de FastAPI.                       |
| `docker compose down`                                                              | Detener y retirar los contenedores y la red del proyecto. |
| `aws dynamodb list-tables --endpoint-url http://localhost:8000 --region us-east-1` | Consultar las tablas de DynamoDB Local mediante AWS CLI.  |

### Precaución con `docker compose down`

Este comando detiene y elimina los contenedores y la red creada por Compose.

Sin embargo, la conservación de los datos depende de cómo esté configurado el almacenamiento.

En esta implementación, los datos locales están asociados al directorio `./docker/dynamodb`.

No se debe utilizar ninguna opción que elimine volúmenes ni borrar manualmente ese directorio sin comprobar primero qué datos contiene.

El archivo `docker/dynamodb/shared-local-instance.db` puede contener datos locales que deban conservarse.

---

# 14. Evidencias de validación

Durante el desarrollo se recopilaron capturas de pantalla que documentan el proceso de construcción, ejecución y comprobación.

Las evidencias se encuentran en:

```text
docs/evidencias/
```

Los archivos incorporados son:

| Archivo                                   | Propósito                                                                                      |
| ----------------------------------------- | ---------------------------------------------------------------------------------------------- |
| `docker-compose-build.png`                | Evidencia de la construcción de Docker.                                                        |
| `docker-compose-up.png`                   | Evidencia de la ejecución de los servicios.                                                    |
| `docker-compose-logs-f__VerRegistros.png` | Evidencia de la consulta de los registros.                                                     |
| `lectura_de_tablas_inicializador.png`     | Evidencia relacionada con la lectura o verificación de las tablas por parte del inicializador. |
| `README.md`                               | Documentación que organiza las evidencias.                                                     |

Estas capturas complementan los registros de ejecución y permiten consultar visualmente las comprobaciones realizadas.

Las evidencias documentan la ejecución observada durante las pruebas; no deben interpretarse como prueba de escenarios que no se ejecutaron, como la creación independiente de una tabla ausente.

---

# 15. Relación con el Pull Request

La implementación se publicó en la rama:

```text
feat/automate-dynamodb-inicializacion
```

El Pull Request incluye los cambios de automatización y la documentación de evidencias.

Los commits publicados fueron:

| Commit    | Descripción                                    |
| --------- | ---------------------------------------------- |
| `a604d06` | `feat: automate DynamoDB table initialization` |
| `3235265` | `docs: add DynamoDB automation evidence`       |

El alcance de los cambios incluye:

* El script `dynamodb/init_tables.py`.
* La configuración de `docker-compose.yml`.
* La integración del inicializador en el arranque de la API.
* Las capturas y la documentación de evidencias.

No se incorporó al Pull Request el cambio local del archivo:

```text
docker/dynamodb/shared-local-instance.db
```

Este archivo se mantuvo fuera de los commits para conservar los datos locales del entorno de desarrollo.

---

# 16. Conclusiones

La implementación permite automatizar la preparación de las tablas de DynamoDB utilizadas por TraceHunt.

El inicializador:

1. Obtiene la configuración de conexión.
2. Espera a que DynamoDB esté disponible.
3. Comprueba qué tablas existen.
4. Utiliza las definiciones JSON para crear las tablas ausentes.
5. Verifica que las tablas estén activas.
6. Finaliza indicando si la inicialización fue exitosa.

Por su parte, `docker-compose.yml` coordina los servicios y garantiza que la API espere a que la inicialización termine correctamente.

Esto reduce la preparación manual del entorno y facilita que los integrantes del equipo reproduzcan el proceso de arranque.

La validación realizada confirmó que el inicializador reconoció las cinco tablas existentes, verificó su estado `ACTIVE`, finalizó con código `0` y permitió que FastAPI iniciara correctamente.

Como siguiente validación técnica, queda comprobar de forma independiente el escenario en el que falta una tabla y el inicializador debe crearla.

**Resultado esperado:** que un integrante del equipo pueda preparar el entorno local de TraceHunt, ejecutar Docker Compose, observar el proceso de inicialización y acceder a la documentación de FastAPI sin tener que crear manualmente las tablas existentes o ausentes.
