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

# ---> LIBRERÍAS PARA EL AUDIO <---
import pyaudio
import struct

# ==========================================
# 1. FLASK - SERVIDOR DE STREAM DUAL
# ==========================================
app = Flask(__name__)

output_frame_local = None
output_frame_ir = None
lock_local = threading.Lock()
lock_ir = threading.Lock()
 
def generate_stream_local():
    global output_frame_local
    while True:
        with lock_local:
            if output_frame_local is None:
                continue
            ret, buffer = cv2.imencode('.jpg', output_frame_local)
            if not ret:
                continue
            frame = buffer.tobytes()
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

def generate_stream_ir():
    global output_frame_ir
    while True:
        with lock_ir:
            if output_frame_ir is None:
                continue
            ret, buffer = cv2.imencode('.jpg', output_frame_ir)
            if not ret:
                continue
            frame = buffer.tobytes()
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
 
@app.route('/video_local')
def video_local():
    return Response(generate_stream_local(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/video_ir')
def video_ir():
    return Response(generate_stream_ir(), mimetype='multipart/x-mixed-replace; boundary=frame')
 
def run_flask():
    app.run(host='0.0.0.0', port=8081, threaded=True)
 
flask_thread = threading.Thread(target=run_flask)
flask_thread.daemon = True
flask_thread.start()

# ==========================================
# 2. CONFIGURACIÓN MQTT
# ==========================================
MQTT_BROKER = "broker"
MQTT_PORT = 1883
MQTT_TOPIC_CAMARA = "babyguard/alertas/camara"
MQTT_TOPIC_AUDIO = "babyguard/alertas/audio"

print("Conectando al Broker MQTT local de BabyGuard...")
mqtt_client = mqtt.Client()
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
mqtt_client.loop_start()

# ==========================================
# 3. MOTOR DE AUDIO (HILO SECUNDARIO)
# ==========================================
def motor_de_audio():
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 44100
    UMBRAL_DECIBELIOS = 75   # <-- Ajusta a partir de cuántos dB es alarma
    TIEMPO_ESPERA = 5

    p = pyaudio.PyAudio()
    
    try:
        # IMPORTANTE: Ajustar input_device_index con el ID real de tu adaptador USB en la Raspberry
        stream = p.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        frames_per_buffer=CHUNK,
                        input_device_index=1) 
        print("🎙️ Motor de audio iniciado en segundo plano...")
    except Exception as e:
        print(f"⚠️ Error grave al abrir el micrófono: {e}")
        return

    ultimo_aviso = 0

    try:
        while True:
            data = stream.read(CHUNK, exception_on_overflow=False)
            count = len(data) / 2
            format_string = "%dh" % (count)
            shorts = struct.unpack(format_string, data)
            
            suma_cuadrados = sum(s**2 for s in shorts)
            rms = math.sqrt(suma_cuadrados / count)
            
            if rms > 0:
                db = 20 * math.log10(rms)
                db_calibrado = db + 20 
                
                if db_calibrado > UMBRAL_DECIBELIOS:
                    ahora = time.time()
                    if (ahora - ultimo_aviso) > TIEMPO_ESPERA:
                        mensaje = f"¡Llanto ruidoso detectado! ({db_calibrado:.2f} dB)"
                        print(f"🚨 (AUDIO) {mensaje}")
                        
                        payload = {
                            "alerta": "CRITICA_AUDIO",
                            "mensaje": mensaje,
                            "decibelios": round(db_calibrado, 2)
                        }
                        mqtt_client.publish(MQTT_TOPIC_AUDIO, json.dumps(payload))
                        ultimo_aviso = ahora
                        
    except Exception as e:
        print(f"Error procesando el audio: {e}")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()

# Iniciar el hilo de audio
audio_thread = threading.Thread(target=motor_de_audio)
audio_thread.daemon = True
audio_thread.start()

# ==========================================
# 4. CONFIGURACIÓN DE CÁMARAS Y MEDIAPIPE
# ==========================================
FUENTE_VIDEO = 0 
cap_local = cv2.VideoCapture(FUENTE_VIDEO)

# URL de la ESP32 (Asegúrate de que la IP sea la correcta al conectar)
URL_ESP32 = "http://10.220.244.165:81/upload"
cap_pc = cv2.VideoCapture(URL_ESP32)

mp_holistic = mp.solutions.holistic
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

def calcular_distancia(p1, p2):
    return math.hypot(p2.x - p1.x, p2.y - p1.y)

# Variables de estado
tiempo_sin_rostro = None
tiempo_mala_postura = None
tiempo_ultima_alerta = 0
cooldown_alertas = 5
segundos_limite = 1.5

framerate = 100 
frames_a_skippear = 1 
contador = 0
turno_camara_local = True

print("👁️ Iniciando BabyGuard Pro - Monitor Dual (Día/Noche) y Audio")

# ==========================================
# 5. BUCLE PRINCIPAL DE IA (VIDEO)
# ==========================================
with mp_holistic.Holistic(
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5) as holistic_model:
    
    while True:
        success_local, frame_local = cap_local.read()
        success_pc, frame_pc = cap_pc.read()
        
        if not success_local and not success_pc:
            continue

        contador += 1
        if contador < frames_a_skippear:
            continue
        contador = 0

        # === INTERCALADOR DE CÁMARAS ===
        turno_camara_local = not turno_camara_local
        
        if turno_camara_local and success_local:
            image = frame_local.copy()
            origen_camara = "Camara Local"
        elif not turno_camara_local and success_pc:
            image = frame_pc.copy()
            origen_camara = "Camara IR"
        else:
            if success_local:
                image = frame_local.copy()
                origen_camara = "Camara Local"
            else:
                image = frame_pc.copy()
                origen_camara = "Camara IR"
        # ===============================

        original = image.copy()
        image_mesh = image.copy()
        image_pose = image.copy()

        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        resultados = holistic_model.process(image_rgb)

        bebe_presente = False
        alerta_critica = False
        mensaje_alerta = ""

        # --- A) EVALUACIÓN DE ROSTRO Y LLANTO VISUAL ---
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
                        mensaje_alerta = "¡Llanto visual detectado!"
                        tiempo_ultima_alerta = tiempo_actual
            
            mp_drawing.draw_landmarks(
                image=image_mesh,
                landmark_list=resultados.face_landmarks,
                connections=mp_holistic.FACEMESH_TESSELATION,
                landmark_drawing_spec=None,
                connection_drawing_spec=mp_drawing_styles.get_default_face_mesh_tesselation_style())
            
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
                image_mesh,
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

        # ==================================================
        # ACTUALIZACIÓN DE STREAMS INDEPENDIENTES PARA FLASK
        # ==================================================
        if origen_camara == "Camara Local":
            with lock_local:
                output_frame_local = image_mesh.copy()
            with lock_ir:
                if success_pc:
                    output_frame_ir = frame_pc.copy()
                    
        elif origen_camara == "Camara IR":
            with lock_ir:
                output_frame_ir = image_mesh.copy()
            with lock_local:
                if success_local:
                    output_frame_local = frame_local.copy()

        # --- C) ENVÍO A MQTT (Solo Alertas Visuales) ---
        if alerta_critica:
            nombre_foto = f"/app/alertas/alerta_{origen_camara.replace(' ', '_')}_{int(time.time())}.png"
            cv2.imwrite(nombre_foto, original) 
            print(f"!! (ALERTA VISUAL) {mensaje_alerta}")
            
            try:
                with open(nombre_foto, "rb") as image_file:
                    encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                
                payload = {
                    "alerta": "CRITICA_VIDEO",
                    "mensaje": mensaje_alerta,
                    "imagen_base64": encoded_string
                }
                
                mqtt_client.publish(MQTT_TOPIC_CAMARA, json.dumps(payload))
                print(f"// (ENVIO) Payload MQTT listo.")
            except Exception as e:
                print(f"!! (ENVIO) Error enviando la alerta MQTT: {e}")
            
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