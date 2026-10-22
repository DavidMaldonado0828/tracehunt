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


