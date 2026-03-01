#include <WiFi.h>
#include <esp_now.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <esp_wifi.h>

// vcc is 3.3 V for all
#define SOIL_PIN 34
#define SDA_PIN 21
#define SCL_PIN 22
#define FLAME_DO 27
#define FLAME_AO 35
#define SOIL_DRY 4095
#define SOIL_WET 1500
#define NODE_ID 1
#define LAT 10.020
#define LON 76.300

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
  float temp;           // Changed from humidity (more useful from MPU)
  float dist;
  bool flame;
} NodePacket;

NodePacket data;
float K = 800000.0;

// ===== Flame detection history =====
const int FLAME_HISTORY_SIZE = 5;
int flameHistory[FLAME_HISTORY_SIZE] = {0};
int flameIndex = 0;

// ===== NEW ESP-NOW send callback (ESP32 core ≥3.x) =====
void onSent(const wifi_tx_info_t *info, esp_now_send_status_t status) {
  Serial.print("ESP-NOW send: ");
  Serial.println(status == ESP_NOW_SEND_SUCCESS ? "OK" : "FAIL");
}

float estimateDistance(int adc) {
  if (adc < 1200 || adc > 3800) {
    return -1.0;
  }
  return sqrt(K / adc);
}

// Improved flame detection with history-based filtering
bool isRealFlame(int adc, int digital) {
  // Flame detected if digital LOW and ADC in valid range
  bool flameDetected = (digital == LOW && adc > 1200 && adc < 3800);
  
  // Store in history
  flameHistory[flameIndex] = flameDetected ? 1 : 0;
  flameIndex = (flameIndex + 1) % FLAME_HISTORY_SIZE;
  
  // Count detections in history - need at least 3/5 for confidence
  int count = 0;
  for (int i = 0; i < FLAME_HISTORY_SIZE; i++) {
    count += flameHistory[i];
  }
  
  return count >= 3;  // Majority voting
}

void setup() {
  Serial.begin(115200);
  delay(1000);  // Give serial time to start
  Serial.println("\n\nNode Starting...");
  
  pinMode(FLAME_DO, INPUT);

  // --- WiFi STA mode ---
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();

  // --- Match gateway channel (11) ---
  esp_wifi_set_channel(11, WIFI_SECOND_CHAN_NONE);

  // --- Init ESP-NOW ---
  if (esp_now_init() != ESP_OK) {
    Serial.println("ERROR: ESP-NOW init failed");
    return;
  }

  esp_now_register_send_cb(onSent);

  // --- Add peer ---
  esp_now_peer_info_t peer{};
  memcpy(peer.peer_addr, GATEWAY_MAC, 6);
  peer.channel = 11;   // must match gateway
  peer.encrypt = false;

  if (esp_now_add_peer(&peer) != ESP_OK) {
    Serial.println("ERROR: Peer add failed");
    return;
  }

  // --- Sensors ---
  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(100000); // Slower I2C for reliability

  // Try to initialize MPU6050 with retry
  int attempts = 0;
  while (attempts < 3) {
    if (mpu.begin()) {
      mpuOK = true;
      mpu.setAccelerometerRange(MPU6050_RANGE_2_G);
      mpu.setGyroRange(MPU6050_RANGE_500_DEG);
      Serial.println("✓ MPU6050 initialized successfully");
      break;
    } else {
      Serial.print("MPU6050 not found, retrying... (");
      Serial.print(attempts + 1);
      Serial.println("/3)");
      delay(1000);
      attempts++;
    }
  }
  
  if (!mpuOK) {
    Serial.println("⚠ WARNING: MPU6050 failed to initialize - will continue without it");
  }

  analogReadResolution(12);

  Serial.println("✓ Node ready (ESP-NOW ch11)");
  Serial.println("-----------------------------------");
}

void loop() {
  // --- Read flame sensor ---
  int flameADC = analogRead(FLAME_AO);
  int flameDigital = digitalRead(FLAME_DO);

  // --- Read vibration (accel) ---
  float vib_x = 0, vib_y = 0, vib_z = 0;
  float temp = 0;

  if (mpuOK) {
    sensors_event_t a, g, t;
    
    // Check for sensor errors
    if (mpu.getEvent(&a, &g, &t)) {
      vib_x = a.acceleration.x;
      vib_y = a.acceleration.y;
      vib_z = a.acceleration.z;
      temp = t.temperature;
      
      // Sanity check: accel should be roughly ±20m/s² in normal conditions
      if (abs(vib_x) > 50 || abs(vib_y) > 50 || abs(vib_z) > 50) {
        Serial.println("⚠ WARNING: Accelerometer values out of expected range");
      }
    } else {
      Serial.println("⚠ WARNING: MPU6050 read error");
      mpuOK = false;
    }
  }

  // --- Read soil moisture ---
  int raw = analogRead(SOIL_PIN);
  int soil = map(raw, SOIL_DRY, SOIL_WET, 0, 100);
  soil = constrain(soil, 0, 100);
  
  // --- Estimate distance ---
  float dist = estimateDistance(flameADC);
  
  // --- Detect flame (with filtering) ---
  bool flame = isRealFlame(flameADC, flameDigital);

  // --- Fill packet ---
  data.node_id = NODE_ID;
  data.lat = LAT;
  data.lon = LON;
  data.soil = soil;
  data.vib_x = vib_x;
  data.vib_y = vib_y;
  data.vib_z = vib_z;
  data.temp = temp;           // Now using actual temperature
  data.dist = dist;
  data.flame = flame;

  // --- Serial output ---
  Serial.print("Soil: ");
  Serial.print(soil);
  Serial.print("% | Flame ADC: ");
  Serial.print(flameADC);
  Serial.print(" | Flame: ");
  Serial.print(flame ? "YES" : "NO");
  Serial.print(" | Dist: ");
  if (dist < 0) {
    Serial.print("N/A");
  } else {
    Serial.print(dist, 2);
    Serial.print("cm");
  }
  Serial.print(" | Temp: ");
  Serial.print(temp, 1);
  Serial.print("°C | Vib(X,Y,Z): ");
  Serial.print(vib_x, 2);
  Serial.print(", ");
  Serial.print(vib_y, 2);
  Serial.print(", ");
  Serial.println(vib_z, 2);

  // --- Send via ESP-NOW ---
  esp_err_t result = esp_now_send(GATEWAY_MAC, (uint8_t*)&data, sizeof(data));

  if (result != ESP_OK) {
    Serial.print("ERROR: ESP-NOW send failed with code ");
    Serial.println(result);
    // Optional: add retry logic here if needed
  }

  delay(5000);  // Send every 5 seconds
}