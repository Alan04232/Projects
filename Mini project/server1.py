from flask import Flask, jsonify, render_template
import paho.mqtt.client as mqtt
import json
from datetime import datetime

app = Flask(__name__)

#test data
test_data = {
    "node_id": 99,
    "lat": 10.2,
    "lon": 76.5,
    "soil": 90,
    "vibration": 0.08,
    "humidity": 88
}
risk, prob = predict_risk(test_data)
node_data[99] = {
    "lat": test_data["lat"],
    "lon": test_data["lon"],
    "risk": risk,
    "probability": round(prob * 100, 1),
    "data": test_data,
    "time": datetime.now().strftime("%H:%M:%S")
}
# -------------------------------
# NODE DATA STORE
# -------------------------------
node_data = {}

# -------------------------------
# SIMPLE ML RISK PREDICTION
# -------------------------------
def predict_risk(data):
    soil = data.get("soil", 0)
    vibration = data.get("vibration", 0)
    humidity = data.get("humidity", 0)

    score = 0
    if soil > 70: score += 0.4
    if vibration > 0.05: score += 0.4
    if humidity > 80: score += 0.2

    if score >= 0.7:
        return "HIGH", score
    elif score >= 0.4:
        return "MEDIUM", score
    else:
        return "LOW", score

# -------------------------------
# MQTT CALLBACK
# -------------------------------
def on_message(client, userdata, msg):
    data = json.loads(msg.payload.decode())
    node_id = data["node_id"]

    risk, prob = predict_risk(data)

    node_data[node_id] = {
        "lat": data["lat"],
        "lon": data["lon"],
        "risk": risk,
        "probability": round(prob * 100, 1),
        "data": data,
        "time": datetime.now().strftime("%H:%M:%S")
    }

    print(f"Node {node_id} | {risk} | {prob*100:.1f}%")

# -------------------------------
# MQTT SETUP
# -------------------------------
mqtt_client = mqtt.Client()
mqtt_client.on_message = on_message
mqtt_client.connect("localhost", 1883)
mqtt_client.subscribe("disaster/repeater/data")
mqtt_client.loop_start()

# -------------------------------
# FLASK ROUTES
# -------------------------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/data")
def api_data():
    return jsonify(node_data)

# -------------------------------
# START SERVER
# -------------------------------
if __name__ == "__main__":
    app.run(debug=True)
