# Evidencias de verificación

>Este directorio está reservado para evidencias reproducibles de tareas completadas, como resultados de pruebas, capturas o instrucciones breves para repetir una validación.


## Evidencias: Dockerización de la API de TraceHunt

### Objetivo

Empaquetar la API de TraceHunt en una imagen Docker para ejecutarla dentro de un contenedor, facilitando su despliegue en diferentes entornos sin depender de las instalaciones locales de Python y sus dependencias.

### Procedimiento realizado

Inicialmente, se verificó el funcionamiento de Docker mediante la ejecución de `docker run hello-world`. Esta prueba permitió comprobar que Docker podía descargar una imagen, crear un contenedor y ejecutarlo correctamente.

![Prueba de funcionamiento de Docker con Hello World](hello-worldDocker.jpg)

Posteriormente, se construyó la imagen Docker de la API de TraceHunt a partir del archivo `Dockerfile`. Durante este proceso se utilizó una imagen base de Python 3.12 Slim, se estableció el directorio de trabajo `/app`, se instalaron las dependencias definidas en `requirements.txt` y se incorporó el código de la aplicación. Finalmente, se configuró Uvicorn como comando de inicio para ejecutar FastAPI en el puerto 8000 dentro del contenedor.

![Construcción de la imagen Docker de la API](buildAPIDocker.jpg)

Una vez construida la imagen, se ejecutó la API mediante un contenedor Docker, publicando el puerto 8000 del contenedor en el puerto 8080 del equipo anfitrión. Se verificó el estado del contenedor y se consultaron los registros de ejecución para comprobar que Uvicorn iniciara correctamente. Además, se realizaron solicitudes a los endpoints `/health` y `/docs`, obteniendo respuestas HTTP 200 OK.

![Ejecución y verificación de la API en Docker](runApiDocker.jpg)

### Resultado

La tarea permitió construir una imagen Docker de la API de TraceHunt y ejecutarla en un contenedor funcional. Se comprobó el acceso a los endpoints mediante el puerto publicado y se verificó el inicio correcto del servidor. Con ello, se cumplió el objetivo de ejecutar la API en Docker.


## Evidencias: Orquestación de TraceHunt con Docker Compose

### Objetivo

Configurar y ejecutar conjuntamente la API de TraceHunt y DynamoDB Local mediante Docker Compose, definiendo sus servicios, variables de entorno, puertos, red de comunicación y almacenamiento persistente.

### Procedimiento realizado

Inicialmente, se verificó la configuración definida en el archivo `docker-compose.yml` mediante el comando `docker compose config`. Esta validación permitió comprobar la configuración de los servicios `api` y `dynamodb-local`, las variables de entorno, los puertos publicados y el volumen utilizado para almacenar los datos de DynamoDB Local.

![Validación de la configuración de Docker Compose](dockerComposeConfig.png)

Posteriormente, se ejecutó el comando `docker compose up --build` para construir la imagen de la API y levantar los servicios definidos. Docker Compose descargó la imagen `amazon/dynamodb-local`, construyó la imagen de TraceHunt a partir del `Dockerfile` y creó los contenedores y la red compartida para permitir la comunicación entre ambos servicios.

![Construcción y ejecución de los servicios mediante Docker Compose](dockerComposeUp.png)

Durante el inicio, se verificó en los registros que DynamoDB Local se inicializara en el puerto 8000 y que Uvicorn iniciara correctamente la API dentro de su contenedor. La API quedó accesible desde el equipo anfitrión mediante el puerto 8080, mientras que la conexión interna con DynamoDB Local se configuró mediante la dirección `http://dynamodb-local:8000`.

Finalmente, se consultó el estado de los servicios mediante `docker compose ps`, comprobando la creación de los contenedores y sus puertos publicados.

![Estado de los servicios de TraceHunt en Docker Compose](dockerComposePs.png)

### Resultado

Se configuró la orquestación local de TraceHunt mediante Docker Compose, integrando la API y DynamoDB Local en una misma red. La configuración permite iniciar ambos servicios con un único comando y establece el almacenamiento persistente para los datos de la base de datos local. Los registros confirmaron el inicio de los procesos de la API y de DynamoDB Local.

Esta evidencia demuestra la configuración y el arranque de los servicios. La comunicación funcional entre la API y DynamoDB Local debe validarse adicionalmente mediante una operación real de lectura o escritura.