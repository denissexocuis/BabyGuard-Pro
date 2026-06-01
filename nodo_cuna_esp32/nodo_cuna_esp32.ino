#include <WiFi.h>
#include <PubSubClient.h> //

// ---------------------------------------------------------
// Configuración de Red y MQTT (Modificar según entorno local)
// ---------------------------------------------------------
const char* ssid = "INFINITUM4C96"; // Nombre de tu red wifi
const char* password = "xxxxxxx";//contrasena de tu red wifi

// Dirección IP del broker MQTT (La IP de la laptop de Denisse o Raspberry)
const char* mqtt_server = "192.168.1.x"; 
const int mqtt_port = 1883;

// ---------------------------------------------------------
// Pines y Variables Globales
// ---------------------------------------------------------
// 18. Definir PIN_BUZZER con el número de GPIO que se usará
#define PIN_BUZZER 4

WiFiClient espClient;
PubSubClient client(espClient);

unsigned long lastMsg = 0;

// ---------------------------------------------------------
// Funciones de Inicialización
// ---------------------------------------------------------
void setup_wifi() {
  delay(10);
  Serial.println();
  Serial.print("Conectando a red Wi-Fi: ");
  Serial.println(ssid);

  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("");
  Serial.println("¡WiFi conectado exitosamente!");
  Serial.print("Dirección IP asignada: ");
  Serial.println(WiFi.localIP());
}

// 16. Crear función callback que recibe el mensaje de comandos
void callback(char* topic, byte* payload, unsigned int length) {
  Serial.print("Mensaje recibido bajo el tópico [");
  Serial.print(topic);
  Serial.print("] Payload: ");

  String messageTemp;
  for (int i = 0; i < length; i++) {
    messageTemp += (char)payload[i];
  }
  Serial.println(messageTemp);

  // 17. Evaluar si se debe activar el buzzer
  // 17. Evaluar si se debe activar el buzzer
  // Comprobamos si el tópico es el correcto y si el JSON contiene "activar": true o "activar":true
  if (String(topic) == "babyguard/cmd_buzzer") {
    if (messageTemp.indexOf("\"activar\":true") != -1 || messageTemp.indexOf("\"activar\": true") != -1) {
      Serial.println("¡ALERTA RECIBIDA! Tocando Piranha Plant Lullaby (SM64)...");
      
      // --- NOTAS DE SUPER MARIO 64 ---
      // Frecuencias base en Hz
      int C4 = 262; int D4 = 294; int E4 = 330; int F4 = 349; int G4 = 392; int A4 = 440; int B4 = 494;
      int C5 = 523; int D5 = 587; int E5 = 659; int F5 = 698; int G5 = 784; int A5 = 880;

      // Arreglo con la melodía principal de la planta piraña durmiendo
      int melodia[] = {
        E5, D5, C5, B4, A4, B4, C5, E5,
        D5, C5, B4, A4, B4, C5, A4,
        E5, D5, C5, B4, A4, B4, C5, E5,
        G5, F5, E5, D5, C5, E5, D5
      };

      // Duraciones: 4 = negra, 8 = corchea, 2 = blanca
      int duracion[] = {
        4,  4,  4,  4,  4,  4,  2,  4,
        4,  4,  4,  4,  4,  2,  2,
        4,  4,  4,  4,  4,  4,  2,  4,
        4,  4,  4,  4,  4,  2,  1  // La última nota es larga
      };
      
      int totalNotas = sizeof(melodia) / sizeof(melodia[0]);
      
      for (int estaNota = 0; estaNota < totalNotas; estaNota++) {
        // Calcular el tiempo que dura cada nota
        int duracionMilisegundos = 1000 / duracion[estaNota];
        
        // El pin 4 es el PIN_BUZZER que configuró Armando
        tone(PIN_BUZZER, melodia[estaNota], duracionMilisegundos);
        
        // Espaciado dinámico entre notas para que suene fluido el vals
        int pausaEntreNotas = duracionMilisegundos * 1.30;
        delay(pausaEntreNotas);
        
        noTone(PIN_BUZZER); // Detener el tono actual antes del que sigue
      }
      // -----------------------------------------------------------

      Serial.println("Canción finalizada. Retornando a monitoreo normal.");
    }
  }
}

void reconnect() {
  // Loop hasta que estemos reconectados
  while (!client.connected()) {
    Serial.print("Intentando conexión al broker MQTT...");
    // Intento de conexión con un ID de cliente único
    if (client.connect("ESP32_Nodo_Cuna")) {
      Serial.println("¡Conectado al broker!");

      // 15. Suscripción al tópico del buzzer una vez conectados
      client.subscribe("babyguard/cmd_buzzer");
      Serial.println("Suscrito a: babyguard/cmd_buzzer");
    } else {
      Serial.print("Falló la conexión, rc=");
      Serial.print(client.state());
      Serial.println(" -> intentando de nuevo en 5 segundos");
      delay(5000);
    }
  }
}

// ---------------------------------------------------------
// Bucle Principal
// ---------------------------------------------------------
void setup() {
  Serial.begin(115200);

  // Configuración de hardware
  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_BUZZER, LOW);

  // Inicialización de conectividad
  setup_wifi();
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  unsigned long now = millis();

  // 14. Publicar al tópico 'babyguard/sensores' cada 5000 ms
  if (now - lastMsg > 5000) {
    lastMsg = now;

    // 4, 5, 6. Generación de lecturas FALSAS de sensores con random()
    float temp = random(220, 300) / 10.0;
    float hum = random(400, 700) / 10.0;
    int ruido = random(30, 85);

    // 8, 9. Armar el JSON de envío con sprintf() asegurando el formato exacto 
    char payload[128];
    sprintf(payload, "{\"temp\":%.1f, \"humedad\":%.1f, \"ruido\":%d}", temp, hum, ruido);

    Serial.print("Publicando telemetría: ");
    Serial.println(payload);

    client.publish("babyguard/sensores", payload);
  }
}
