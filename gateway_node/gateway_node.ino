#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include <HTTPClient.h>

// ================= WiFi =================
const char* ssid = "N00384";
const char* password = "01010123";
const char* serverURL = "http://192.168.137.1:5000/node-data";

// ================= Packet =================
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

volatile bool newPacket = false;
NodePacket incoming;

// ================= ESP-NOW RECEIVE =================
void onReceive(const esp_now_recv_info *info, const uint8_t *data, int len) {

  if (len != sizeof(NodePacket)) return;

  memcpy(&incoming, data, sizeof(incoming));

  Serial.println("\n===== DATA RECEIVED FROM NODE =====");

  // Sender MAC
  Serial.print("Sender MAC: ");
  for (int i = 0; i < 6; i++) {
    Serial.printf("%02X", info->src_addr[i]);
    if (i < 5) Serial.print(":");
  }
  Serial.println();

  // Sensor values
  Serial.print("Node ID: "); Serial.println(incoming.node_id);
  Serial.print("Lat: "); Serial.println(incoming.lat, 5);
  Serial.print("Lon: "); Serial.println(incoming.lon, 5);
  Serial.print("Soil: "); Serial.println(incoming.soil);
  Serial.print("VibX: "); Serial.println(incoming.vib_x, 3);
  Serial.print("VibY: "); Serial.println(incoming.vib_y, 3);
  Serial.print("VibZ: "); Serial.println(incoming.vib_z, 3);
  Serial.print("Humidity: "); Serial.println(incoming.humidity, 1);

  Serial.println("==================================");

  newPacket = true;
}

// ================= WIFI CONNECT =================
void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  Serial.print("WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println(" connected");
  Serial.print("Gateway IP: ");
  Serial.println(WiFi.localIP());

  WiFi.setSleep(false);

  esp_wifi_set_channel(WiFi.channel(), WIFI_SECOND_CHAN_NONE);

  Serial.print("WiFi channel: ");
  Serial.println(WiFi.channel());
}

// ================= SETUP =================
void setup() {
  Serial.begin(115200);

  connectWiFi();

  if (esp_now_init() != ESP_OK) {
    Serial.println("ESP-NOW init failed");
    return;
  }

  esp_now_register_recv_cb(onReceive);

  Serial.println("Gateway ready (ESP-NOW + WiFi)");
}

// ================= LOOP =================
void loop() {

  if (!newPacket) return;
  newPacket = false;

  // Create JSON payload
  String payload = "{";
  payload += "\"node_id\":" + String(incoming.node_id) + ",";
  payload += "\"lat\":" + String(incoming.lat, 5) + ",";
  payload += "\"lon\":" + String(incoming.lon, 5) + ",";
  payload += "\"soil_moisture\":" + String(incoming.soil) + ",";
  payload += "\"vib_x\":" + String(incoming.vib_x, 3) + ",";
  payload += "\"vib_y\":" + String(incoming.vib_y, 3) + ",";
  payload += "\"vib_z\":" + String(incoming.vib_z, 3) + ",";
  payload += "\"humidity\":" + String(incoming.humidity, 1) + "}";

  Serial.println("\n----- JSON SENT TO SERVER -----");
  Serial.println(payload);

  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(serverURL);
    http.addHeader("Content-Type", "application/json");

    int code = http.POST(payload);

    Serial.print("Server response: ");
    Serial.println(code);

    http.end();
  } else {
    Serial.println("WiFi lost");
  }

  Serial.println("------------------------------");
}
