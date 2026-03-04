"""
main.py  —  Landslide + Fire Detection Server
=============================================
• Receives sensor data from IoT gateway via POST /node-data
• Runs ML prediction every 15 minutes on latest sensor readings
• Saves every prediction + sensor snapshot to training_data.csv for future retraining
• Auto-retrains the model every 24 hours using accumulated real data
• Serves dashboard API at /api/data and /api/realtime
"""

import os
import csv
import time
import threading
import logging
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import joblib
from flask import Flask, jsonify, request, render_template
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, VotingClassifier
from sklearn.model_selection import cross_val_score

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
MODEL_PATH   = r"D:\workspace\Projects\Mini project\model.pkl"
TRAINING_CSV = r"D:\workspace\Projects\Mini project\training_data.csv"
PREDICT_INTERVAL  = 15 * 60          # 15 minutes in seconds
RETRAIN_INTERVAL  = 24 * 60 * 60     # 24 hours in seconds
MIN_ROWS_RETRAIN  = 20               # minimum rows before auto-retrain kicks in

FEATURE_COLS = [
    "soil_avg", "vib_max", "hum_avg", "rain",
    "soil_type", "soil_capacity", "slope"
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# STATIC NODE PROPERTIES
# ─────────────────────────────────────────────
NODE_PROPS = {
    1: {"soil_type": 2, "soil_capacity": 140, "slope": 25}
}

FLAME_SENSOR_DIRECTIONS = {
    "front": 0,   # North
    "right": 90,  # East
    "back":  180, # South
    "left":  270, # West
}

# ─────────────────────────────────────────────
# SHARED STATE  (protected by a lock)
# ─────────────────────────────────────────────
state_lock  = threading.Lock()
raw_buffer  = {}   # node_id -> list of sensor dicts (reset every 15 min)
result_db   = {}   # node_id -> latest prediction result

# ─────────────────────────────────────────────
# SEED TRAINING DATA  (used only when CSV is absent / empty)
# ─────────────────────────────────────────────
SEED_DATA = {
    "soil_avg":      [40,  60,  80,  90,  75,  50,  85,  95,  30,  55,  70,  88],
    "vib_max":       [0.02,0.03,0.07,0.08,0.06,0.02,0.09,0.10,0.01,0.03,0.05,0.08],
    "hum_avg":       [50,  60,  75,  85,  80,  55,  90,  95,  45,  65,  70,  88],
    "rain":          [30,  50, 100, 150, 120,  40, 160, 180,  20,  60,  90, 140],
    "soil_type":     [1,   1,   2,   2,   2,   1,   3,   3,   1,   1,   2,   3],
    "soil_capacity": [140,140, 120, 110, 120, 140, 100,  95, 150, 140, 120, 100],
    "slope":         [10,  15,  25,  30,  28,  12,  35,  40,   8,  18,  22,  32],
    "label":         [0,   0,   1,   1,   1,   0,   1,   1,   0,   0,   0,   1],
}

# ─────────────────────────────────────────────
# TRAINING DATA CSV HELPERS
# ─────────────────────────────────────────────
CSV_HEADER = FEATURE_COLS + [
    "label", "fire_detected", "spread_direction",
    "node_id", "lat", "lon", "timestamp"
]

def ensure_csv():
    """Create CSV with header if it doesn't exist or is empty."""
    if not Path(TRAINING_CSV).exists() or Path(TRAINING_CSV).stat().st_size == 0:
        df_seed = pd.DataFrame(SEED_DATA)
        # add placeholder columns
        for col in ["fire_detected", "spread_direction", "node_id", "lat", "lon"]:
            df_seed[col] = None
        df_seed["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        df_seed.to_csv(TRAINING_CSV, index=False)
        log.info("Created %s with %d seed rows", TRAINING_CSV, len(df_seed))

def append_to_csv(row: dict):
    """Append a single prediction row to the training CSV."""
    file_exists = Path(TRAINING_CSV).exists()
    with open(TRAINING_CSV, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADER, extrasaction="ignore")
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

def load_training_df() -> pd.DataFrame:
    ensure_csv()
    return pd.read_csv(TRAINING_CSV)

# ─────────────────────────────────────────────
# MODEL TRAINING
# ─────────────────────────────────────────────
def build_model():
    rf = RandomForestClassifier(n_estimators=200, max_depth=6, random_state=42)
    gb = GradientBoostingClassifier(n_estimators=150, learning_rate=0.05, random_state=42)
    return VotingClassifier(estimators=[("rf", rf), ("gb", gb)], voting="soft")

def train_model(df: pd.DataFrame):
    """Train on labelled rows only (label column not null/NaN)."""
    labelled = df.dropna(subset=["label"])
    if len(labelled) < MIN_ROWS_RETRAIN:
        log.warning("Only %d labelled rows — skipping retrain (need %d)",
                    len(labelled), MIN_ROWS_RETRAIN)
        return None

    X = labelled[FEATURE_COLS].astype(float)
    y = labelled["label"].astype(int)

    clf = build_model()
    if len(y.unique()) > 1:
        scores = cross_val_score(clf, X, y, cv=min(3, len(y)), scoring="roc_auc")
        log.info("Retrain CV AUC: %s  mean=%.3f", scores.round(3), scores.mean())
    clf.fit(X, y)
    return clf

def load_or_init_model():
    """Load existing model, or train a fresh one from seed data."""
    if Path(MODEL_PATH).exists():
        log.info("Loading existing model from %s", MODEL_PATH)
        return joblib.load(MODEL_PATH)
    log.info("No saved model found — training from seed data")
    df = load_training_df()
    clf = train_model(df)
    if clf:
        joblib.dump(clf, MODEL_PATH)
        log.info("Seed model saved to %s", MODEL_PATH)
    return clf
# Global model (replaced atomically on retrain)
model = load_or_init_model()
# PREDICTION HELPERS
def ml_predict(features: list) -> float:
    global model
    if model is None:
        return 0.0
    return float(model.predict_proba([features])[0][1])

def risk_level(p: float) -> str:
    if p > 0.75:   return "HIGH"
    if p > 0.4:    return "MEDIUM"
    return "LOW"

# ─────────────────────────────────────────────
# SIMULATED WEATHER (replace with real API)
# ─────────────────────────────────────────────
def get_rainfall(lat, lon) -> float:
    return float(np.random.randint(40, 200))

# ─────────────────────────────────────────────
# FIRE DIRECTION ANALYSIS
# ─────────────────────────────────────────────
def bearing_to_cardinal(deg: float) -> str:
    labels = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    return labels[round(deg / 45) % 8]

def analyse_fire_direction(flame: dict) -> dict:
    active = {k: v for k, v in flame.items() if v == 1}
    if not active:
        return {"fire_detected": False, "origin_directions": [],
                "spread_direction": None, "alert": "No fire detected"}

    bearings = [FLAME_SENSOR_DIRECTIONS[k] for k in active if k in FLAME_SENSOR_DIRECTIONS]
    sin_s = sum(np.sin(np.radians(b)) for b in bearings)
    cos_s = sum(np.cos(np.radians(b)) for b in bearings)
    mean_b  = np.degrees(np.arctan2(sin_s, cos_s)) % 360
    spread_b = (mean_b + 180) % 360

    origins = [bearing_to_cardinal(b) for b in bearings]
    spread  = bearing_to_cardinal(spread_b)
    return {
        "fire_detected": True,
        "origin_directions": origins,
        "spread_direction": spread,
        "spread_bearing_deg": round(spread_b, 1),
        "alert": f"Fire from {', '.join(origins)} — spreading toward {spread}."
    }

# ─────────────────────────────────────────────
# 15-MINUTE PREDICTION LOOP
# ─────────────────────────────────────────────
def prediction_loop():
    """Runs every 15 minutes: aggregates buffer, predicts, saves to CSV."""
    while True:
        time.sleep(PREDICT_INTERVAL)
        log.info("── 15-min prediction cycle started ──")

        with state_lock:
            local_copy = {nid: list(recs) for nid, recs in raw_buffer.items() if recs}
            raw_buffer.clear()

        for node_id, records in local_copy.items():
            try:
                soils = [r["soil"]  for r in records]
                vx    = [r["vib_x"] for r in records]
                vy    = [r["vib_y"] for r in records]
                vz    = [r["vib_z"] for r in records]
                hums  = [r["humidity"] for r in records]

                soil_avg = float(np.mean(soils))
                vib_max  = max(max(vx), max(vy), max(vz))
                hum_avg  = float(np.mean(hums))

                lat, lon = records[-1]["lat"], records[-1]["lon"]
                rain     = get_rainfall(lat, lon)
                props    = NODE_PROPS.get(node_id, NODE_PROPS[1])

                features = [
                    soil_avg, vib_max, hum_avg, rain,
                    props["soil_type"], props["soil_capacity"], props["slope"]
                ]

                prob = ml_predict(features)
                risk = risk_level(prob)

                # Aggregate flame readings
                merged_flame = {"front": 0, "right": 0, "back": 0, "left": 0}
                for r in records:
                    for direction, val in r.get("flame", {}).items():
                        if val:
                            merged_flame[direction] = 1
                fire_info = analyse_fire_direction(merged_flame)

                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # ── Store result for dashboard ──
                with state_lock:
                    result_db[node_id] = {
                        "lat": lat, "lon": lon,
                        "risk": risk,
                        "probability": round(prob * 100, 2),
                        "soil_avg": round(soil_avg, 2),
                        "vib_x_max": round(max(vx), 3),
                        "vib_y_max": round(max(vy), 3),
                        "vib_z_max": round(max(vz), 3),
                        "fire": fire_info,
                        "time": now_str,
                    }

                # ── Save to CSV for future training ──
                # label is None (unknown) — a human/expert can fill it in later
                # Once labelled rows accumulate, the auto-retrain loop will use them
                csv_row = {
                    "soil_avg":       round(soil_avg, 3),
                    "vib_max":        round(vib_max, 4),
                    "hum_avg":        round(hum_avg, 3),
                    "rain":           round(rain, 2),
                    "soil_type":      props["soil_type"],
                    "soil_capacity":  props["soil_capacity"],
                    "slope":          props["slope"],
                    "label":          "",          # fill in after a real event
                    "fire_detected":  int(fire_info["fire_detected"]),
                    "spread_direction": fire_info.get("spread_direction", ""),
                    "node_id":        node_id,
                    "lat":            round(lat, 6),
                    "lon":            round(lon, 6),
                    "timestamp":      now_str,
                }
                append_to_csv(csv_row)
                log.info("Node %s | risk=%s (%.1f%%) | fire=%s | saved to CSV",
                         node_id, risk, prob * 100, fire_info["fire_detected"])

            except Exception as exc:
                log.error("Prediction failed for node %s: %s", node_id, exc)

# ─────────────────────────────────────────────
# 24-HOUR AUTO-RETRAIN LOOP
# ─────────────────────────────────────────────
def retrain_loop():
    """Every 24 h, reload the CSV and retrain if enough labelled data exists."""
    global model
    while True:
        time.sleep(RETRAIN_INTERVAL)
        log.info("── Daily retrain cycle started ──")
        try:
            df  = load_training_df()
            clf = train_model(df)
            if clf:
                joblib.dump(clf, MODEL_PATH)
                model = clf   # atomic replace
                log.info("Model retrained on %d labelled rows and saved.", len(df.dropna(subset=["label"])))
            else:
                log.info("Retrain skipped — not enough labelled data yet.")
        except Exception as exc:
            log.error("Retrain failed: %s", exc)

# ─────────────────────────────────────────────
# FLASK APP
# ─────────────────────────────────────────────
app = Flask(__name__)

@app.route("/node-data", methods=["POST"])
def receive_node_data():
    try:
        data = request.get_json(force=True)   # <-- FORCE JSON PARSE
        if data is None:
            return jsonify({"error": "No JSON received"}), 400

        log.info("RECEIVED FROM GATEWAY: %s", data)

        node_id = data["node_id"]
        flame   = data.get("flame", {"front": 0, "right": 0, "back": 0, "left": 0})

        record = {
            "soil":     data["soil_moisture"],
            "vib_x":    data["vib_x"],
            "vib_y":    data["vib_y"],
            "vib_z":    data["vib_z"],
            "humidity": data.get("humidity", 70),
            "lat":      data["lat"],
            "lon":      data["lon"],
            "flame":    flame,
            "time":     datetime.now(),
        }

        with state_lock:
            raw_buffer.setdefault(node_id, []).append(record)

        return jsonify({"status": "received"}), 200

    except Exception as e:
        log.error("POST /node-data error: %s", e)
        return jsonify({"error": str(e)}), 400

@app.route("/api/data")
def api_data():
    """Latest 15-min aggregated prediction per node."""
    with state_lock:
        return jsonify(dict(result_db))

@app.route("/api/realtime")
def api_realtime():
    """Current raw buffer snapshot with live fire direction."""
    out = {}
    with state_lock:
        for node_id, records in raw_buffer.items():
            if not records:
                continue
            latest = records[-1]
            out[node_id] = {
                "soil":     latest["soil"],
                "vib_x":    latest["vib_x"],
                "vib_y":    latest["vib_y"],
                "vib_z":    latest["vib_z"],
                "humidity": latest["humidity"],
                "fire":     analyse_fire_direction(latest.get("flame", {})),
                "time":     latest["time"].strftime("%Y-%m-%d %H:%M:%S"),
            }
    return jsonify(out)

@app.route("/api/training-data")
def api_training_data():
    """Return the last 100 rows of the training CSV as JSON."""
    try:
        df = pd.read_csv(TRAINING_CSV).tail(100)
        return jsonify(df.to_dict(orient="records"))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

@app.route("/api/label", methods=["POST"])
def api_label():
    """
    Allow an operator to assign a ground-truth label to a saved row.
    POST body: { "timestamp": "2024-01-01 12:00:00", "node_id": 1, "label": 1 }
    This labelled data will be used in the next 24h retrain.
    """
    body      = request.json
    ts        = body.get("timestamp")
    node_id   = body.get("node_id")
    label_val = body.get("label")

    if ts is None or label_val is None:
        return jsonify({"error": "timestamp and label are required"}), 400

    try:
        df = pd.read_csv(TRAINING_CSV)
        mask = (df["timestamp"] == ts)
        if node_id is not None:
            mask &= (df["node_id"] == node_id)
        if mask.sum() == 0:
            return jsonify({"error": "No matching row found"}), 404
        df.loc[mask, "label"] = int(label_val)
        df.to_csv(TRAINING_CSV, index=False)
        log.info("Label %s applied to %d row(s) at %s", label_val, mask.sum(), ts)
        return jsonify({"updated": int(mask.sum())})
    except Exception as exc:
        log.error("Labelling failed: %s", exc)
        return jsonify({"error": str(exc)}), 500

@app.route("/")
def index():
    return render_template("index1.html")

# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    ensure_csv()

    threading.Thread(target=prediction_loop, daemon=True, name="PredictionLoop").start()
    threading.Thread(target=retrain_loop,    daemon=True, name="RetrainLoop").start()

    log.info("Server starting — predictions every 15 min, retrain every 24 h")
    app.run(host="0.0.0.0", port=5000, debug=False)