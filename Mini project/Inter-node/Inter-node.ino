#include <WiFi.h>
#include <WebServer.h>
#include <HTTPClient.h>

const char* ssid = "YOUR_WIFI";
const char* password = "YOUR_PASSWORD";

// Server (PC) IP
const char* serverURL = "http://192.168.1.100/node-data";

WebServer server(80);

void handleNodeData() {
  String payload = server.arg("plain");

  HTTPClient http;
  http.begin(serverURL);
  http.addHeader("Content-Type", "application/json");
  http.POST(payload);
  http.end();

  server.send(200, "text/plain", "OK");
}

void setup() {
  Serial.begin(115200);

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
  }

  server.on("/node-data", HTTP_POST, handleNodeData);
  server.begin();
}

void loop() {
  server.handleClient();
}
