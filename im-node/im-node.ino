/*
 * INTELLIGENT MULTI-HAZARD DISASTER EARLY WARNING SYSTEM
 * SENSOR NODE 1 - IMPROVED VERSION
 * 
 * IMPROVEMENTS:
 * ✓ Sends ONLY raw sensor data (no processing)
 * ✓ Fixed I2C/MPU6050 communication issues
 * ✓ Better error handling for sensors
 * ✓ Proper ADC resolution configuration
 * ✓ Raw data values for server processing
 * ✓ Improved reliability and stability
 */

#include <WiFi.h>
#include <esp_now.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <esp_wifi.h>

// ========== PIN DEFINITIONS ==========
#define SOIL_PIN 34      // ADC pin for soil moisture (GPIO 34 = ADC1_CH6)
#define SDA_PIN 21       // I2C Data (GPIO 21)
#define SCL_PIN 22       // I2C Clock (GPIO 22)
#define FLAME_DO 27      // Flame digital output (GPIO 27)
#define FLAME_AO 35      // Flame analog output (GPIO 35 = ADC1_CH7)

// ========== NODE CONFIGURATION ==========
#define NODE_ID 1
#define LAT 10.020
#define LON 76.300
#define SENSOR_READ_INTERVAL_MS 5000  // Read every 5 seconds

// ========== GATEWAY MAC ADDRESS ==========
// IMPORTANT: Replace with your actual gateway MAC address
uint8_t GATEWAY_MAC[] = {0x00, 0x70, 0x07, 0x3A, 0x55, 0x58};

// ========== RAW DATA PACKET (Only Raw Values) ==========
typedef struct {
  uint32_t timestamp;      // Seconds since boot
  uint8_t node_id;
  float lat;
  float lon;
  int soil_raw;            // Raw ADC (0-4095) - NOT converted to %
  float vib_x;             // Raw acceleration (m/s²)
  float vib_y;
  float vib_z;
  float temperature;       // Raw temperature (°C)
  int flame_adc;           // Raw ADC (0-4095) - NOT distance
  bool flame_digital;      // Raw digital pin state
  uint8_t mpu_status;      // 0=OK, 1=ERROR, 2=DISCONNECTED
} RawSensorPacket;

RawSensorPacket sensorData;
Adafruit_MPU6050 mpu;
bool mpuOK = false;
uint8_t mpuErrorCount = 0;

// ========== ESP-NOW CALLBACK ==========
void onSent(const wifi_tx_info_t *info, esp_now_send_status_t status) {
  if (status == ESP_NOW_SEND_SUCCESS) {
    Serial.println("✓ Packet sent successfully");
  } else {
    Serial.println("✗ Packet send failed");
  }
}

// ========== SETUP ==========
void setup() {
  Serial.begin(115200);
  delay(2000);  // Wait for serial to initialize
  
  Serial.println("\n\n╔═══════════════════════════════════════╗");
  Serial.println("║  SENSOR NODE 1 - IMPROVED             ║");
  Serial.println("║  Raw Data Collection Only              ║");
  Serial.println("╚═══════════════════════════════════════╝\n");
  
  // ===== PIN CONFIGURATION =====
  Serial.println("[1/5] Configuring pins...");
  pinMode(FLAME_DO, INPUT);
  pinMode(SOIL_PIN, INPUT);
  
  // Configure ADC for 12-bit resolution (0-4095)
  analogReadResolution(12);
  Serial.println("  ✓ ADC resolution: 12-bit (0-4095)");
  Serial.println("  ✓ Soil pin: GPIO 34");
  Serial.println("  ✓ Flame AO pin: GPIO 35");
  Serial.println("  ✓ Flame DO pin: GPIO 27");
  
  // ===== WIFI INITIALIZATION (for ESP-NOW) =====
  Serial.println("\n[2/5] Initializing WiFi for ESP-NOW...");
  WiFi.mode(WIFI_STA);
  WiFi.disconnect(false);  // Don't turn off radio
  
  // Set WiFi channel to 11 (must match gateway)
  esp_wifi_set_channel(11, WIFI_SECOND_CHAN_NONE);
  Serial.println("  ✓ WiFi mode: STA");
  Serial.println("  ✓ Channel: 11");
  Serial.println("  ✓ Radio: ON (for ESP-NOW)");
  
  // ===== ESP-NOW INITIALIZATION =====
  Serial.println("\n[3/5] Initializing ESP-NOW...");
  if (esp_now_init() != ESP_OK) {
    Serial.println("  ✗ ERROR: ESP-NOW initialization failed!");
    while (1) {
      delay(1000);  // Halt
    }
  }
  
  // Register send callback
  esp_now_register_send_cb(onSent);
  
  // Add gateway as peer
  esp_now_peer_info_t peer = {};
  memcpy(peer.peer_addr, GATEWAY_MAC, 6);
  peer.channel = 11;
  peer.encrypt = false;
  
  if (esp_now_add_peer(&peer) != ESP_OK) {
    Serial.println("  ✗ ERROR: Failed to add gateway peer!");
    Serial.println("  CHECK: Is GATEWAY_MAC address correct?");
    while (1) {
      delay(1000);
    }
  }
  
  Serial.println("  ✓ Gateway peer added");
  Serial.print("  ✓ Gateway MAC: ");
  printMacAddress(GATEWAY_MAC);
  
  // ===== I2C INITIALIZATION =====
  Serial.println("\n[4/5] Initializing I2C & MPU6050...");
  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(100000);  // 100kHz I2C speed for reliability
  Serial.println("  ✓ I2C initialized (100kHz)");
  Serial.println("  ✓ SDA: GPIO 21");
  Serial.println("  ✓ SCL: GPIO 22");
  
  // Initialize MPU6050 with retries
  Serial.print("  Initializing MPU6050...");
  int mpu_attempts = 0;
  
  while (mpu_attempts < 3) {
    if (mpu.begin()) {
      mpuOK = true;
      mpu.setAccelerometerRange(MPU6050_RANGE_2_G);
      mpu.setGyroRange(MPU6050_RANGE_500_DEG);
      mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
      
      Serial.println(" ✓ OK");
      Serial.println("    - Range: ±2G");
      Serial.println("    - I2C Address: 0x68");
      sensorData.mpu_status = 0;  // OK
      break;
    } else {
      mpu_attempts++;
      if (mpu_attempts < 3) {
        Serial.print(".");
        delay(1000);
      }
    }
  }
  
  if (!mpuOK) {
    Serial.println(" ✗ FAILED");
    Serial.println("    WARNING: Continuing without MPU6050");
    Serial.println("    CHECK: I2C connection, address 0x68");
    sensorData.mpu_status = 2;  // DISCONNECTED
  }
  
  // ===== PRINT CONFIGURATION =====
  Serial.println("\n[5/5] Configuration Summary");
  Serial.print("  Node ID: ");
  Serial.println(NODE_ID);
  Serial.print("  Location: ");
  Serial.print(LAT, 3);
  Serial.print(", ");
  Serial.println(LON, 3);
  Serial.print("  Send interval: ");
  Serial.print(SENSOR_READ_INTERVAL_MS);
  Serial.println(" ms");
  Serial.print("  Packet size: ");
  Serial.print(sizeof(RawSensorPacket));
  Serial.println(" bytes");
  
  Serial.println("\n✓ Node ready! Starting sensor collection...");
  Serial.println("═══════════════════════════════════════\n");
}

// ========== MAIN LOOP ==========
void loop() {
  // Get timestamp (seconds since boot)
  sensorData.timestamp = (uint32_t)(millis() / 1000);
  sensorData.node_id = NODE_ID;
  sensorData.lat = LAT;
  sensorData.lon = LON;
  
  // ===== READ SOIL MOISTURE (RAW ADC) =====
  // NO conversion to percentage - send raw value
  sensorData.soil_raw = analogRead(SOIL_PIN);
  
  // ===== READ VIBRATION SENSOR (MPU6050) =====
  sensorData.vib_x = 0.0;
  sensorData.vib_y = 0.0;
  sensorData.vib_z = 0.0;
  sensorData.temperature = 0.0;
  
  if (mpuOK) {
    sensors_event_t accel, gyro, temp;
    
    if (mpu.getEvent(&accel, &gyro, &temp)) {
      // Read successful - get raw acceleration values
      sensorData.vib_x = accel.acceleration.x;
      sensorData.vib_y = accel.acceleration.y;
      sensorData.vib_z = accel.acceleration.z;
      sensorData.temperature = temp.temperature;
      
      sensorData.mpu_status = 0;  // OK
      mpuErrorCount = 0;  // Reset error counter
      
    } else {
      // Read failed
      mpuErrorCount++;
      
      if (mpuErrorCount >= 5) {
        // After 5 consecutive errors, mark as disconnected
        mpuOK = false;
        sensorData.mpu_status = 2;  // DISCONNECTED
        Serial.println("⚠ MPU6050 marked as disconnected (5 errors)");
      } else {
        sensorData.mpu_status = 1;  // ERROR
      }
    }
  }
  
  // ===== READ FLAME SENSOR (RAW ADC + DIGITAL) =====
  // NO distance calculation, NO flame detection logic
  // Send raw values only
  sensorData.flame_adc = analogRead(FLAME_AO);
  sensorData.flame_digital = (digitalRead(FLAME_DO) == LOW);  // LOW = flame detected
  
  // ===== PRINT DATA (for debugging) =====
  Serial.print("[");
  Serial.print(sensorData.timestamp);
  Serial.print("s] ");
  Serial.print("Soil_RAW:");
  Serial.print(sensorData.soil_raw);
  Serial.print(" | Vib(");
  Serial.print(sensorData.vib_x, 1);
  Serial.print(",");
  Serial.print(sensorData.vib_y, 1);
  Serial.print(",");
  Serial.print(sensorData.vib_z, 1);
  Serial.print(") | Temp:");
  Serial.print(sensorData.temperature, 1);
  Serial.print("°C | Flame_ADC:");
  Serial.print(sensorData.flame_adc);
  Serial.print(" | Flame_DO:");
  Serial.print(sensorData.flame_digital ? "LOW" : "HIGH");
  Serial.print(" | MPU:");
  
  if (sensorData.mpu_status == 0) Serial.print("OK");
  else if (sensorData.mpu_status == 1) Serial.print("ERR");
  else Serial.print("DIS");
  
  Serial.println();
  
  // ===== SEND VIA ESP-NOW =====
  esp_err_t result = esp_now_send(
    GATEWAY_MAC,
    (uint8_t*)&sensorData,
    sizeof(RawSensorPacket)
  );
  
  if (result != ESP_OK) {
    Serial.print("  ✗ Send failed: code ");
    Serial.println(result);
  }
  
  // Wait before next reading
  delay(SENSOR_READ_INTERVAL_MS);
}

// ========== UTILITY FUNCTIONS ==========

void printMacAddress(uint8_t *mac) {
  for (int i = 0; i < 6; i++) {
    if (mac[i] < 16) Serial.print("0");
    Serial.print(mac[i], HEX);
    if (i < 5) Serial.print(":");
  }
  Serial.println();
}