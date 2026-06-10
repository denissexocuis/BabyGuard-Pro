# usar la base de Python
FROM python:3.10-slim

# la carpeta de trabajo dentro del contenedor
WORKDIR /app

# instalar todas las librerías del sistema necesarias para OpenCV y audio
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    alsa-utils \
    portaaudio19-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /app/alertas

# instalar las librerías de Python
RUN pip install --no-cache-dir \
    opencv-python-headless \
    mediapipe==0.10.14 \
    paho-mqtt \
    flask \
    pyaudio

# copiar todo el código de la IA dentro del contenedor
COPY . .

# comando final que enciende el motor de video al instante
CMD ["python", "motor_ia.py"]
