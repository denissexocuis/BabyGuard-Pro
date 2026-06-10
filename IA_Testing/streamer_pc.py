import cv2
import requests
import time

# --- CONFIGURACIÓN ---
# ¡Cambia esto por la IP que la ESP32 te dé en el Monitor Serial!
ESP32_URL = "http://10.220.244.165:81/upload"
FUENTE_VIDEO = 2 # Tu cámara IR en la PC

# Límite de FPS (10 es ideal para no saturar al microcontrolador)
TARGET_FPS = 10
delay = 1.0 / TARGET_FPS

cap = cv2.VideoCapture(FUENTE_VIDEO)

print(f"Iniciando transmisión activa hacia la ESP32 en: {ESP32_URL}")

while True:
    start_time = time.time()
    success, frame = cap.read()
    
    if not success:
        print("Error leyendo la cámara IR de la PC.")
        break
        
    # 1. SÚPER LIGERO: Reducimos resolución para salvar la RAM de la ESP32
    frame_resized = cv2.resize(frame, (320, 240))
    
    # 2. SÚPER COMPRIMIDO: Calidad JPEG al 30%
    ret, buffer = cv2.imencode('.jpg', frame_resized, [cv2.IMWRITE_JPEG_QUALITY, 30])
    
    if ret:
        try:
            # 3. DISPARO A ESP32: Enviamos la imagen cruda por POST
            # Usamos un timeout súper corto para que el código no se congele si la red falla
            requests.post(ESP32_URL, data=buffer.tobytes(), headers={'Content-Type': 'image/jpeg'}, timeout=0.5)
        except requests.exceptions.RequestException:
            pass # Ignoramos errores de red para mantener la fluidez
            
    # cv2.imshow("Monitor Local PC (Cámara IR)", frame_resized)
    if cv2.waitKey(1) & 0xFF == 27:
        break

    # Pausa inteligente para mantener los FPS estables
    elapsed = time.time() - start_time
    if elapsed < delay:
        time.sleep(delay - elapsed)

cap.release()
cv2.destroyAllWindows()