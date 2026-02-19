#include <WiFi.h>
#include <WebServer.h>
#include <HTTPClient.h>

const char* ssid = "N00384";
const char* password = "01010123";

/* 👉 PUT FLASK SERVER PC IP */
const char* serverURL = "http://192.168.1.100:5000/node-data";

WebServer server(80);

void handleNodeData() {

  String payload = server.arg("plain");

  Serial.println("From node: " + payload);

  if (WiFi.status() == WL_CONNECTED) {

    HTTPClient http;
    http.begin(serverURL);
    http.addHeader("Content-Type","application/json");

    int code = http.POST(payload);

    Serial.println("To server: " + String(code));

    http.end();
    server.send(200,"text/plain","OK");
  } 
  else {
    server.send(500,"text/plain","WiFi lost");
  }
}

void connectWiFi() {
  WiFi.begin(ssid,password);
  Serial.print("WiFi");
  while (WiFi.status()!=WL_CONNECTED){
    delay(500);
    Serial.print(".");
  }
  Serial.println(" connected");
}

void setup() {
  Serial.begin(115200);
  connectWiFi();

  Serial.print("Gateway IP: ");
  Serial.println(WiFi.localIP());

  server.on("/node-data",HTTP_POST,handleNodeData);
  server.begin();
}

void loop() {
  server.handleClient();

  if (WiFi.status()!=WL_CONNECTED)
    connectWiFi();
}
