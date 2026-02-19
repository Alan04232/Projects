from flask import Flask, jsonify, request, render_template
from datetime import datetime
import numpy as np
import joblib
import threading
import time

app = Flask(__name__)

# ---------------- LOAD ML MODEL ----------------
model = joblib.load(r"D:\workspace\Projects\Mini project\model.pkl")

# ---------------- DATA STORAGE ----------------
raw_buffer = {}
hourly_db = {}

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

# ---------------- RECEIVE DATA ----------------
@app.route("/node-data", methods=["POST"])
def receive_node_data():
    data = request.json
    node_id = data["node_id"]

    raw_buffer.setdefault(node_id, []).append({
    "soil": data["soil_moisture"],
    "vib_x": data["vib_x"],
    "vib_y": data["vib_y"],
    "vib_z": data["vib_z"],
    "humidity": data.get("humidity",70),
    "lat": data["lat"],
    "lon": data["lon"],
    "time": datetime.now()
})


    return jsonify({"status": "received"})

# ---------------- HOURLY AGGREGATION ----------------
def hourly_processor():
    while True:
        time.sleep(3600)

        local_copy = raw_buffer.copy()
        raw_buffer.clear()

        for node_id, records in local_copy.items():
            if not records:
                continue

            soils = [r["soil"] for r in records]
            vx = [r["vib_x"] for r in records]
            vy = [r["vib_y"] for r in records]
            vz = [r["vib_z"] for r in records]
            hums = [r["humidity"] for r in records]

            soil_avg = np.mean(soils)
            vib_max = max(max(vx), max(vy), max(vz))
            hum_avg = np.mean(hums)

            lat, lon = records[-1]["lat"], records[-1]["lon"]
            rain = get_rainfall(lat, lon)
            props = node_props.get(node_id, node_props[1])

            features = [
                soil_avg,
                vib_max,
                hum_avg,
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
                "vib_x_max": round(max(vx), 3),
                "vib_y_max": round(max(vy), 3),
                "vib_z_max": round(max(vz), 3),
                "time": datetime.now().strftime("%Y-%m-%d %H:00")
            }

# ---------------- API ----------------
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
