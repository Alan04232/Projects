#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <MPU6050.h>

#define SOIL_PIN 34

// ---------------- CONFIG ----------------
#define NODE_ID 1
#define LAT 10.020
#define LON 76.300

const char* ssid = "YOUR_WIFI";
const char* password = "YOUR_PASSWORD";

// Intermediate Node IP
const char* gatewayURL = "http://192.168.1.50/node-data";
// ---------------------------------------

MPU6050 mpu;

void setup() {
  Serial.begin(115200);
  Wire.begin();
  mpu.initialize();

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
  }
}

void loop() {
  int16_t ax, ay, az;
  mpu.getAcceleration(&ax, &ay, &az);

  float vibration = abs(ax) / 16384.0;

  int raw = analogRead(SOIL_PIN);
  int soil = map(raw, 4095, 1500, 0, 100);

  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(gatewayURL);
    http.addHeader("Content-Type", "application/json");

    String payload = "{";
    payload += "\"node_id\":" + String(NODE_ID) + ",";
    payload += "\"lat\":" + String(LAT, 5) + ",";
    payload += "\"lon\":" + String(LON, 5) + ",";
    payload += "\"soil_moisture\":" + String(soil) + ",";
    payload += "\"vibration\":" + String(vibration, 3);
    payload += "}";

    http.POST(payload);
    http.end();
  }

  delay(5000);
}
