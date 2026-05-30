# Servidor Raspberry Pi

[cite_start]Este directorio contiene la configuración de infraestructura centralizada para **BabyGuard Pro**[cite: 46, 55]. [cite_start]Todo el ecosistema del servidor (Broker MQTT, Backend de Node-RED, Base de Datos MySQL y el Motor de IA en Python) corre de forma aislada y portátil utilizando **Docker**[cite: 55].

---

## ¿Qué hace este Docker?

Al levantar este Docker, se encienden 4 contenedores independientes que se comunican entre sí de forma interna:

1. [cite_start]**`bg_broker` (Eclipse Mosquitto):** El intermediario MQTT que recibe los JSON de telemetría ambientales (`babyguard/sensores`) y las alertas de IA[cite: 62, 67, 73].
2. [cite_start]**`bg_nodered` (Node-RED):** El backend visual (disponible en el puerto `1880`). [cite_start]Diseña el Dashboard, procesa las alertas, guarda en la base de datos y despacha los mensajes de emergencia al bot de Telegram[cite: 74, 75, 78].
3. [cite_start]**`bg_mysql` (MySQL 8.0):** La base de datos persistente encargada de almacenar el historial de logs de los sensores (`babyguard_db`)[cite: 78].
4. [cite_start]**`bg_ia_motor` (Python 3.10 Slim):** El entorno que ejecuta el script de Inteligencia Artificial (`motor_ia.py`). [cite_start]Instala en automático OpenCV y MediaPipe para procesar el flujo de video.

---

## Requisitos Previos (Instalación)

Asegúrate de tener instalado Docker en tu sistema operativo.

## Cómo iniciar el entorno

### 1. Obtener los últimos cambios
```bash
git pull origin main
```
