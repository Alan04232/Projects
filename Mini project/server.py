from flask import Flask, jsonify, request, render_template
from datetime import datetime
import numpy as np
import joblib
import threading
import time

app = Flask(__name__)

# ---------------- LOAD ML MODEL ----------------
model = joblib.load("D:\workspace\Projects\Mini project\model.pkl")

# ---------------- DATA STORAGE ----------------
raw_buffer = {}        # temporary 5-min data
hourly_db = {}         # final hourly database

# ---------------- STATIC NODE INFO ----------------
node_props = {
    1: {"soil_type": 2, "soil_capacity": 140, "slope": 25}
}

# ---------------- SIMULATED WEATHER ----------------
def get_rainfall(lat, lon):
    return np.random.randint(40, 200)

# ---------------- ML ----------------
def ml_predict(features):
    return model.predict_proba([features])[0][1]

def risk_level(p):
    if p > 0.75:
        return "HIGH"
    elif p > 0.4:
        return "MEDIUM"
    else:
        return "LOW"

# ---------------- RECEIVE 5-MIN DATA ----------------
@app.route("/node-data", methods=["POST"])
def receive_node_data():
    data = request.json
    node_id = data["node_id"]

    if node_id not in raw_buffer:
        raw_buffer[node_id] = []

    raw_buffer[node_id].append({
        "soil": data["soil_moisture"],
        "vibration": data["vibration"],
        "lat": data["lat"],
        "lon": data["lon"],
        "time": datetime.now()
    })

    return jsonify({"status": "received"})

# ---------------- HOURLY AGGREGATION THREAD ----------------
def hourly_processor():
    while True:
        time.sleep(3600)  # 1 hour

        for node_id, records in raw_buffer.items():
            if len(records) == 0:
                continue

            soils = [r["soil"] for r in records]
            vibs = [r["vibration"] for r in records]

            soil_avg = np.mean(soils)
            vib_max = np.max(vibs)
            vib_std = np.std(vibs)

            lat = records[-1]["lat"]
            lon = records[-1]["lon"]

            rain = get_rainfall(lat, lon)
            props = node_props[node_id]

            features = [
                soil_avg,
                vib_max,
                70,              # humidity
                rain,
                props["soil_type"],
                props["soil_capacity"],
                props["slope"]
            ]

            prob = ml_predict(features)
            risk = risk_level(prob)

            hourly_db[node_id] = {
                "lat": lat,
                "lon": lon,
                "risk": risk,
                "probability": round(prob * 100, 2),
                "soil_avg": round(soil_avg, 2),
                "vib_max": round(vib_max, 3),
                "vib_std": round(vib_std, 4),
                "time": datetime.now().strftime("%Y-%m-%d %H:00")
            }

        # Clear raw buffer after processing
        raw_buffer.clear()

# ---------------- API FOR WEB ----------------
@app.route("/api/data")
def api_data():
    return jsonify(hourly_db)

@app.route("/")
def index():
    return render_template("index.html")

# ---------------- START SERVER ----------------
if __name__ == "__main__":
    threading.Thread(target=hourly_processor, daemon=True).start()
    app.run(debug=True)
