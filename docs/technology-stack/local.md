# Componentes tecnológicos de TraceHunt

TraceHunt utiliza una arquitectura local basada en contenedores Docker, donde el backend, la base de datos y el proceso de inicialización se ejecutan como servicios independientes.

## 1. Tecnologías principales

| Tecnología | Función dentro del proyecto |
|---|---|
| **Python** | Lenguaje utilizado para implementar la lógica del backend, las reglas de detección y el simulador de eventos. |
| **FastAPI** | Framework encargado de construir la API REST, gestionar las peticiones HTTP y exponer los endpoints del sistema. |
| **Boto3** | SDK de AWS para Python utilizado para interactuar con DynamoDB mediante operaciones de consulta, inserción, actualización y eliminación. |
| **DynamoDB Local** | Base de datos NoSQL que permite almacenar usuarios, eventos, alertas, auditorías y simulaciones sin depender de los servicios en la nube. |
| **Docker** | Tecnología de contenedorización utilizada para empaquetar y ejecutar los componentes del sistema en entornos aislados. |
| **Docker Compose** | Herramienta que permite definir, configurar y coordinar los servicios necesarios para ejecutar TraceHunt localmente. |
| **HTML, CSS y JavaScript** | Tecnologías utilizadas para construir la interfaz web con la que los usuarios interactúan con el sistema. |

## 2. Componentes de la arquitectura

### API Backend y Frontend
Implementado con Python y FastAPI. Es el componente principal del sistema: recibe las solicitudes HTTP, ejecuta la lógica de negocio, aplica las reglas de detección y permite acceder a la interfaz web.

FastAPI también sirve los archivos estáticos del frontend mediante la ruta `/ui` y proporciona documentación interactiva de los endpoints mediante Swagger UI en `/docs`.

### Base de datos NoSQL
DynamoDB Local almacena la información del sistema. Su modelo de datos utiliza tablas independientes para usuarios, eventos, alertas, auditorías y simulaciones.

La interacción con la base de datos se realiza mediante Boto3, que permite ejecutar las operaciones necesarias desde Python.

### Servicio de inicialización
Se utiliza un contenedor independiente para ejecutar el script `init_tables.py`, encargado de leer los esquemas JSON del proyecto y crear las tablas que todavía no existen.

Este proceso permite preparar automáticamente la base de datos antes de iniciar el backend.

### Docker Compose
Coordina los servicios de la aplicación y establece sus configuraciones, variables de entorno, puertos, volúmenes y dependencias de ejecución.

De esta manera, los componentes pueden iniciarse mediante una configuración centralizada.

## 3. Comunicación entre componentes

El funcionamiento local sigue este flujo:

1. El usuario accede a la interfaz web desde el navegador mediante `http://localhost:8080/ui`.
2. El frontend realiza solicitudes HTTP a los endpoints de FastAPI.
3. FastAPI procesa las solicitudes y ejecuta la lógica correspondiente.
4. El backend utiliza Boto3 para comunicarse con DynamoDB Local.
5. DynamoDB Local almacena o devuelve la información solicitada.

El servicio de inicialización prepara las tablas antes de que el backend comience a ejecutarse.

## 4. Puertos de acceso

| Puerto | Componente | Acceso |
|---|---|---|
| `8080` | API FastAPI | `http://localhost:8080` |
| `8000` | DynamoDB Local | `http://localhost:8000` |

**Nota:** El frontend y la API comparten el mismo contenedor FastAPI. No se ejecutan como servicios independientes.

## 5. Ventajas de la arquitectura local

- **Portabilidad:** permite ejecutar el proyecto en diferentes equipos con Docker.
- **Aislamiento:** cada servicio funciona dentro de su propio contenedor.
- **Reproducibilidad:** Docker Compose facilita levantar el mismo entorno de desarrollo.
- **Independencia de la nube:** DynamoDB Local permite desarrollar y probar el sistema sin depender de una cuenta AWS.
- **Mantenimiento:** la separación de responsabilidades facilita identificar y modificar componentes sin afectar directamente a los demás.