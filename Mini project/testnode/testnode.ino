#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>

#define SOIL_PIN 34
#define SDA_PIN 21
#define SCL_PIN 22

#define NODE_ID 1
#define LAT 10.020
#define LON 76.300

const char* ssid = "IQOO Z7 PRO";
const char* password = "";

// Laptop IP (server)
const char* serverURL = "http://192.168.43.1:5000/data";

Adafruit_MPU6050 mpu;
bool mpuAvailable = false;

void setup() {
  Serial.begin(115200);

  // I2C
  Wire.begin(SDA_PIN, SCL_PIN);
  Serial.println("Initializing MPU6050...");
  if (mpu.begin()) {
    Serial.println("MPU6050 detected");
    mpuAvailable = true;
  } else {
    Serial.println("MPU6050 NOT detected");
  }

  analogReadResolution(12);
  pinMode(SOIL_PIN, INPUT);

  // WiFi
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi Connected");
  Serial.print("ESP32 IP: ");
  Serial.println(WiFi.localIP());
}

void loop() {
  float vx = 0, vy = 0, vz = 0;

  if (mpuAvailable) {
    sensors_event_t a, g, temp;
    mpu.getEvent(&a, &g, &temp);
    vx = abs(a.acceleration.x);
    vy = abs(a.acceleration.y);
    vz = abs(a.acceleration.z);
  }

  int raw = analogRead(SOIL_PIN);
  int soil = map(raw, 4095, 1500, 0, 100);
  soil = constrain(soil, 0, 100);

  Serial.println("Sending data...");
  Serial.print("Soil: "); Serial.print(soil);
  Serial.print(" | Vibration: ");
  Serial.print(vx); Serial.print(", ");
  Serial.print(vy); Serial.print(", ");
  Serial.println(vz);

  if (WiFi.status() == WL_CONNECTED) {
    WiFiClient client;
    HTTPClient http;

    http.begin(client, serverURL);
    http.addHeader("Content-Type", "application/json");

    String payload = "{";
    payload += "\"node_id\":" + String(NODE_ID) + ",";
    payload += "\"lat\":" + String(LAT, 5) + ",";
    payload += "\"lon\":" + String(LON, 5) + ",";
    payload += "\"soil_moisture\":" + String(soil) + ",";
    payload += "\"vibration_x\":" + String(vx, 2) + ",";
    payload += "\"vibration_y\":" + String(vy, 2) + ",";
    payload += "\"vibration_z\":" + String(vz, 2);
    payload += "}";

    int httpCode = http.POST(payload);
    Serial.print("HTTP Response: ");
    Serial.println(httpCode);

    http.end();
  }

  delay(5000);
}
