#include <WiFi.h>
#include "esp_http_server.h"

// ---------------------------------------------------------
// Configuración de Red
// ---------------------------------------------------------
const char* ssid = "OnePlus Nord 5 t2yq";
const char* password = "del0al10";

// ---------------------------------------------------------
// Servidor y Memoria
// ---------------------------------------------------------
httpd_handle_t server = NULL;

// Buffer global en la PSRAM para almacenar la foto de la PC
uint8_t* frame_buffer = NULL;
size_t frame_len = 0;
portMUX_TYPE frame_mux = portMUX_INITIALIZER_UNLOCKED;

#define PART_BOUNDARY "123456789000000000000987654321"
static const char* STREAM_CONTENT_TYPE = "multipart/x-mixed-replace;boundary=" PART_BOUNDARY;
static const char* STREAM_BOUNDARY = "\r\n--" PART_BOUNDARY "\r\n";
static const char* STREAM_PART = "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";

// 1. ENDPOINT PARA RECIBIR DE LA PC (POST /upload)
static esp_err_t upload_handler(httpd_req_t *req) {
  // Limite de seguridad: Ignorar imágenes mayores a 50KB para no colapsar
  if (req->content_len > 50000) {
    httpd_resp_send_500(req);
    return ESP_FAIL;
  }

  // ps_malloc guarda la imagen en la RAM externa (PSRAM) de la ESP32-CAM
  uint8_t* temp_buf = (uint8_t*) ps_malloc(req->content_len);
  if (!temp_buf) {
    httpd_resp_send_500(req);
    return ESP_FAIL;
  }

  int received = 0;
  int remaining = req->content_len;
  while (remaining > 0) {
    int ret = httpd_req_recv(req, (char*)temp_buf + received, remaining);
    if (ret <= 0) {
      free(temp_buf);
      httpd_resp_send_500(req);
      return ESP_FAIL;
    }
    received += ret;
    remaining -= ret;
  }

  // Intercambio seguro en memoria (Bloqueamos momentáneamente para no cruzar datos)
  portENTER_CRITICAL(&frame_mux);
  if (frame_buffer != NULL) {
    free(frame_buffer);
  }
  frame_buffer = temp_buf;
  frame_len = req->content_len;
  portEXIT_CRITICAL(&frame_mux);

  httpd_resp_sendstr(req, "OK");
  return ESP_OK;
}

// 2. ENDPOINT PARA RE-TRANSMITIR A LA RASPBERRY (GET /stream)
static esp_err_t stream_handler(httpd_req_t *req) {
  esp_err_t res = httpd_resp_set_type(req, STREAM_CONTENT_TYPE);
  if (res != ESP_OK) return res;

  char part_buf[64];

  while (true) {
    uint8_t* send_buf = NULL;
    size_t send_len = 0;

    // Copiamos el frame actual de forma segura para transmitirlo
    portENTER_CRITICAL(&frame_mux);
    if (frame_buffer != NULL && frame_len > 0) {
      send_len = frame_len;
      send_buf = (uint8_t*) ps_malloc(send_len);
      if (send_buf) {
        memcpy(send_buf, frame_buffer, send_len);
      }
    }
    portEXIT_CRITICAL(&frame_mux);

    if (send_buf) {
      res = httpd_resp_send_chunk(req, STREAM_BOUNDARY, strlen(STREAM_BOUNDARY));
      if (res == ESP_OK) {
        size_t hlen = snprintf(part_buf, 64, STREAM_PART, send_len);
        res = httpd_resp_send_chunk(req, part_buf, hlen);
      }
      if (res == ESP_OK) {
        res = httpd_resp_send_chunk(req, (const char *)send_buf, send_len);
      }
      free(send_buf);
    }

    if (res != ESP_OK) break;
    vTaskDelay(100 / portTICK_PERIOD_MS); // Ajustamos a ~10 FPS
  }
  return res;
}

void startBridgeServer() {
  httpd_config_t config = HTTPD_DEFAULT_CONFIG();
  config.server_port = 81;
  config.stack_size = 8192; // Mucha pila para evitar desbordes

  httpd_uri_t stream_uri = { .uri = "/stream", .method = HTTP_GET, .handler = stream_handler, .user_ctx = NULL };
  httpd_uri_t upload_uri = { .uri = "/upload", .method = HTTP_POST, .handler = upload_handler, .user_ctx = NULL };

  if (httpd_start(&server, &config) == ESP_OK) {
    httpd_register_uri_handler(server, &stream_uri);
    httpd_register_uri_handler(server, &upload_uri);
    Serial.println("Servidor Puente iniciado en el puerto 81");
  }
}

void setup() {
  Serial.begin(115200);

  // Inicializar Memoria PSRAM (Crucial para este truco)
  if(psramInit()){
    Serial.println("PSRAM Inicializada correctamente.");
  } else {
    Serial.println("Error: PSRAM no disponible.");
  }

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println("\nWiFi conectado!");
  Serial.print("Dile a tu PC que envíe video a: http://");
  Serial.print(WiFi.localIP());
  Serial.println(":81/upload");
  
  Serial.print("Dile a tu Raspberry que lea video de: http://");
  Serial.print(WiFi.localIP());
  Serial.println(":81/stream");

  startBridgeServer();
}

void loop() {
  delay(10000); // El procesador principal descansa, el servidor HTTP hace todo
}