#include <WiFi.h>
#include <WebServer.h>
#include <PubSubClient.h>

const char* ssid = "realme 8";
const char* password = "1234567890";
const char* mqtt_server = "192.168.1.100";

WiFiClient espClient;
PubSubClient mqttClient(espClient);
WebServer server(80);

void reconnectMQTT() {
  while (!mqttClient.connected()) {
    Serial.print("Reconnecting MQTT...");
    if (mqttClient.connect("ESP32_Repeater")) {
      Serial.println("connected");
    } else {
      Serial.print("failed, rc=");
      Serial.print(mqttClient.state());
      delay(2000);
    }
  }
}

void handleData() {
  if (!server.hasArg("plain")) {
    server.send(400, "text/plain", "No data");
    return;
  }

  String payload = server.arg("plain");
  Serial.println("Received from sensor: " + payload);

  if (mqttClient.connected()) {
    mqttClient.publish("disaster/repeater/data", payload.c_str(), true);
  }

  server.send(200, "text/plain", "OK");
}

void setup() {
  Serial.begin(115200);

  WiFi.begin(ssid, password);
  unsigned long startAttemptTime = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - startAttemptTime < 15000) {
    delay(500);
  }

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi Failed");
    return;
  }

  Serial.print("Repeater IP: ");
  Serial.println(WiFi.localIP());

  mqttClient.setServer(mqtt_server, 1883);
  reconnectMQTT();

  server.on("/data", HTTP_POST, handleData);
  server.begin();

  Serial.println("Repeater ready");
}

void loop() {
  if (!mqttClient.connected()) {
    reconnectMQTT();
  }
  mqttClient.loop();
  server.handleClient();
}
