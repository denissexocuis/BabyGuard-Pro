#include <WiFi.h>
#include <PubSubClient.h> //
#include "esp_http_server.h"
#include "esp_camera.h"

// ---------------------------------------------------------
// Configuración de Red y MQTT (Modificar según entorno local)
// ---------------------------------------------------------
const char* ssid = "OnePlus Nord 5 t2yq"; // Nombre de tu red wifi
const char* password = "del0al10";//contrasena de tu red wifi

// Dirección IP del broker MQTT (La IP de la laptop de Denisse o Raspberry)
const char* mqtt_server = "10.97.203.31"; 
const int mqtt_port = 1883;

// ---------------------------------------------------------
// Pines y Variables Globales
// ---------------------------------------------------------
// 18. Definir PIN_BUZZER con el número de GPIO que se usará
#define PIN_BUZZER 4
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22
#define PART_BOUNDARY "123456789000000000000987654321"


// constantes y variables para el stream 
static const char* STREAM_CONTENT_TYPE = "multipart/x-mixed-replace;boundary=" PART_BOUNDARY;
static const char* STREAM_BOUNDARY = "\r\n--" PART_BOUNDARY "\r\n";
static const char* STREAM_PART = "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";
httpd_handle_t stream_httpd = NULL;

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
  Serial.print("Stream disponible en: http://");
  Serial.print(WiFi.localIP());
  Serial.println(":81/stream");
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

// Configura la camara antes de conectarse al Wi-Fi
void setup_camera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0       = Y2_GPIO_NUM;
  config.pin_d1       = Y3_GPIO_NUM;
  config.pin_d2       = Y4_GPIO_NUM;
  config.pin_d3       = Y5_GPIO_NUM;
  config.pin_d4       = Y6_GPIO_NUM;
  config.pin_d5       = Y7_GPIO_NUM;
  config.pin_d6       = Y8_GPIO_NUM;
  config.pin_d7       = Y9_GPIO_NUM;
  config.pin_xclk     = XCLK_GPIO_NUM;
  config.pin_pclk     = PCLK_GPIO_NUM;
  config.pin_vsync    = VSYNC_GPIO_NUM;
  config.pin_href     = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn     = PWDN_GPIO_NUM;
  config.pin_reset    = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size   = FRAMESIZE_QVGA;
  config.jpeg_quality = 30;
  config.fb_count     = 1;

  esp_err_t err = esp_camera_init(&config);

  if (err != ESP_OK) {
    Serial.printf("Error iniciando cámara: 0x%x\n", err);
    return;
  }
}

// Manejador de stream de la camara
static esp_err_t stream_handler(httpd_req_t *req) {
  camera_fb_t * fb = NULL;
  esp_err_t res = ESP_OK;
  char part_buf[64];

  res = httpd_resp_set_type(req, STREAM_CONTENT_TYPE);
  if (res != ESP_OK) return res;

  while (true) {
    fb = esp_camera_fb_get();
    if (!fb) {
      Serial.println("Error capturando frame");
      res = ESP_FAIL;
      break;
    }

    res = httpd_resp_send_chunk(req, STREAM_BOUNDARY, strlen(STREAM_BOUNDARY));
    if (res == ESP_OK) {
      size_t hlen = snprintf(part_buf, 64, STREAM_PART, fb->len);
      res = httpd_resp_send_chunk(req, part_buf, hlen);
    }
    if (res == ESP_OK) {
      res = httpd_resp_send_chunk(req, (const char *)fb->buf, fb->len);
    }
    esp_camera_fb_return(fb);
    if (res != ESP_OK) break;
  }
  return res;
}

// Init del sevidor de stream
void startCameraServer() {
  httpd_config_t config = HTTPD_DEFAULT_CONFIG();
  config.server_port = 81;
  config.stack_size = 8192;

  httpd_uri_t stream_uri = {
    .uri       = "/stream",
    .method    = HTTP_GET,
    .handler   = stream_handler,
    .user_ctx  = NULL
  };

  if (httpd_start(&stream_httpd, &config) == ESP_OK) {
    httpd_register_uri_handler(stream_httpd, &stream_uri);
    Serial.println("Stream iniciado en puerto 81");
  }
}

void mqttTask(void *pvParameters) {
  while (true) {
    if (!client.connected()) {
      reconnect();
    }
    client.loop();

    unsigned long now = millis();
    if (now - lastMsg > 5000) {
      lastMsg = now;
      float temp = random(220, 300) / 10.0;
      float hum = random(400, 700) / 10.0;
      int ruido = random(30, 85);
      char payload[128];
      sprintf(payload, "{\"temp\":%.1f, \"humedad\":%.1f, \"ruido\":%d}", temp, hum, ruido);
      Serial.print("Publicando telemetría: ");
      Serial.println(payload);
      client.publish("babyguard/sensores", payload);
    }
    vTaskDelay(10 / portTICK_PERIOD_MS);
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
  setup_camera();
  setup_wifi();
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);
  client.setKeepAlive(60);

  startCameraServer();
  xTaskCreatePinnedToCore(mqttTask, "mqttTask", 8192, NULL, 1, NULL, 0);
}

void loop() {
  /*
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
  */
  vTaskDelay(1000 / portTICK_PERIOD_MS);
}
