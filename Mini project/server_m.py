
+from __future__ import annotations
+
+from datetime import datetime
+import json
+from typing import Any, Dict, Tuple
+
 from flask import Flask, jsonify, render_template
 import paho.mqtt.client as mqtt
-import json
-from datetime import datetime
 
 app = Flask(__name__)
 
-#test data
-test_data = {
-    "node_id": 99,
-    "lat": 10.2,
-    "lon": 76.5,
-    "soil": 90,
-    "vibration": 0.08,
-    "humidity": 88
-}
-risk, prob = predict_risk(test_data)
-node_data[99] = {
-    "lat": test_data["lat"],
-    "lon": test_data["lon"],
-    "risk": risk,
-    "probability": round(prob * 100, 1),
-    "data": test_data,
-    "time": datetime.now().strftime("%H:%M:%S")
-}
 # -------------------------------
 # NODE DATA STORE
 # -------------------------------
-node_data = {}
+node_data: Dict[int, Dict[str, Any]] = {}
 
-# -------------------------------
-# SIMPLE ML RISK PREDICTION
-# -------------------------------
-def predict_risk(data):
-    soil = data.get("soil", 0)
-    vibration = data.get("vibration", 0)
-    humidity = data.get("humidity", 0)
 
-    score = 0
-    if soil > 70: score += 0.4
-    if vibration > 0.05: score += 0.4
-    if humidity > 80: score += 0.2
+def predict_risk(data: Dict[str, Any]) -> Tuple[str, float]:
+    """Compute a simple landslide risk score from incoming sensor data."""
+    soil = float(data.get("soil", 0))
+    vibration = float(data.get("vibration", 0))
+    humidity = float(data.get("humidity", 0))
+
+    score = 0.0
+    if soil > 70:
+        score += 0.4
+    if vibration > 0.05:
+        score += 0.4
+    if humidity > 80:
+        score += 0.2
 
     if score >= 0.7:
         return "HIGH", score
-    elif score >= 0.4:
+    if score >= 0.4:
         return "MEDIUM", score
-    else:
-        return "LOW", score
+    return "LOW", score
 
-# -------------------------------
-# MQTT CALLBACK
-# -------------------------------
-def on_message(client, userdata, msg):
-    data = json.loads(msg.payload.decode())
-    node_id = data["node_id"]
 
+def store_node_reading(data: Dict[str, Any]) -> None:
+    """Normalize and store the latest reading per node."""
+    node_id = int(data["node_id"])
     risk, prob = predict_risk(data)
 
     node_data[node_id] = {
-        "lat": data["lat"],
-        "lon": data["lon"],
+        "lat": data.get("lat"),
+        "lon": data.get("lon"),
         "risk": risk,
         "probability": round(prob * 100, 1),
         "data": data,
-        "time": datetime.now().strftime("%H:%M:%S")
+        "time": datetime.now().strftime("%H:%M:%S"),
     }
 
-    print(f"Node {node_id} | {risk} | {prob*100:.1f}%")
 
-# -------------------------------
-# MQTT SETUP
-# -------------------------------
-mqtt_client = mqtt.Client()
-mqtt_client.on_message = on_message
-mqtt_client.connect("localhost", 1883)
-mqtt_client.subscribe("disaster/repeater/data")
-mqtt_client.loop_start()
+def on_message(client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
+    """Handle incoming MQTT payloads safely."""
+    try:
+        data = json.loads(msg.payload.decode())
+        required = {"node_id", "lat", "lon", "soil", "vibration", "humidity"}
+        missing = required.difference(data)
+        if missing:
+            print(f"Skipping message with missing keys: {sorted(missing)}")
+            return
+
+        store_node_reading(data)
+        node_id = int(data["node_id"])
+        probability = node_data[node_id]["probability"]
+        print(f"Node {node_id} | {node_data[node_id]['risk']} | {probability:.1f}%")
+    except (ValueError, TypeError, json.JSONDecodeError) as exc:
+        print(f"Invalid MQTT payload ({exc}); raw={msg.payload!r}")
+
+
+def setup_mqtt(host: str = "localhost", port: int = 1883) -> mqtt.Client:
+    client = mqtt.Client()
+    client.on_message = on_message
+    client.connect(host, port)
+    client.subscribe("disaster/repeater/data")
+    client.loop_start()
+    return client
+
+
+# Seed the dashboard with one local sample so the UI is populated on first load.
+store_node_reading(
+    {
+        "node_id": 99,
+        "lat": 10.2,
+        "lon": 76.5,
+        "soil": 90,
+        "vibration": 0.08,
+        "humidity": 88,
+    }
+)
+
 
-# -------------------------------
-# FLASK ROUTES
-# -------------------------------
 @app.route("/")
 def index():
     return render_template("index.html")
 
+
 @app.route("/api/data")
 def api_data():
     return jsonify(node_data)
 
-# -------------------------------
-# START SERVER
-# -------------------------------
+
 if __name__ == "__main__":
+    mqtt_client = setup_mqtt()
     app.run(debug=True)
