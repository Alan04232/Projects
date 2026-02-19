#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <Wire.h>

#define I2C_SDA 21
#define I2C_SCL 22
#define SOIL_DATA_PIN 34 

Adafruit_MPU6050 mpu;

void setup() {
  // 1. Start Serial IMMEDIATELY
  Serial.begin(115200);
  delay(1000); 
  Serial.println("\n--- Serial Started! ---");

  // 2. Initialize I2C
  Wire.begin(I2C_SDA, I2C_SCL);
  Serial.println("I2C Bus Initialized...");

  // 3. Try MPU6050 but DON'T freeze if it fails
  if (!mpu.begin()) {
    Serial.println("CRITICAL: MPU6050 not found! Check SDA(21) and SCL(22)");
  } else {
    Serial.println("MPU6050 Online!");
  }

  analogReadResolution(12); 
  Serial.println("Setup Complete. Starting Loop...\n");
}

void loop() {
  // Heartbeat - shows the ESP32 is actually looping
  Serial.print("."); 

  sensors_event_t a, g, temp;
  bool mpuSuccess = mpu.getEvent(&a, &g, &temp);

  int rawSoilValue = analogRead(SOIL_DATA_PIN);
  
  if(mpuSuccess) {
    Serial.print(" [Accel X: "); Serial.print(a.acceleration.x);
    Serial.print(" [Accel Y: "); Serial.print(a.acceleration.y);
    Serial.print(" [Accel Z: "); Serial.print(a.acceleration.z);
    Serial.print(" | Soil: "); Serial.print(rawSoilValue);
    Serial.println("]");
  } else {
    Serial.print(" [MPU Error | Soil: "); Serial.print(rawSoilValue);
    Serial.println("]");
  }

  delay(1000); 
}