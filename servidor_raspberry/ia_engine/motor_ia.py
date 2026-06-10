import os
os.environ["DISPLAY"] = ""

import cv2
import mediapipe as mp
import time
import base64
import json
import paho.mqtt.client as mqtt
import math
import threading
import glob
from flask import Flask, Response

# FLASK - servidor de stream
app = Flask(__name__)
output_frame = None
lock = threading.Lock()
 
def generate_stream():
    global output_frame
    while True:
        with lock:
            if output_frame is None:
                continue
            ret, buffer = cv2.imencode('.jpg', output_frame)
            if not ret:
                continue
            frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
 
@app.route('/video')
def video():
    return Response(generate_stream(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')
 
def run_flask():
    app.run(host='0.0.0.0', port=8081, threaded=True)
 
# Iniciar Flask en un hilo separado
flask_thread = threading.Thread(target=run_flask)
flask_thread.daemon = True
flask_thread.start()

# MQTT
#MQTT_BROKER = "127.0.0.1" # para localhost
MQTT_BROKER = "broker"
MQTT_PORT = 1883
MQTT_TOPIC = "babyguard/alertas/camara"

print("Conectando al Broker MQTT local de BabyGuard...")
mqtt_client = mqtt.Client()
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
mqtt_client.loop_start()


# MEDIAPIPE
# Fuente para el stream del video y uso de camara de la esp (ahi ya toca poner el topico donde se haga stream del video)
# FUENTE_VIDEO = "Media/Test/Videos/baby_4.mp4"
FUENTE_VIDEO = 0

# Camara infrarroja de la pc
URL_ESP32 = "http://10.97.203.75:81/stream"
cap_pc = cv2.VideoCapture(URL_ESP32)

mp_holistic = mp.solutions.holistic
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

# camara externa usb
cap = cv2.VideoCapture(FUENTE_VIDEO)

def calcular_distancia(p1, p2):
    return math.hypot(p2.x - p1.x, p2.y - p1.y)

# Variables de estado
tiempo_sin_rostro = None
tiempo_mala_postura = None
tiempo_ultima_alerta = 0
cooldown_alertas = 5
segundos_limite = 1.5

print(f"Iniciando BabyGuard Pro - Face Mesh Monitor: {FUENTE_VIDEO}")
#print("Presiona 'ESC' en la ventana de video para salir")

framerate = 100 # configuracion virtual de framerate
frames_a_skippear = 1 # configuracion de cuantos frames quiero saltar
# por ejemplo frames_a_skippear = 1, proceso 1 salto 1 proceso 1 salto 1 - procesamiento vs real 1/2=50%
# por ejemplo frames_a_skippear = 2, proceso 1 salto 2 proceso 1 salto 2 - procesamiento 1/3=33%
# por ejemplo frames_a_skippear = 3, proceso 1 salto 3 proceso 1 salto 3 - procesamiento 1/4=25%

delay = 1 / float(framerate)
contador = 0

# Bandera para alternar el procesamiento entre las dos cámaras
turno_camara_local = True

print("Iniciando BabyGuard Pro - Monitor Dual (Día/Noche)")

with mp_holistic.Holistic(
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5) as holistic_model:
    
    while True:
        # Siempre leemos AMBAS cámaras para vaciar el buffer y evitar lag
        success_local, frame_local = cap_local.read()
        success_pc, frame_pc = cap_pc.read()
        
        if not success_local and not success_pc:
            continue # Si ambas fallan, saltar

        contador += 1
        if contador < frames_a_skippear:
            continue
        contador = 0

        # intercalador de camaras
        turno_camara_local = not turno_camara_local
        
        if turno_camara_local and success_local:
            image = frame_local.copy()
            origen_camara = "Camara Local"
        elif not turno_camara_local and success_pc:
            image = frame_pc.copy()
            origen_camara = "Camara IR"
        else:
            # Respaldo: si tocaba una cámara pero se desconectó, usamos la otra
            if success_local:
                image = frame_local.copy()
                origen_camara = "Camara Local"
            else:
                image = frame_pc.copy()
                origen_camara = "Camara IR"

        original = image.copy()
        image_mesh = image.copy()
        image_pose = image.copy()

        # Inferencia neuronal sobre la cámara seleccionada en este ciclo
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        resultados = holistic_model.process(image_rgb)

        bebe_presente = False
        alerta_critica = False
        mensaje_alerta = ""

        # --- A) EVALUACIÓN DE ROSTRO Y LLANTO ---
        if resultados.face_landmarks:
            bebe_presente = True
            tiempo_sin_rostro = None

            face_landmarks = resultados.face_landmarks

            labio_sup = face_landmarks.landmark[13]
            labio_inf = face_landmarks.landmark[14]
            comisura_izq = face_landmarks.landmark[78]
            comisura_der = face_landmarks.landmark[308]
            
            apertura_boca = calcular_distancia(labio_sup, labio_inf)
            ancho_boca = calcular_distancia(comisura_izq, comisura_der)
            
            if ancho_boca > 0:
                ratio_boca = apertura_boca / ancho_boca
                if ratio_boca > 0.6:
                    tiempo_actual = time.time()
                    if tiempo_actual - tiempo_ultima_alerta > cooldown_alertas:
                        alerta_critica = True
                        mensaje_alerta = "¡Bebé en llanto detectado!"
                        tiempo_ultima_alerta = tiempo_actual
            
            mp_drawing.draw_landmarks(
                image=image_mesh,
                landmark_list=resultados.face_landmarks,
                connections=mp_holistic.FACEMESH_TESSELATION,
                landmark_drawing_spec=None,
                connection_drawing_spec=mp_drawing_styles.get_default_face_mesh_tesselation_style())
            
            # Etiqueta en pantalla mostrando qué cámara está activa
            cv2.putText(image_mesh, f"Bebe Detectado ({origen_camara})", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            
        else:
            if tiempo_sin_rostro is None:
                tiempo_sin_rostro = time.time()
            
            tiempo_transcurrido = time.time() - tiempo_sin_rostro
            tiempo_restante = max(0, round(segundos_limite - tiempo_transcurrido + 1, 2))
            
            cv2.putText(image_mesh, f"Sin bebe en {origen_camara} ({tiempo_restante}s)", (20, 40), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

            if tiempo_transcurrido >= segundos_limite:
                alerta_critica = True
                mensaje_alerta = f"Bebe no detectado en la cuna ({origen_camara})"
                tiempo_sin_rostro = time.time()

        # --- B) EVALUACIÓN DE POSTURA ---
        if resultados.pose_landmarks and bebe_presente:
            landmarks = resultados.pose_landmarks.landmark
            
            nariz = landmarks[mp_holistic.PoseLandmark.NOSE.value]
            hombro_izq = landmarks[mp_holistic.PoseLandmark.LEFT_SHOULDER.value]
            hombro_der = landmarks[mp_holistic.PoseLandmark.RIGHT_SHOULDER.value]

            mp_drawing.draw_landmarks(
                image_mesh, # Dibujamos en la misma imagen para que Flask muestre todo
                resultados.pose_landmarks, 
                mp_holistic.POSE_CONNECTIONS,
                landmark_drawing_spec=mp_drawing_styles.get_default_pose_landmarks_style())

            estado_postura = "Segura"
            color_postura = (0, 255, 0)

            distancia_hombros = abs(hombro_izq.x - hombro_der.x)
            limite_cercania = 0.30 
            
            if distancia_hombros > limite_cercania:
                estado_postura = "¡Trepando!"
                color_postura = (0, 0, 255) 
                alerta_critica = True
                mensaje_alerta = f"¡Bebe de pie o cerca de la cámara! ({origen_camara})"

            elif (hombro_izq.visibility > 0.6 and hombro_der.visibility > 0.6) and nariz.visibility < 0.2:
                estado_postura = "¡Boca abajo!"
                color_postura = (0, 0, 255)
                alerta_critica = True
                mensaje_alerta = f"¡Bebe posicionado boca abajo! ({origen_camara})"

            cv2.putText(image_mesh, f"Postura: {estado_postura}", (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color_postura, 2)
            
            if alerta_critica and "PELIGRO" in estado_postura:
                if tiempo_mala_postura is None:
                    tiempo_mala_postura = time.time()
                
                if time.time() - tiempo_mala_postura < segundos_limite:
                    alerta_critica = False 
            else:
                tiempo_mala_postura = None

        # Actualizar frame para el stream Flask
        with lock:
            output_frame = image_mesh.copy()

        # --- C) ENVÍO A MQTT ---
        if alerta_critica:
            nombre_foto = f"/app/alertas/alerta_{origen_camara.replace(' ', '_')}_{int(time.time())}.png"
            # Ojo: asegúrate de que el directorio /app/alertas/ exista o quitar /app/alertas/ si estás local
            cv2.imwrite(nombre_foto, original) 
            print(f"!! (ALERTA) {mensaje_alerta}")
            
            try:
                with open(nombre_foto, "rb") as image_file:
                    encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                
                payload = {
                    "alerta": "CRITICA",
                    "mensaje": mensaje_alerta,
                    "imagen_base64": encoded_string
                }
                
                mqtt_client.publish(MQTT_TOPIC, json.dumps(payload))
                print(f"// (ENVIO) Payload MQTT listo.")
            except Exception as e:
                print(f"!! (ENVIO) Error enviando la alerta MQTT: {e}")
            
            # Limpieza de fotos viejas
            fotos = glob.glob('/app/alertas/alerta_*.png')
            fotos.sort()
            if len(fotos) > 20:
                for foto_vieja in fotos[:-20]:
                    try:
                        os.remove(foto_vieja)
                    except:
                        pass

            if "detectado" not in mensaje_alerta:
                tiempo_mala_postura = time.time()