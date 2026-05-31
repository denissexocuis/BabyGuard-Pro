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
  // Comprobamos si el tópico es el correcto y si el JSON contiene "activar": true o "activar":true
  if (String(topic) == "babyguard/cmd_buzzer") {
    if (messageTemp.indexOf("\"activar\":true") != -1 || messageTemp.indexOf("\"activar\": true") != -1) {
      Serial.println("¡ALERTA RECIBIDA! Activando buzzer por 3 segundos...");
      digitalWrite(PIN_BUZZER, HIGH);
      delay(3000);
      digitalWrite(PIN_BUZZER, LOW);
      Serial.println("Buzzer desactivado. Retornando a monitoreo normal.");
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
