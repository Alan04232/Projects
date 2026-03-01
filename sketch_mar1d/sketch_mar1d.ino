// Soil Moisture Sensor - IMPROVED VERSION
// Capacitive sensor with better filtering, hysteresis, and error detection

#define SOIL_PIN 34        // ADC pin for soil sensor
#define SOIL_DRY 3500      // Calibration: dry soil (adjust based on your sensor)
#define SOIL_WET 1500      // Calibration: saturated soil (adjust based on your sensor)
#define SAMPLES 10         // Number of samples for averaging
#define FILTER_ALPHA 0.3   // Low-pass filter (0=smooth, 1=responsive)

// Status codes (more memory efficient than strings)
#define STATUS_DRY 0
#define STATUS_MOIST 1
#define STATUS_WET 2
#define STATUS_VERY_WET 3
#define STATUS_ERROR 4

// Hysteresis boundaries (% moisture)
#define THRESHOLD_DRY_LOW 25      // Lower boundary (dry state)
#define THRESHOLD_DRY_HIGH 35     // Upper boundary (transition zone)
#define THRESHOLD_MOIST_LOW 45    // Lower boundary (moist state)
#define THRESHOLD_MOIST_HIGH 70   // Upper boundary (transition zone)
#define THRESHOLD_WET_HIGH 85     // Upper boundary (wet state)

struct SoilData {
  int raw_value;
  int raw_filtered;          // Filtered raw value
  int moisture_percent;
  int min_raw;
  int max_raw;
  int status_code;           // Use codes instead of strings
  unsigned long timestamp;
  bool error_detected;
  String error_message;      // Only for errors
};

SoilData soilData;
float filteredRaw = 0;
int previous_status = STATUS_MOIST;  // Start neutral

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n\n╔════════════════════════════════════════╗");
  Serial.println("║   SOIL MOISTURE SENSOR (IMPROVED)    ║");
  Serial.println("╚════════════════════════════════════════╝\n");
  
  // Configure ADC
  analogReadResolution(12);  // 0-4095 range
  
  Serial.println("Sensor ready!");
  Serial.print("Calibration: DRY=");
  Serial.print(SOIL_DRY);
  Serial.print(", WET=");
  Serial.println(SOIL_WET);
  Serial.println("Thresholds:");
  Serial.print("  Dry if < ");
  Serial.print(THRESHOLD_DRY_HIGH);
  Serial.println("%");
  Serial.print("  Moist if ");
  Serial.print(THRESHOLD_DRY_HIGH);
  Serial.print("% - ");
  Serial.print(THRESHOLD_MOIST_HIGH);
  Serial.println("%");
  Serial.print("  Wet if > ");
  Serial.print(THRESHOLD_WET_HIGH);
  Serial.println("%\n");
  
  // Initial calibration check
  performCalibrationCheck();
  
  // Initialize filter with first reading
  for (int i = 0; i < 5; i++) {
    filteredRaw = (FILTER_ALPHA * analogRead(SOIL_PIN)) + 
                  ((1.0 - FILTER_ALPHA) * filteredRaw);
    delay(50);
  }
}

void loop() {
  readSoilSensor();
  printSoilData();
  
  delay(1000);  // Read every 1 second (adjustable)
}

// ===== READ SOIL SENSOR WITH FILTERING =====
void readSoilSensor() {
  // Read multiple samples
  long sum = 0;
  int minVal = 4096;
  int maxVal = 0;
  
  for (int i = 0; i < SAMPLES; i++) {
    int reading = analogRead(SOIL_PIN);
    sum += reading;
    
    if (reading < minVal) minVal = reading;
    if (reading > maxVal) maxVal = reading;
    
    delayMicroseconds(500);
  }
  
  // Calculate raw average
  soilData.raw_value = sum / SAMPLES;
  soilData.min_raw = minVal;
  soilData.max_raw = maxVal;
  
  // Apply low-pass filter for smoothing
  filteredRaw = (FILTER_ALPHA * soilData.raw_value) + 
                ((1.0 - FILTER_ALPHA) * filteredRaw);
  soilData.raw_filtered = (int)filteredRaw;
  
  // ===== ERROR DETECTION =====
  soilData.error_detected = false;
  soilData.error_message = "";
  
  if (soilData.raw_filtered > SOIL_DRY + 300) {
    soilData.error_detected = true;
    soilData.error_message = "ERROR: Reading too high (sensor disconnected?)";
    soilData.status_code = STATUS_ERROR;
  } else if (soilData.raw_filtered < SOIL_WET - 300) {
    soilData.error_detected = true;
    soilData.error_message = "ERROR: Reading too low (sensor flooded/short?)";
    soilData.status_code = STATUS_ERROR;
  } else {
    // ===== CONVERT TO PERCENTAGE (with bounds) =====
    soilData.moisture_percent = map(soilData.raw_filtered, SOIL_DRY, SOIL_WET, 0, 100);
    soilData.moisture_percent = constrain(soilData.moisture_percent, 0, 100);
    
    // ===== DETERMINE STATUS WITH HYSTERESIS =====
    determineStatus();
  }
  
  soilData.timestamp = millis();
}

// ===== HYSTERESIS-BASED STATUS DETERMINATION =====
void determineStatus() {
  int current_status = previous_status;  // Default: keep previous status
  
  // Dry state (moisture < 35%)
  if (soilData.moisture_percent < THRESHOLD_DRY_LOW) {
    current_status = STATUS_DRY;
  }
  // Transition zone (35% - 45%)
  else if (soilData.moisture_percent >= THRESHOLD_DRY_HIGH && 
           soilData.moisture_percent < THRESHOLD_MOIST_LOW) {
    // Stay in previous state (don't flip-flop)
    current_status = previous_status;
  }
  // Moist state (45% - 85%)
  else if (soilData.moisture_percent >= THRESHOLD_MOIST_LOW && 
           soilData.moisture_percent <= THRESHOLD_MOIST_HIGH) {
    current_status = STATUS_MOIST;
  }
  // Wet state (> 85%)
  else if (soilData.moisture_percent > THRESHOLD_WET_HIGH) {
    current_status = STATUS_VERY_WET;
  }
  // Intermediate wet zone (70% - 85%)
  else {
    if (soilData.moisture_percent > THRESHOLD_MOIST_HIGH) {
      current_status = STATUS_WET;
    }
  }
  
  soilData.status_code = current_status;
  previous_status = current_status;  // Remember for next iteration
}

// ===== PRINT SENSOR DATA =====
void printSoilData() {
  Serial.println("╔════════════════════════════════════════╗");
  Serial.println("║    SOIL MOISTURE READINGS              ║");
  Serial.println("╚════════════════════════════════════════╝");
  
  // Check for errors
  if (soilData.error_detected) {
    Serial.println("⚠️  " + soilData.error_message);
    Serial.println();
    return;
  }
  
  // Raw values
  Serial.print("Raw ADC:  ");
  Serial.print(soilData.raw_value);
  Serial.print(" (filtered: ");
  Serial.print(soilData.raw_filtered);
  Serial.print(", range: ");
  Serial.print(soilData.min_raw);
  Serial.print("-");
  Serial.print(soilData.max_raw);
  Serial.println(")");
  
  // Moisture percentage
  Serial.print("Moisture: ");
  Serial.print(soilData.moisture_percent);
  Serial.print("% | Status: ");
  printStatus(soilData.status_code);
  Serial.println();
  
  // Visual bar graph
  Serial.print("Graph:    [");
  int bars = map(soilData.moisture_percent, 0, 100, 0, 20);
  for (int i = 0; i < 20; i++) {
    if (i < bars) {
      Serial.print("█");
    } else {
      Serial.print("░");
    }
  }
  Serial.print("] ");
  Serial.print(soilData.moisture_percent);
  Serial.println("%");
  
  // Thresholds indicator
  Serial.print("Zones:    ");
  if (soilData.moisture_percent < THRESHOLD_DRY_HIGH) {
    Serial.print("🔴 DRY ");
  } else if (soilData.moisture_percent < THRESHOLD_MOIST_LOW) {
    Serial.print("🟡 TRANSITION ");
  } else if (soilData.moisture_percent < THRESHOLD_MOIST_HIGH) {
    Serial.print("🟢 MOIST ");
  } else if (soilData.moisture_percent < THRESHOLD_WET_HIGH) {
    Serial.print("🔵 WET ");
  } else {
    Serial.print("🟣 VERY WET ");
  }
  Serial.println();
  
  Serial.println("═══════════════════════════════════════════\n");
}

// ===== PRINT STATUS BASED ON CODE =====
void printStatus(int code) {
  switch (code) {
    case STATUS_DRY:
      Serial.print("🔴 DRY - WATER NEEDED!");
      break;
    case STATUS_MOIST:
      Serial.print("🟢 MOIST - GOOD");
      break;
    case STATUS_WET:
      Serial.print("🔵 WET - OK");
      break;
    case STATUS_VERY_WET:
      Serial.print("🟣 VERY WET - TOO MUCH WATER");
      break;
    case STATUS_ERROR:
      Serial.print("⚠️  ERROR - CHECK SENSOR");
      break;
    default:
      Serial.print("? UNKNOWN");
  }
}

// ===== CALIBRATION CHECK =====
void performCalibrationCheck() {
  Serial.println("┌─ Calibration Check ─────────────────┐");
  
  // Take average reading
  long sum = 0;
  for (int i = 0; i < 20; i++) {
    sum += analogRead(SOIL_PIN);
    delay(25);
  }
  int current = sum / 20;
  
  Serial.print("│ Current reading: ");
  Serial.print(current);
  Serial.println("                      │");
  
  // Check which range it's in
  float from_dry = abs(current - SOIL_DRY);
  float from_wet = abs(current - SOIL_WET);
  float from_mid = abs(current - ((SOIL_DRY + SOIL_WET) / 2));
  
  Serial.print("│ Distance from DRY: ");
  Serial.print((int)from_dry);
  Serial.println("                  │");
  Serial.print("│ Distance from WET: ");
  Serial.print((int)from_wet);
  Serial.println("                  │");
  
  if (from_dry < from_wet) {
    Serial.println("│ Status: Close to DRY calibration     │");
  } else if (from_wet < from_dry) {
    Serial.println("│ Status: Close to WET calibration     │");
  } else {
    Serial.println("│ Status: Between DRY and WET          │");
  }
  
  Serial.println("│                                      │");
  Serial.println("│ CALIBRATION GUIDE:                   │");
  Serial.println("│ 1. Place sensor in DRY soil/air      │");
  Serial.println("│ 2. Note the ADC reading              │");
  Serial.println("│ 3. Update SOIL_DRY constant          │");
  Serial.println("│ 4. Place sensor in WET/saturated     │");
  Serial.println("│ 5. Note the ADC reading              │");
  Serial.println("│ 6. Update SOIL_WET constant          │");
  Serial.println("└──────────────────────────────────────┘\n");
}