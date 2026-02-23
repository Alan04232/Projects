#include <WiFi.h>

// Replace with your network credentials
const char* ssid = "Realme";
const char* password = "";

// Create a WiFi server on port 80
WiFiServer server(80);

void setup() {
  Serial.begin(115200);

  // Connect to Wi-Fi
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConnected!");
  Serial.print("ESP32 IP Address: ");
  Serial.println(WiFi.localIP());

  // Start the server
  server.begin();
}

void loop() {
  WiFiClient client = server.available();   // Listen for incoming clients

  if (client) {
    Serial.println("New Client Connected.");
    String request = client.readStringUntil('\r');  // Read client request
    Serial.println("Received: " + request);
    client.flush();

    // Send response back to client
    client.println("Hello from ESP32! You sent: " + request);

    // Close connection
    client.stop();
    Serial.println("Client Disconnected.");
  }
}