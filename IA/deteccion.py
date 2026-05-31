import cv2
import mediapipe as mp
import time


# Fuente para el stream del video y uso de camara de la esp (ahi ya toca poner el topico donde se haga stream del video)
FUENTE_VIDEO = "Media/Test/Videos/baby_4.mp4" 

mp_face_mesh = mp.solutions.face_mesh
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

cap = cv2.VideoCapture(FUENTE_VIDEO)

tiempo_sin_rostro = None
segundos_limite = 1.5

print(f"Iniciando BabyGuard Pro - Face Mesh Monitor: {FUENTE_VIDEO}")
print("Presiona 'ESC' en la ventana de video para salir")

with mp_face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5) as face_mesh:
    
    while True:
        success, image = cap.read()
        scs, original = cap.read()
        
        if not success:
            print("Fin del video de prueba. Reiniciando bucle...")
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        resultados = face_mesh.process(image_rgb)

        if resultados.multi_face_landmarks:
            tiempo_sin_rostro = None  
            
            for face_landmarks in resultados.multi_face_landmarks:
                # dibujo de tesselado de rostro (los triangulos de la cara)
                mp_drawing.draw_landmarks(
                    image=image,
                    landmark_list=face_landmarks,
                    connections=mp_face_mesh.FACEMESH_TESSELATION,
                    landmark_drawing_spec=None,
                    connection_drawing_spec=mp_drawing_styles.get_default_face_mesh_tesselation_style())
                
                # dibujar contornos (ojos, cejas, labios y cara)
                mp_drawing.draw_landmarks(
                    image=image,
                    landmark_list=face_landmarks,
                    connections=mp_face_mesh.FACEMESH_CONTOURS,
                    landmark_drawing_spec=None,
                    connection_drawing_spec=mp_drawing_styles.get_default_face_mesh_contours_style())
        else:
            # ALERTAS DE QUE NO HAY BEBE EN LA IMAGEN
            if tiempo_sin_rostro is None:
                tiempo_sin_rostro = time.time()
            
            tiempo_transcurrido = time.time() - tiempo_sin_rostro
            tiempo_restante = max(0, int(segundos_limite - tiempo_transcurrido) + 1)
            
            cv2.putText(image, f"Sin bebe... Foto en: {tiempo_restante}s", (20, 40), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

            if tiempo_transcurrido >= segundos_limite:
                nombre_foto = f"alerta_mesh_{int(time.time())}.png"
                cv2.imwrite(nombre_foto, image)
                print(f"!! (ALERTA) Foto guardada {nombre_foto}")
                
                # TODO: cosas q hay que mandar a los usuarios para alertarlos
                tiempo_sin_rostro = time.time()

        cv2.imshow('BabyGuard Pro - Monitor', image)
        cv2.imshow('BabyGuard Pro - Camara', original)

        if cv2.waitKey(30) & 0xFF == 27: 
            break

cap.release()
cv2.destroyAllWindows()