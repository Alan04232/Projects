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

#define SOIL_DRY 4095
#define SOIL_WET 1500

const char* ssid = "N00384";
const char* password = "01010123";

/* 👉 PUT INTERMEDIATE ESP32 IP HERE */
const char* gatewayURL = "http://192.168.137.1:5000/node-data";

Adafruit_MPU6050 mpu;
bool mpuOK = false;

void connectWiFi() {
  WiFi.begin(ssid, password);
  Serial.print("WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println(" connected");
}

void setup() {
  Serial.begin(115200);
  connectWiFi();

  Serial.print("Node IP: ");
  Serial.println(WiFi.localIP());

  Serial.print("Target GW: ");
  Serial.println(gatewayURL);

  Wire.begin(SDA_PIN, SCL_PIN);

  if (mpu.begin()) {
    mpuOK = true;
    mpu.setAccelerometerRange(MPU6050_RANGE_2_G);
  }

  analogReadResolution(12);
  connectWiFi();
}

void loop() {

  if (WiFi.status() != WL_CONNECTED)
    connectWiFi();

  float vib_x=0, vib_y=0, vib_z=0;

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

  String payload = "{";
  payload += "\"node_id\":1,";
  payload += "\"lat\":" + String(LAT,5) + ",";
  payload += "\"lon\":" + String(LON,5) + ",";
  payload += "\"soil_moisture\":" + String(soil) + ",";
  payload += "\"vib_x\":" + String(vib_x,3) + ",";
  payload += "\"vib_y\":" + String(vib_y,3) + ",";
  payload += "\"vib_z\":" + String(vib_z,3) + ",";
  payload += "\"humidity\":70}";
  
  HTTPClient http;
  http.begin(gatewayURL);
  http.addHeader("Content-Type","application/json");

  int code = http.POST(payload);
  Serial.println("POST->GW: " + String(code));

  http.end();
  delay(5000);
}
