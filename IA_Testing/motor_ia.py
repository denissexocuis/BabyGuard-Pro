import cv2
import mediapipe as mp
import time
import base64
import json
import paho.mqtt.client as mqtt
import math

# MQTT
# MQTT_BROKER = "127.0.0.1" # para localhost
# MQTT_BROKER = "broker"
# MQTT_PORT = 1883
# MQTT_TOPIC = "babyguard/alertas/camara"

print("Conectando al Broker MQTT local de BabyGuard...")
# mqtt_client = mqtt.Client()
# mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
# mqtt_client.loop_start()


# MEDIAPIPE
# Fuente para el stream del video y uso de camara de la esp (ahi ya toca poner el topico donde se haga stream del video)
# FUENTE_VIDEO = "Media/Test/Videos/baby_4.mp4"
FUENTE_VIDEO = 1

mp_holistic = mp.solutions.holistic
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

cap = cv2.VideoCapture(FUENTE_VIDEO)

def calcular_distancia(p1, p2):
    return math.hypot(p2.x - p1.x, p2.y - p1.y)

tiempo_sin_rostro = None
tiempo_mala_postura = None
tiempo_ultima_alerta = 0
cooldown_alertas = 5
segundos_limite = 1.5

print(f"Iniciando BabyGuard Pro - Face Mesh Monitor: {FUENTE_VIDEO}")
print("Presiona 'ESC' en la ventana de video para salir")

framerate = 20 # configuracion virtual de framerate
frames_a_skippear = 1 # configuracion de cuantos frames quiero saltar
# por ejemplo frames_a_skippear = 1, proceso 1 salto 1 proceso 1 salto 1 - procesamiento vs real 1/2=50%
# por ejemplo frames_a_skippear = 2, proceso 1 salto 2 proceso 1 salto 2 - procesamiento 1/3=33%
# por ejemplo frames_a_skippear = 3, proceso 1 salto 3 proceso 1 salto 3 - procesamiento 1/4=25%

delay = 1 / float(framerate)
contador = 0

with mp_holistic.Holistic(
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5) as holistic_model:
    
    while True:
        success, image = cap.read()
        
        if not success:
            print("-- (deteccion) Fin del video de prueba. Reiniciando bucle...")
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        original = image.copy()
        image_mesh = image.copy()
        image_pose = image.copy()

        # contador para skipeo de frames para evitar el sobreprocesamiento en la Rasp
        contador += 1
        if contador < frames_a_skippear:
            cv2.imshow('BabyGuard Pro - Camara', original)
            cv2.imshow('BabyGuard Pro - Face Mesh', image_mesh)
            cv2.imshow('BabyGuard Pro - Postura', image_pose)
            if cv2.waitKey(1) & 0xFF == 27: break
            continue

        contador = 0

        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        resultados = holistic_model.process(image_rgb)

        # flags de estado del bebe
        bebe_presente = False
        alerta_critica = False
        mensaje_alerta = ""

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
                    print("// (log) Bebe en llanto")
                    tiempo_actual = time.time()
                    if tiempo_actual - tiempo_ultima_alerta > cooldown_alertas:
                        alerta_critica = True
                        mensaje_alerta = "¡Bebe de pie o peligrosamente cerca de la cámara!"
                        tiempo_ultima_alerta = tiempo_actual
            
            # dibujo de tesselado de rostro (los triangulos de la cara)
            mp_drawing.draw_landmarks(
                image=image_mesh,
                landmark_list=resultados.face_landmarks,
                connections=mp_holistic.FACEMESH_TESSELATION,
                landmark_drawing_spec=None,
                connection_drawing_spec=mp_drawing_styles.get_default_face_mesh_tesselation_style())
            
            # dibujar contornos (ojos, cejas, labios y cara)
            mp_drawing.draw_landmarks(
                image=image_mesh,
                landmark_list=resultados.face_landmarks,
                connections=mp_holistic.FACEMESH_CONTOURS,
                landmark_drawing_spec=None,
                connection_drawing_spec=mp_drawing_styles.get_default_face_mesh_contours_style())
            
            cv2.putText(image_mesh, "Bebe Detectado", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            print("// (log) Bebe en pantalla.")
        else:
            # ALERTAS DE QUE NO HAY BEBE EN LA IMAGEN

            if tiempo_sin_rostro is None:
                tiempo_sin_rostro = time.time()
            
            tiempo_transcurrido = time.time() - tiempo_sin_rostro
            print(f"!! (ALERTA) Sin bebe detectado por {round(tiempo_transcurrido,3)} segundos.")
            tiempo_restante = max(0, round(segundos_limite - tiempo_transcurrido + 1, 2))
            
            cv2.putText(image, f"Sin bebe... Foto en: {tiempo_restante}s", (20, 40), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

            if tiempo_transcurrido >= segundos_limite:
                alerta_critica = True
                mensaje_alerta = "Bebe no detectado en la cuna..."
                tiempo_sin_rostro = time.time()

        # POSTURA DEL BEBE
        if resultados.pose_landmarks and bebe_presente:
            landmarks = resultados.pose_landmarks.landmark
            
            nariz = landmarks[mp_holistic.PoseLandmark.NOSE.value]
            hombro_izq = landmarks[mp_holistic.PoseLandmark.LEFT_SHOULDER.value]
            hombro_der = landmarks[mp_holistic.PoseLandmark.RIGHT_SHOULDER.value]

            # Dibujo de esqueleto en la imagen de postura
            mp_drawing.draw_landmarks(
                image_pose, 
                resultados.pose_landmarks, 
                mp_holistic.POSE_CONNECTIONS,
                landmark_drawing_spec=mp_drawing_styles.get_default_pose_landmarks_style())

            estado_postura = "Postura: Segura"
            color_postura = (0, 255, 0) # Verde

            # se calcula la distancia entre los hombros para ver si esta parado
            # la camara se encuentra justo encima de la cuna,
            # asi que se calcula la distancia de hombro a hombro para calcular cercania
            distancia_hombros = abs(hombro_izq.x - hombro_der.x)
            limite_cercania = 0.30 # cerca del 30% del ancho de la camara
            
            if distancia_hombros > limite_cercania:
                estado_postura = "¡PELIGRO: Trepando!"
                color_postura = (0, 0, 255) # Rojo
                alerta_critica = True
                mensaje_alerta = "¡Bebe de pie o peligrosamente cerca de la cámara!"

            # buena visibilidad de hombros (espalda) pero nada de visibilidad en la nariz
            elif (hombro_izq.visibility > 0.6 and hombro_der.visibility > 0.6) and nariz.visibility < 0.2:
                estado_postura = "¡PELIGRO: Boca abajo!"
                color_postura = (0, 0, 255)
                alerta_critica = True
                mensaje_alerta = "¡Bebe posicionado boca abajo!"

            cv2.putText(image_pose, estado_postura, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color_postura, 2)
            
            # temporizador para posturas peligrosas
            if alerta_critica and "PELIGRO" in estado_postura:
                if tiempo_mala_postura is None:
                    tiempo_mala_postura = time.time()
                
                if time.time() - tiempo_mala_postura < segundos_limite:
                    alerta_critica = False # reset mientras no se termine el tiempo
            else:
                tiempo_mala_postura = None

        # ENVIO A MQTT
        if alerta_critica:
            nombre_foto = f"alerta_mesh_{int(time.time())}.png"
            cv2.imwrite(nombre_foto, original) # Mandamos la foto limpia al dashboard
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
                print(f"// (ENVIO) Payload MQTT listo para: {mensaje_alerta}")
            except Exception as e:
                print(f"!! (ENVIO) Error enviando la alerta MQTT: {e}")
            
            if "detectado" not in mensaje_alerta:
                tiempo_mala_postura = time.time() # Reset de seguridad

        cv2.imshow('BabyGuard Pro - Camara', original)
        cv2.imshow('BabyGuard Pro - Face Mesh', image_mesh)
        cv2.imshow('BabyGuard Pro - Postura', image_pose)

        if cv2.waitKey(30) & 0xFF == 27:
            break

cap.release()
cv2.destroyAllWindows()
