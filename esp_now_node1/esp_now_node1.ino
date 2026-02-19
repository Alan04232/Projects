#include <WiFi.h>
#include <esp_now.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <esp_wifi.h>


#define SOIL_PIN 34
#define SDA_PIN 21
#define SCL_PIN 22

#define NODE_ID 1
#define LAT 10.020
#define LON 76.300

#define SOIL_DRY 4095
#define SOIL_WET 1500

// 👉 PUT YOUR GATEWAY MAC HERE
uint8_t GATEWAY_MAC[] = {0x00, 0x70, 0x07, 0x3A, 0x55, 0x58};

Adafruit_MPU6050 mpu;
bool mpuOK = false;

// ===== Packet struct =====
typedef struct {
  int node_id;
  float lat;
  float lon;
  int soil;
  float vib_x;
  float vib_y;
  float vib_z;
  float humidity;
} NodePacket;

NodePacket data;

// ===== NEW ESP-NOW send callback (ESP32 core ≥3.x) =====
void onSent(const wifi_tx_info_t *info, esp_now_send_status_t status) {
  Serial.print("ESP-NOW send: ");
  Serial.println(status == ESP_NOW_SEND_SUCCESS ? "OK" : "FAIL");
}

void setup() {
  Serial.begin(115200);

  // --- WiFi STA mode ---
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();

  // --- Match gateway channel (11) ---
  esp_wifi_set_channel(11, WIFI_SECOND_CHAN_NONE);

  // --- Init ESP-NOW ---
  if (esp_now_init() != ESP_OK) {
    Serial.println("ESP-NOW init failed");
    return;
  }

  esp_now_register_send_cb(onSent);

  // --- Add peer ---
  esp_now_peer_info_t peer{};
  memcpy(peer.peer_addr, GATEWAY_MAC, 6);
  peer.channel = 11;   // must match gateway
  peer.encrypt = false;

  if (esp_now_add_peer(&peer) != ESP_OK) {
    Serial.println("Peer add failed");
    return;
  }

  // --- Sensors ---
  Wire.begin(SDA_PIN, SCL_PIN);

  if (mpu.begin()) {
    mpuOK = true;
    mpu.setAccelerometerRange(MPU6050_RANGE_2_G);
  }

  analogReadResolution(12);

  Serial.println("Node ready (ESP-NOW ch11)");
}

void loop() {

  float vib_x = 0, vib_y = 0, vib_z = 0;

  if (mpuOK) {
    sensors_event_t a, g, t;
    mpu.getEvent(&a, &g, &t);

    vib_x = a.acceleration.x;
    vib_y = a.acceleration.y;
    vib_z = a.acceleration.z;
  }

  int raw = analogRead(SOIL_PIN);
  int soil = map(raw, SOIL_DRY, SOIL_WET, 0, 100);
  soil = constrain(soil, 0, 100);

  data.node_id = NODE_ID;
  data.lat = LAT;
  data.lon = LON;
  data.soil = soil;
  data.vib_x = vib_x;
  data.vib_y = vib_y;
  data.vib_z = vib_z;
  data.humidity = 70;

  esp_err_t result = esp_now_send(GATEWAY_MAC, (uint8_t*)&data, sizeof(data));

  if (result != ESP_OK) {
    Serial.println("Send error");
  }

  delay(5000);
}
