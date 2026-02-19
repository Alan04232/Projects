#include <WiFi.h>
#include <esp_now.h>
#include <HTTPClient.h>

// ===== WiFi to Flask =====
const char* ssid="N00384";
const char* password="01010123";
const char* serverURL="http://192.168.137.1:5000/node-data";

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

NodePacket incoming;

// ===== ESP-NOW receive =====
void onReceive(const uint8_t *mac,const uint8_t *data,int len){
  memcpy(&incoming,data,sizeof(incoming));

  Serial.println("ESP-NOW packet received");

  // Convert to JSON
  String payload="{";
  payload+="\"node_id\":"+String(incoming.node_id)+",";
  payload+="\"lat\":"+String(incoming.lat,5)+",";
  payload+="\"lon\":"+String(incoming.lon,5)+",";
  payload+="\"soil_moisture\":"+String(incoming.soil)+",";
  payload+="\"vib_x\":"+String(incoming.vib_x,3)+",";
  payload+="\"vib_y\":"+String(incoming.vib_y,3)+",";
  payload+="\"vib_z\":"+String(incoming.vib_z,3)+",";
  payload+="\"humidity\":"+String(incoming.humidity,1)+"}";

  if(WiFi.status()==WL_CONNECTED){
    HTTPClient http;
    http.begin(serverURL);
    http.addHeader("Content-Type","application/json");
    int code=http.POST(payload);
    Serial.print("HTTP->Server: ");
    Serial.println(code);
    http.end();
  } else {
    Serial.println("WiFi not connected");
  }
}

void connectWiFi(){
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid,password);

  Serial.print("WiFi");
  while(WiFi.status()!=WL_CONNECTED){
    delay(500);
    Serial.print(".");
  }
  Serial.println(" connected");

  Serial.print("Gateway IP: ");
  Serial.println(WiFi.localIP());
}

void setup(){
  Serial.begin(115200);

  connectWiFi();

  if(esp_now_init()!=ESP_OK){
    Serial.println("ESP-NOW init fail");
    return;
  }

  esp_now_register_recv_cb(onReceive);

  Serial.println("Gateway ready");
}

void loop(){
}
