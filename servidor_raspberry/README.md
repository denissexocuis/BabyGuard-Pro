# Servidor Raspberry Pi

Este directorio contiene la configuración de infraestructura centralizada para **BabyGuard Pro**. Todo el ecosistema del servidor (Broker MQTT, Backend de Node-RED, Base de Datos MySQL y el Motor de IA en Python) corre de forma aislada y portátil utilizando **Docker**.

---

## ¿Qué hace este Docker?

Al levantar este Docker, se encienden 4 contenedores independientes que se comunican entre sí de forma interna:

1. **`bg_broker` (Eclipse Mosquitto):** El intermediario MQTT que recibe los JSON de telemetría ambientales (`babyguard/sensores`) y las alertas de IA.
2. **`bg_nodered` (Node-RED):** El backend visual (disponible en el puerto `1880`). Diseña el Dashboard, procesa las alertas, guarda en la base de datos y despacha los mensajes de emergencia al bot de Telegram.
3. **`bg_mysql` (MySQL 8.0):** La base de datos persistente encargada de almacenar el historial de logs de los sensores (`babyguard_db`).
4. **`bg_ia_motor` (Python 3.10 Slim):** El entorno que ejecuta el script de Inteligencia Artificial (`motor_ia.py`). Instala en automático OpenCV y MediaPipe para procesar el flujo de video.

---

## Requisitos Previos (Instalación)

Asegúrate de tener instalado Docker en tu sistema operativo.

## Cómo iniciar el entorno

### 1. Obtener los últimos cambios
```bash
git pull origin main
```

### 2. Encender el servdor
Entra a esta carpeta en tu terminal y ejecuta el comando maestro:
```bash
docker compose up -d
```
La bandera -d (detached mode) hace que los servidores corran en segundo plano, liberando tu terminal.

### 3. Verificar que todo esté
Para comprobar que los 4 contenedores se descargaron y están corriendo correctamente, ejecuta:
```bash
docker ps
```
Deberías ver los contenedores **`bg_broker`, **`bg_nodered`, **`bg_mysql` y **`bg_ia_motor` con el estatus Up.

## Puertos disponibles para chambear
Una vez encendido el Docker, puedes acceder a los servicios desde tu navegador o herramientas de pruebas usando las siguientes direcciones:

- Node-RED (Interfaz de Desarrollo): http://localhost:1880
- Broker MQTT (Mosquitto): localhost:1883
- Base de Datos MySQL: localhost:3306

----
- ./ia_engine/: Aquí se programa la IA. REGLA CRÍTICA: El archivo principal obligatorio debe llamarse motor_ia.py para que el contenedor lo ejecute en automático al encender.
- ./nodered_data/: Aquí se guardan en automático las paletas de nodos y configuraciones. Los flujos finales deben exportarse como flows.json.
- ./mosquitto/config/mosquitto.conf: Archivo de configuración del broker para permitir conexiones externas en la red local.

## Como apaagar el entorno
```bash
docker compose down
```
