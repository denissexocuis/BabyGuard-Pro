# Servidor Raspberry Pi

Este directorio contiene la configuración de infraestructura centralizada para **BabyGuard Pro**. Todo el ecosistema del servidor (Broker MQTT, Backend de Node-RED, Base de Datos MySQL y el Motor de IA en Python) corre de forma aislada y portátil utilizando **Docker**.

---

## ¿Qué hace este Docker?

Al levantar este Docker, se encienden 4 contenedores independientes que se comunican entre sí de forma interna:

1. **`bg_broker` (Eclipse Mosquitto):** El intermediario MQTT que recibe los JSON de telemetría ambiental (`babyguard/sensores`) y las alertas de IA.
2. **`bg_nodered` (Node-RED):** El backend visual (disponible en el puerto `1880`). Diseña el Dashboard, procesa las alertas, guarda en la base de datos y despacha los mensajes de emergencia al bot de Telegram.
3. **`bg_mysql` (MySQL 8.0):** La base de datos persistente encargada de almacenar el historial de logs de los sensores (`babyguard_db`).
4. **`bg_ia_motor` (Python 3.10 Slim):** El entorno que ejecuta el script de Inteligencia Artificial (`motor_ia.py`). Instala en automático OpenCV y MediaPipe para procesar el flujo de video.
---

## Requisitos Previos

Tener instalado **Docker Desktop** en tu sistema operativo antes de continuar:
- Windows / Mac: https://www.docker.com/products/docker-desktop
- Linux: https://docs.docker.com/engine/install/

---

## Cómo iniciar el entorno

### 1. Obtener los últimos cambios
```bash
git pull origin main
```

### 2. Configurar las variables de entorno
Antes de encender el servidor por primera vez, copia el archivo de ejemplo y llena tus credenciales reales:
```bash
cp .env.example .env
```

Abre el archivo `.env` y completa los valores:

```
TELEGRAM_TOKEN=pon_aqui_el_token_de_tu_bot
TELEGRAM_CHAT_ID=pon_aqui_tu_chat_id
MYSQL_ROOT_PASSWORD=pon_aqui_una_contrasena
MYSQL_DATABASE=babyguard_db
STREAM_URL=http://192.168.1.100:81/stream
```

> ⚠️ **NUNCA subas el archivo `.env` a GitHub.** Ya está en el `.gitignore`, pero por si las dudas, verifica antes de hacer commit.


### 3. Encender el servdor
Entra a esta carpeta en tu terminal y ejecuta el comando maestro:
```bash
docker compose up -d
```
La bandera `-d` (detached mode) hace que los servidores corran en segundo plano, liberando tu terminal.

### 3. Verificar que todo esté corriendo
Para comprobar que los 4 contenedores se descargaron y están corriendo correctamente, ejecuta:
 
```bash
docker ps
```
 
Deberías ver los 4 contenedores con el estatus `Up`:
 
```
CONTAINER ID   NAME            STATUS
xxxxxxxxxxxx   bg_broker       Up X seconds
xxxxxxxxxxxx   bg_nodered      Up X seconds
xxxxxxxxxxxx   bg_mysql        Up X seconds
xxxxxxxxxxxx   bg_ia_motor     Up X seconds
```

---

## Puertos disponibles para chambear
Una vez encendido el Docker, puedes acceder a los servicios desde tu navegador o herramientas de prueba:
 
| Servicio | Dirección | Para qué |
|---|---|---|
| Node-RED | http://localhost:1880 | Diseñar flujos y el Dashboard |
| Dashboard web | http://localhost:1880/ui | Ver el panel de monitoreo |
| Broker MQTT | localhost:1883 | Conectar MQTT X para pruebas |
| MySQL | localhost:3306 | Consultar la base de datos |

---
## Estructura de carpetas
 
```
servidor/
├── docker-compose.yml          ← archivo para docker
├── .env                        ← credenciales (NO subir a GitHub)
├── .env.example                ← plantilla de variables de entorno
├── ia_engine/
│   ├── motor_ia.py             ← REGLA: debe llamarse exactamente así el archivo de python
│   ├── bebe_test.mp4           ← video de prueba (NO subir a GitHub)
│   ├── requirements.txt        ← dependencias de Python
│   └── Dockerfile
├── nodered_data/               ← Node-RED guarda aquí sus configuraciones
│   └── flows.json              ← exportar desde Node-RED al terminar cambios
├── mysql/
│   └── init.sql                ← se ejecuta automáticamente al crear la BD
└── mosquitto/
    └── config/
        └── mosquitto.conf      ← permite conexiones externas en la red local
```

> **REGLA — IA:** El archivo principal de Python **obligatoriamente debe llamarse `motor_ia.py`**. El contenedor lo busca con ese nombre exacto al encenderse. Si se llama diferente, el contenedor arranca y no hace nada.

---
 
## Cómo apagar el entorno
 
```bash
docker compose down
```
 
Si además quieres borrar los datos guardados en MySQL (útil para empezar desde cero en pruebas):
 
```bash
docker compose down -v
```
 
> El flag `-v` borra los volúmenes. Usar solo si de verdad se quiere resetear la base de datos.
 
---
 
## Solución de problemas
 
**Ver los logs de un contenedor** (cuando algo no arranca):
 
```bash
docker compose logs bg_nodered
docker compose logs bg_ia_motor
docker compose logs bg_mysql
docker compose logs bg_broker
```
 
**Reiniciar un solo contenedor** sin apagar todo:
 
```bash
docker compose restart bg_ia_motor
```
 
**El contenedor de IA arranca y se cierra solo:**
Revisar que `motor_ia.py` existe en la carpeta `ia_engine/` y que el `STREAM_URL` en tu `.env` es accesible desde la red.
 
**Node-RED no guarda flujos:**
Exportar manualmente: menú `≡` → Export → All Flows → guarda como `nodered_data/flows.json` y haz commit.
 
**MySQL no arranca:**
Revisar que `MYSQL_ROOT_PASSWORD` esté definido en `.env`. Sin contraseña, el contenedor falla.
