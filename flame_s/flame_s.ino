// KY-026 Flame Sensor - CORRECTED VERSION
// Digital and analog flame sensor with improved reliability

#define FLAME_DO 27      // Digital output pin
#define FLAME_AO 35      // Analog output pin
#define SAMPLES 10       // Number of samples for averaging
#define SENSITIVITY 0.7  // Analog threshold multiplier (0.5-0.8 recommended)

struct FlameData {
  int analog_raw;
  int analog_avg;
  int digital_value;
  bool flame_detected;
  int intensity;        // 0-100% (higher = more intense flame)
  int baseline;         // Ambient light level
  unsigned long timestamp;
  unsigned long last_detection;
};

FlameData flameData;
unsigned long lastReadTime = 0;

// Low-pass filter for analog readings
float filteredValue = 0;
const float FILTER_ALPHA = 0.3;  // 0 = no filtering, 1 = fast response

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n\n╔════════════════════════════════════╗");
  Serial.println("║   KY-026 FLAME SENSOR TEST (FIXED) ║");
  Serial.println("╚════════════════════════════════════╝\n");
  
  pinMode(FLAME_DO, INPUT);
  
  analogReadResolution(12);  // 0-4095 range
  
  Serial.println("Sensor initialized!");
  Serial.println("Digital: LOW = Flame detected, HIGH = No flame");
  Serial.println("Analog: Lower value = More intense flame\n");
  
  // Calibrate baseline
  calibrateBaseline();
  
  // Initialize filter
  filteredValue = flameData.baseline;
}

void loop() {
  readFlameSensor();
  printFlameData();
  
  // Check for rapid changes (fire flicker)
  detectFireCharacteristics();
  
  delay(200);  // Faster sampling for better flicker detection
}

void calibrateBaseline() {
  Serial.println("Calibrating ambient light baseline...");
  Serial.println("(Keep sensor away from flames)\n");
  
  long sum = 0;
  for (int i = 0; i < 30; i++) {
    sum += analogRead(FLAME_AO);
    Serial.print(".");
    delay(50);
  }
  Serial.println();
  
  flameData.baseline = sum / 30;
  filteredValue = flameData.baseline;
  
  Serial.print("✓ Baseline calibrated: ");
  Serial.println(flameData.baseline);
  Serial.println();
}

void readFlameSensor() {
  // Read digital value
  flameData.digital_value = digitalRead(FLAME_DO);
  
  // Read multiple analog samples for averaging
  long sum = 0;
  int minVal = 4096;
  int maxVal = 0;
  
  for (int i = 0; i < SAMPLES; i++) {
    int reading = analogRead(FLAME_AO);
    sum += reading;
    
    if (reading < minVal) minVal = reading;
    if (reading > maxVal) maxVal = reading;
    
    delayMicroseconds(500);
  }
  
  flameData.analog_raw = sum / SAMPLES;  // Average is more stable
  
  // Apply low-pass filter for noise reduction
  filteredValue = (FILTER_ALPHA * flameData.analog_raw) + 
                  ((1.0 - FILTER_ALPHA) * filteredValue);
  flameData.analog_avg = (int)filteredValue;
  
  // ===== FLAME DETECTION LOGIC =====
  // Digital LOW = flame (active low)
  bool digitalFlame = (flameData.digital_value == LOW);
  
  // Analog: lower value = more IR = flame present
  // Threshold: below (baseline * SENSITIVITY)
  // Example: if baseline=3000, threshold=3000*0.7=2100
  bool analogFlame = (flameData.analog_avg < (flameData.baseline * SENSITIVITY));
  
  // BOTH conditions should be true for reliable detection
  // This reduces false positives from ambient light or noise
  flameData.flame_detected = (digitalFlame && analogFlame);
  
  // ===== CALCULATE INTENSITY =====
  // Based on how far below baseline we are
  if (flameData.analog_avg < flameData.baseline) {
    int diff = flameData.baseline - flameData.analog_avg;
    int range = flameData.baseline;
    
    // Map: 0 diff = 0%, full range = 100%
    flameData.intensity = map(diff, 0, range, 0, 100);
    flameData.intensity = constrain(flameData.intensity, 0, 100);
  } else {
    flameData.intensity = 0;
  }
  
  if (flameData.flame_detected) {
    flameData.last_detection = millis();
  }
  
  flameData.timestamp = millis();
}

void printFlameData() {
  Serial.println("═══════ Flame Sensor Readings ═════════");
  
  // Digital status
  Serial.print("Digital: ");
  Serial.print(flameData.digital_value ? "HIGH" : "LOW");
  Serial.print(" | ");
  
  // Flame detection status
  if (flameData.flame_detected) {
    Serial.println("🔥 FLAME DETECTED");
  } else {
    Serial.println("✓ NO FLAME");
  }
  
  // Analog values
  Serial.print("Analog - Raw: ");
  Serial.print(flameData.analog_raw);
  Serial.print(" | Filtered: ");
  Serial.print(flameData.analog_avg);
  Serial.print(" | Baseline: ");
  Serial.println(flameData.baseline);
  
  // Threshold line
  int threshold = flameData.baseline * SENSITIVITY;
  Serial.print("Threshold: ");
  Serial.print(threshold);
  Serial.print(" (");
  Serial.print((int)(SENSITIVITY * 100));
  Serial.println("% of baseline)");
  
  // Intensity bar
  Serial.print("Intensity: ");
  Serial.print(flameData.intensity);
  Serial.print("% [");
  
  // Visual bar
  int barLength = map(flameData.intensity, 0, 100, 0, 20);
  for (int i = 0; i < 20; i++) {
    if (i < barLength) {
      Serial.print("=");
    } else {
      Serial.print(" ");
    }
  }
  Serial.println("]");
  
  // Status
  if (flameData.flame_detected) {
    Serial.println("Status: 🔴 ACTIVE FLAME");
  } else if (flameData.intensity > 30) {
    Serial.println("Status: 🟡 POSSIBLE FLAME (waiting for confirmation)");
  } else {
    unsigned long timeSince = millis() - flameData.last_detection;
    Serial.print("Status: 🟢 SAFE (");
    Serial.print(timeSince / 1000);
    Serial.println("s since last flame)");
  }
  
  Serial.println("═════════════════════════════════════════\n");
}

void detectFireCharacteristics() {
  static int lastIntensity = 0;
  static unsigned long lastFlicker = 0;
  static int flickerCount = 0;
  
  // Detect flame flicker (characteristic of fire)
  int diff = abs(flameData.intensity - lastIntensity);
  
  if (diff > 10) {  // Significant intensity change
    flickerCount++;
    
    if (flickerCount > 2) {
      Serial.println("⚠️  FLAME FLICKER PATTERN DETECTED!");
      flickerCount = 0;
    }
  } else {
    flickerCount = 0;
  }
  
  lastIntensity = flameData.intensity;
  
  // Warning for sustained intense flame
  if (flameData.flame_detected && 
      flameData.intensity > 70) {
    unsigned long sustainedTime = millis() - flameData.last_detection;
    
    if (sustainedTime > 10000) {  // More than 10 seconds
      Serial.println("🚨 SUSTAINED HIGH INTENSITY FLAME - POTENTIAL FIRE!");
    }
  }
}