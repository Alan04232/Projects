from flask import Flask, jsonify, request, render_template
from datetime import datetime
import numpy as np
import joblib

# -------------------------------
# FLASK APP
# -------------------------------
app = Flask(__name__)

# -------------------------------
# LOAD TRAINED ML MODEL
# -------------------------------
model = joblib.load("model.pkl")   # RandomForest / LogisticRegression

# -------------------------------
# DATA STORE
# -------------------------------
node_data = {}

# -------------------------------
# STATIC GEO + SOIL DATA (PROTOTYPE)
# -------------------------------
node_properties = {
    1: {
        "soil_type": 2,        # Laterite
        "soil_capacity": 140,  # mm
        "slope": 25            # degrees
    }
}

# -------------------------------
# WEATHER DATA (SIMULATED)
# -------------------------------
def get_rainfall(lat, lon):
    # Replace with real API later
    return np.random.randint(20, 200)  # mm (3-day cumulative)

# -------------------------------
# ML PREDICTION
# -------------------------------
def ml_predict(features):
    """
    features order:
    [soil_moisture, vibration, humidity, rain_3day,
     soil_type, soil_capacity, slope]
    """
    X = np.array([features])
    probability = model.predict_proba(X)[0][1]
    return probability

def risk_level(prob):
    if prob > 0.75:
        return "HIGH"
    elif prob > 0.4:
        return "MEDIUM"
    else:
        return "LOW"

# -------------------------------
# RECEIVE DATA FROM INTERMEDIATE NODE
# -------------------------------
@app.route("/node-data", methods=["POST"])
def receive_node_data():
    data = request.json
    node_id = data["node_id"]

    lat = data["lat"]
    lon = data["lon"]
    soil = data["soil_moisture"]
    vibration = data["vibration"]
    humidity = data.get("humidity", 70)

    # Static + contextual data
    soil_type = node_properties[node_id]["soil_type"]
    soil_capacity = node_properties[node_id]["soil_capacity"]
    slope = node_properties[node_id]["slope"]
    rain_3day = get_rainfall(lat, lon)

    # ---- ML FEATURE VECTOR ----
    features = [
        soil,
        vibration,
        humidity,
        rain_3day,
        soil_type,
        soil_capacity,
        slope
    ]

    # ---- ML PREDICTION ----
    prob = ml_predict(features)
    risk = risk_level(prob)

    # ---- STORE RESULT ----
    node_data[node_id] = {
        "lat": lat,
        "lon": lon,
        "risk": risk,
        "probability": round(prob * 100, 2),
        "time": datetime.now().strftime("%H:%M:%S")
    }

    print(f"Node {node_id} | Risk: {risk} | Prob: {prob:.2f}")

    return jsonify({"status": "ok"})

# -------------------------------
# API FOR WEB DASHBOARD
# -------------------------------
@app.route("/api/data")
def api_data():
    return jsonify(node_data)

# -------------------------------
# WEB PAGE
# -------------------------------
@app.route("/")
def index():
    return render_template("index.html")

# -------------------------------
# START SERVER
# -------------------------------
if __name__ == "__main__":
    app.run(debug=True)