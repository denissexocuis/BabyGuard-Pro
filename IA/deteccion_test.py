# deteccion mp
import cv2
import time
import mediapipe as mp


mp_face_mesh = mp.solutions.face_mesh
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles


# Funcion generica para la obtencion de un frame/foto, procesamiento, y retorno de ella con una mesh
def procesar_imagen_mesh(image, face_mesh):
    # Convertir a RGB para MediaPipe
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    
    # inferencia de la malla
    resultados = face_mesh.process(image_rgb)
    rostro_detectado = False

    if resultados.multi_face_landmarks:
        rostro_detectado = True
        
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
            
    return image, rostro_detectado


# Funcion para el uso de imagen en disco
def procesar_imagen_disco(ruta_imagen):
    image = cv2.imread(ruta_imagen)
    if image is None:
        print(f"!! (Disco) No se encontro la imagen en {ruta_imagen}")
        return

    with mp_face_mesh.FaceMesh(
        static_image_mode=True,
        # para que no tenga que intentar detectas mas rostros mas que 1
        # TODO quizas se pueda configurar para que el usuario ponga si hay mas de un bebe en la camara
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5) as face_mesh:
        
        image_procesada, detectado = procesar_imagen_mesh(image, face_mesh)
        
        cv2.imshow('BabyGuard Pro', image_procesada)
        cv2.waitKey(0)
        cv2.destroyAllWindows()


# Funcion para el stream del video y uso de camara
def procesar_camara(fuente_video=0):
    cap = cv2.VideoCapture(fuente_video)
    if not cap.isOpened():
        print(f"!! (Camara) No se pudo acceder a la camara: {fuente_video}")
        return

    tiempo_sin_rostro = None
    segundos_limite = 1.5

    with mp_face_mesh.FaceMesh(
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5) as face_mesh:
        
        while True:
            success, image = cap.read()
            if not success:
                break

            image_procesada, rostro_detectado = procesar_imagen_mesh(image, face_mesh)

            # si no hay rostro entonces empieza un timer para tomar una foto y posteriormente alertar a los usuarios
            if rostro_detectado:
                tiempo_sin_rostro = None
            else:
                if tiempo_sin_rostro is None:
                    tiempo_sin_rostro = time.time()
                
                tiempo_transcurrido = time.time() - tiempo_sin_rostro
                tiempo_restante = max(0, int(segundos_limite - tiempo_transcurrido) + 1)
                
                cv2.putText(image_procesada, f"Sin bebe... Foto en: {tiempo_restante}s", (20, 40), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

                if tiempo_transcurrido >= segundos_limite:
                    nombre_foto = f"alerta_mesh_{int(time.time())}.png"
                    cv2.imwrite(nombre_foto, image_procesada)
                    print(f"!! (ALERTA) Foto guardada {nombre_foto}")
                    # TODO: cosas q hay que mandar a los usuarios para alertarlos
                    tiempo_sin_rostro = time.time()

            cv2.imshow('BabyGuard Pro', image_procesada)

            if cv2.waitKey(5) & 0xFF == 27: # ESC para salir
                break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    # solo foto
    procesar_imagen_disco("Fotos/Test/Baby_1.jpg")
    
    # un video
    # procesar_camara(0)