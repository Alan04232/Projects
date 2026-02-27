from flask import Flask, request, jsonify
from datetime import datetime
import numpy as np
import threading
import time
import csv
import os
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import joblib

app = Flask(__name__)

# ---------------- FILES ----------------
CSV_FILE = "training_data_30min.csv"
MODEL_FILE = "model.pkl"

# ---------------- DATA STORAGE ----------------
minute_buffer = {}
latest_data = {}
model = None

# ---------------- INITIALIZE CSV ----------------
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "timestamp",
            "node_id",
            "lat",
            "lon",
            "soil_avg",
            "vib_avg",
            "vib_max",
            "flame_avg",
            "flame_max",
            "label"   # manual or auto hazard label
        ])

# ---------------- LOAD MODEL IF EXISTS ----------------
if os.path.exists(MODEL_FILE):
    model = joblib.load(MODEL_FILE)

# ---------------- RECEIVE DATA (5 sec) ----------------
@app.route("/node-data", methods=["POST"])
def receive_data():
    data = request.json
    node_id = data["node_id"]

    minute_buffer.setdefault(node_id, []).append({
        "soil": data["soil_moisture"],
        "vib": max(abs(data["vib_x"]),
                   abs(data["vib_y"]),
                   abs(data["vib_z"])),
        "flame": data["flame_adc"],
        "lat": data["lat"],
        "lon": data["lon"]
    })

    # Real-time prediction (if model exists)
    if model:
        features = [[
            data["soil_moisture"],
            max(abs(data["vib_x"]),
                abs(data["vib_y"]),
                abs(data["vib_z"])),
            data["flame_adc"]
        ]]
        prob = model.predict_proba(features)[0][1]
        risk = "HIGH" if prob > 0.7 else "MEDIUM" if prob > 0.4 else "LOW"
    else:
        risk = "UNKNOWN"
        prob = 0

    latest_data[node_id] = {
        "lat": data["lat"],
        "lon": data["lon"],
        "risk": risk,
        "probability": round(prob * 100, 2),
        "time": datetime.now().strftime("%H:%M:%S")
    }

    return jsonify({"status": "ok"})

# ---------------- 30-MIN AGGREGATION ----------------
def half_hour_aggregation():
    while True:
        time.sleep(1800)

        local_copy = minute_buffer.copy()
        minute_buffer.clear()

        for node_id, records in local_copy.items():
            if not records:
                continue

            soils = [r["soil"] for r in records]
            vibs = [r["vib"] for r in records]
            flames = [r["flame"] for r in records]

            soil_avg = np.mean(soils)
            vib_avg = np.mean(vibs)
            vib_max = np.max(vibs)
            flame_avg = np.mean(flames)
            flame_max = np.max(flames)

            lat = records[-1]["lat"]
            lon = records[-1]["lon"]

            # Simple automatic labeling logic
            label = 1 if flame_max > 2500 or vib_max > 3 else 0

            with open(CSV_FILE, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().strftime("%Y-%m-%d %H:%M"),
                    node_id,
                    lat,
                    lon,
                    round(soil_avg, 2),
                    round(vib_avg, 3),
                    round(vib_max, 3),
                    round(flame_avg, 2),
                    round(flame_max, 2),
                    label
                ])

        print("30-min data saved.")

# ---------------- AUTO ML RETRAINING ----------------
def retrain_model():
    global model

    while True:
        time.sleep(7200)  # Retrain every 2 hours

        if not os.path.exists(CSV_FILE):
            continue

        df = pd.read_csv(CSV_FILE)

        if len(df) < 20:   # Minimum data threshold
            continue

        X = df[[
            "soil_avg",
            "vib_avg",
            "vib_max",
            "flame_avg",
            "flame_max"
        ]]
        y = df["label"]

        new_model = RandomForestClassifier(n_estimators=100)
        new_model.fit(X, y)

        joblib.dump(new_model, MODEL_FILE)
        model = new_model

        print("Model retrained automatically.")

# ---------------- API ----------------
@app.route("/api/data")
def api_data():
    return jsonify(latest_data)

# ---------------- START SERVER ----------------
if __name__ == "__main__":
    threading.Thread(target=half_hour_aggregation, daemon=True).start()
    threading.Thread(target=retrain_model, daemon=True).start()
    app.run(debug=True)

