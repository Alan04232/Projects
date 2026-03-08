"""
main_improved.py — Enhanced Landslide + Fire Detection Server
===============================================================
Features:
• Receives sensor data from IoT gateway via POST /node-data
• Fetches real-time soil data from SoilGrids API
• Fetches real-time weather data from WeatherAPI/OpenWeatherMap
• Runs ML prediction every 15 minutes using enhanced features
• Auto-retrains model every 24 hours with accumulated data
• Saves predictions + sensor snapshots to training_data.csv
• Provides REST APIs for dashboard consumption
• Improved error handling, validation, and logging
"""
import os
import csv
import json
import time
import threading
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
import numpy as np
import pandas as pd
import requests
import joblib
from flask import Flask, jsonify, request, render_template
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, VotingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score
# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────
MODEL_PATH = r"D:\workspace\Projects\Mini project\model.pkl"
SCALER_PATH = r"D:\workspace\Projects\Mini project\scaler.pkl"
TRAINING_CSV = r"D:\workspace\Projects\Mini project\training_data.csv"
PREDICT_INTERVAL = 15 * 60  # 15 minutes
RETRAIN_INTERVAL = 24 * 60 * 60  # 24 hours
MIN_ROWS_RETRAIN = 20
SOIL_FETCH_INTERVAL = 60 * 60  # Fetch soil data every hour
# API Keys (set via environment variables for security)
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "your_api_key_here")
WEATHER_API_URL = "https://api.weatherapi.com/v1/current.json"  # Free tier available

# Feature columns with improved engineering
FEATURE_COLS = [
    "soil_moisture", "vib_max", "vib_rms", "humidity", "rainfall",
    "temperature", "wind_speed", "soil_type", "soil_capacity",
    "slope", "land_use", "ndvi"
]

STATIC_FEATURES = ["soil_type", "soil_capacity", "slope", "land_use", "ndvi"]
DYNAMIC_FEATURES = ["soil_moisture", "vib_max", "vib_rms", "humidity", 
                    "rainfall", "temperature", "wind_speed"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────
@dataclass
class SensorReading:
    """Single sensor reading from IoT node"""
    node_id: int
    soil_moisture: float  # 0-100%
    vib_x: float
    vib_y: float
    vib_z: float
    humidity: float  # 0-100%
    lat: float
    lon: float
    flame: Dict[str, int]  # front, right, back, left
    timestamp: datetime

    def to_dict(self):
        d = asdict(self)
        d['timestamp'] = self.timestamp.isoformat()
        return d


@dataclass
class NodeProperties:
    """Static properties of a sensor node"""
    soil_type: int  # 1=clay, 2=loam, 3=sandy
    soil_capacity: float  # mm/m
    slope: float  # degrees
    land_use: int  # 1=forest, 2=agriculture, 3=urban
    ndvi: float  # Normalized Vegetation Index


@dataclass
class WeatherData:
    """Real-time weather at node location"""
    temperature: float  # Celsius
    humidity: float  # 0-100%
    rainfall: float  # mm
    wind_speed: float  # km/h
    wind_direction: int  # degrees
    pressure: float  # mb
    visibility: float  # km
    timestamp: datetime


@dataclass
class PredictionResult:
    """ML model prediction output"""
    node_id: int
    probability: float  # 0-1
    risk_level: str  # LOW, MEDIUM, HIGH
    fire_detected: bool
    fire_origin: List[str]
    fire_spread: Optional[str]
    features: Dict[str, float]
    timestamp: datetime


# ─────────────────────────────────────────────
# NODE PROPERTIES & CONFIGURATION
# ─────────────────────────────────────────────
NODE_PROPS = {
    1: NodeProperties(
        soil_type=2,  # Loam
        soil_capacity=140,
        slope=25,
        land_use=1,  # Forest
        ndvi=0.65
    ),
    2: NodeProperties(
        soil_type=1,  # Clay
        soil_capacity=120,
        slope=15,
        land_use=2,  # Agriculture
        ndvi=0.45
    )
}

FLAME_SENSOR_DIRECTIONS = {
    "front": 0, "right": 90, "back": 180, "left": 270
}

# ─────────────────────────────────────────────
# SEED TRAINING DATA (Enhanced)
# ─────────────────────────────────────────────
SEED_DATA = {
    "soil_moisture": [40, 60, 80, 90, 75, 50, 85, 95, 30, 55, 70, 88],
    "vib_max": [0.02, 0.03, 0.07, 0.08, 0.06, 0.02, 0.09, 0.10, 0.01, 0.03, 0.05, 0.08],
    "vib_rms": [0.01, 0.015, 0.035, 0.04, 0.03, 0.01, 0.045, 0.05, 0.005, 0.015, 0.025, 0.04],
    "humidity": [50, 60, 75, 85, 80, 55, 90, 95, 45, 65, 70, 88],
    "rainfall": [30, 50, 100, 150, 120, 40, 160, 180, 20, 60, 90, 140],
    "temperature": [15, 18, 25, 28, 26, 16, 30, 32, 12, 20, 23, 29],
    "wind_speed": [5, 8, 15, 20, 18, 6, 25, 28, 3, 10, 12, 22],
    "soil_type": [1, 1, 2, 2, 2, 1, 3, 3, 1, 1, 2, 3],
    "soil_capacity": [140, 140, 120, 110, 120, 140, 100, 95, 150, 140, 120, 100],
    "slope": [10, 15, 25, 30, 28, 12, 35, 40, 8, 18, 22, 32],
    "land_use": [1, 1, 1, 1, 1, 1, 2, 2, 1, 1, 1, 2],
    "ndvi": [0.6, 0.65, 0.5, 0.45, 0.48, 0.62, 0.3, 0.25, 0.7, 0.63, 0.55, 0.35],
    "label": [0, 0, 1, 1, 1, 0, 1, 1, 0, 0, 0, 1],
}

# ─────────────────────────────────────────────
# SHARED STATE (Protected by locks)
# ─────────────────────────────────────────────
state_lock = threading.Lock()
raw_buffer: Dict[int, List[SensorReading]] = {}  # node_id -> [readings]
soil_cache: Dict[int, Dict] = {}  # node_id -> soil data
weather_cache: Dict[int, WeatherData] = {}  # node_id -> weather data
result_db: Dict[int, PredictionResult] = {}  # node_id -> latest prediction

# ─────────────────────────────────────────────
# CSV HELPERS (Enhanced)
# ─────────────────────────────────────────────
CSV_HEADER = FEATURE_COLS + [
    "label", "fire_detected", "fire_origin", "fire_spread",
    "node_id", "lat", "lon", "timestamp"
]


def ensure_csv():
    """Create CSV with header if empty or missing."""
    csv_path = Path(TRAINING_CSV)
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        df_seed = pd.DataFrame(SEED_DATA)
        for col in ["fire_detected", "fire_origin", "fire_spread", 
                    "node_id", "lat", "lon"]:
            df_seed[col] = None
        df_seed["timestamp"] = datetime.now().isoformat()
        df_seed.to_csv(TRAINING_CSV, index=False)
        log.info(f"Created training CSV with {len(df_seed)} seed rows")


def append_to_csv(row: dict):
    """Append row to training CSV with validation."""
    try:
        csv_path = Path(TRAINING_CSV)
        file_exists = csv_path.exists() and csv_path.stat().st_size > 0
        
        with open(TRAINING_CSV, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADER, 
                                   extrasaction="ignore")
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
    except Exception as e:
        log.error(f"Failed to append to CSV: {e}")


def load_training_df() -> pd.DataFrame:
    """Load training CSV with error handling."""
    ensure_csv()
    try:
        return pd.read_csv(TRAINING_CSV)
    except Exception as e:
        log.error(f"Failed to load training CSV: {e}")
        return pd.DataFrame(SEED_DATA)


# ─────────────────────────────────────────────
# SOIL DATA API INTEGRATION
# ─────────────────────────────────────────────
def fetch_soil_data(latitude: float, longitude: float) -> Dict:
    """
    Fetch soil data from SoilGrids API
    Returns: soil texture, bulk density, organic carbon
    """
    base_url = "https://rest.isric.org/soilgrids/v2.0/properties/query"
    properties = ['sand', 'silt', 'clay', 'bdod', 'soc']
    depths = ['0-5cm', '5-15cm', '15-30cm']
    
    params = {
        'lon': longitude,
        'lat': latitude,
        'property': properties,
        'depth': depths,
        'value': 'mean'
    }
    
    try:
        log.info(f"Fetching soil data for ({latitude}, {longitude})")
        response = requests.get(base_url, params=params, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        
        if 'properties' not in data:
            log.warning("No soil properties in response")
            return _get_default_soil_data()
        
        results = {}
        for prop in data['properties']:
            prop_name = prop.get('name', 'unknown')
            results[prop_name] = {}
            
            for depth_layer in prop.get('layers', []):
                depth_range = depth_layer.get('name', 'unknown')
                depths_data = depth_layer.get('depths', [])
                
                if depths_data and len(depths_data) > 0:
                    values = depths_data[0].get('values', {})
                    value = values.get('mean', values.get('median', None))
                    
                    if value is not None:
                        # Unit conversions
                        if prop_name == 'bdod':  # Bulk density
                            value = value  # kg/dm³ = g/cm³
                        elif prop_name == 'soc':  # Organic carbon
                            value = value / 10  # dg/kg to g/kg
                        
                        results[prop_name][depth_range] = value
        
        log.info(f"✓ Successfully fetched soil data")
        return results
        
    except requests.exceptions.Timeout:
        log.warning("Soil API timeout")
        return _get_default_soil_data()
    except Exception as e:
        log.error(f"Soil API error: {e}")
        return _get_default_soil_data()


def _get_default_soil_data() -> Dict:
    """Default soil data (typical loam)"""
    return {
        'sand': {'0-5cm': 40.0, '5-15cm': 38.0, '15-30cm': 35.0},
        'silt': {'0-5cm': 35.0, '5-15cm': 36.0, '15-30cm': 37.0},
        'clay': {'0-5cm': 25.0, '5-15cm': 26.0, '15-30cm': 28.0},
        'bdod': {'0-5cm': 1.3, '5-15cm': 1.35, '15-30cm': 1.4},
        'soc': {'0-5cm': 15.0, '5-15cm': 10.0, '15-30cm': 5.0}
    }


# ─────────────────────────────────────────────
# WEATHER DATA API INTEGRATION
# ─────────────────────────────────────────────
def fetch_weather_data(latitude: float, longitude: float) -> WeatherData:
    """
    Fetch real-time weather data from WeatherAPI
    Free tier: 1M calls/month, instant data
    """
    params = {
        'key': WEATHER_API_KEY,
        'q': f"{latitude},{longitude}",
        'aqi': 'yes'
    }
    
    try:
        log.info(f"Fetching weather data for ({latitude}, {longitude})")
        response = requests.get(WEATHER_API_URL, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        current = data['current']
        
        weather = WeatherData(
            temperature=current['temp_c'],
            humidity=current['humidity'],
            rainfall=current.get('precip_mm', 0),
            wind_speed=current['wind_kph'],
            wind_direction=current['wind_degree'],
            pressure=current['pressure_mb'],
            visibility=current['vis_km'],
            timestamp=datetime.now()
        )
        
        log.info(f"✓ Weather: {weather.temperature}°C, {weather.humidity}% RH, "
                f"{weather.rainfall}mm rain, {weather.wind_speed} km/h wind")
        return weather
        
    except Exception as e:
        log.warning(f"Weather API error: {e} - using default values")
        return _get_default_weather_data()


def _get_default_weather_data() -> WeatherData:
    """Default weather data"""
    return WeatherData(
        temperature=20.0,
        humidity=60.0,
        rainfall=0.0,
        wind_speed=5.0,
        wind_direction=0,
        pressure=1013.0,
        visibility=10.0,
        timestamp=datetime.now()
    )


# ─────────────────────────────────────────────
# MODEL TRAINING (Enhanced)
# ─────────────────────────────────────────────
def build_model():
    """Build ensemble ML model with improved hyperparameters"""
    rf = RandomForestClassifier(
        n_estimators=300,
        max_depth=8,
        min_samples_split=5,
        min_samples_leaf=2,
        max_features='sqrt',
        class_weight='balanced',
        random_state=42,
        n_jobs=-1
    )
    
    gb = GradientBoostingClassifier(
        n_estimators=200,
        learning_rate=0.05,
        max_depth=5,
        min_samples_split=5,
        min_samples_leaf=2,
        subsample=0.8,
        max_features='sqrt',
        random_state=42
    )
    
    return VotingClassifier(
        estimators=[("rf", rf), ("gb", gb)],
        voting="soft",
        weights=[0.5, 0.5]
    )


def train_model(df: pd.DataFrame) -> Tuple[Optional, Optional]:
    """
    Train model on labelled data with feature scaling
    Returns: (model, scaler) tuple
    """
    labelled = df.dropna(subset=["label"])
    
    if len(labelled) < MIN_ROWS_RETRAIN:
        log.warning(f"Only {len(labelled)} labelled rows (need {MIN_ROWS_RETRAIN})")
        return None, None
    
    try:
        X = labelled[FEATURE_COLS].astype(float)
        y = labelled["label"].astype(int)
        
        # Scale features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        clf = build_model()
        
        if len(y.unique()) > 1:
            cv_folds = min(5, len(y) // 10)
            scores = cross_val_score(clf, X_scaled, y, 
                                    cv=cv_folds, scoring='roc_auc')
            log.info(f"CV AUC scores: {scores.round(3)} (mean={scores.mean():.3f})")
        
        clf.fit(X_scaled, y)
        log.info(f"✓ Model trained on {len(labelled)} labelled rows")
        
        return clf, scaler
        
    except Exception as e:
        log.error(f"Training error: {e}")
        return None, None


def load_or_init_model() -> Tuple[Optional, Optional]:
    """Load existing model/scaler or train from seed data"""
    model_path = Path(MODEL_PATH)
    scaler_path = Path(SCALER_PATH)
    
    if model_path.exists() and scaler_path.exists():
        try:
            log.info("Loading existing model and scaler")
            model = joblib.load(MODEL_PATH)
            scaler = joblib.load(SCALER_PATH)
            return model, scaler
        except Exception as e:
            log.error(f"Failed to load model: {e}")
    
    log.info("Training initial model from seed data")
    df = pd.DataFrame(SEED_DATA)
    model, scaler = train_model(df)
    
    if model and scaler:
        try:
            joblib.dump(model, MODEL_PATH)
            joblib.dump(scaler, SCALER_PATH)
            log.info("Seed model saved")
        except Exception as e:
            log.error(f"Failed to save model: {e}")
    
    return model, scaler


# Global model and scaler
model, scaler = load_or_init_model()

# ─────────────────────────────────────────────
# PREDICTION HELPERS
# ─────────────────────────────────────────────
def ml_predict(features: List[float]) -> float:
    """Predict landslide probability (0-1)"""
    global model, scaler
    
    if model is None or scaler is None:
        log.warning("Model not available")
        return 0.5
    
    try:
        features_scaled = scaler.transform([features])
        prob = float(model.predict_proba(features_scaled)[0][1])
        return max(0.0, min(1.0, prob))  # Clamp to [0,1]
    except Exception as e:
        log.error(f"Prediction error: {e}")
        return 0.5


def risk_level(prob: float) -> str:
    """Convert probability to risk level"""
    if prob > 0.75:
        return "HIGH"
    elif prob > 0.4:
        return "MEDIUM"
    else:
        return "LOW"


# ─────────────────────────────────────────────
# FIRE DETECTION ANALYSIS
# ─────────────────────────────────────────────
def bearing_to_cardinal(deg: float) -> str:
    """Convert bearing (degrees) to cardinal direction"""
    labels = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
              "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return labels[round(deg / 22.5) % 16]


def analyse_fire_direction(flame: Dict[str, int]) -> Dict:
    """Analyze fire sensor readings to determine origin and spread"""
    active = {k: v for k, v in flame.items() if v == 1}
    
    if not active:
        return {
            "fire_detected": False,
            "origin_directions": [],
            "spread_direction": None,
            "spread_bearing_deg": None,
            "confidence": 0.0
        }
    
    bearings = [FLAME_SENSOR_DIRECTIONS[k] for k in active 
                if k in FLAME_SENSOR_DIRECTIONS]
    
    if not bearings:
        return {
            "fire_detected": False,
            "origin_directions": [],
            "spread_direction": None,
            "spread_bearing_deg": None,
            "confidence": 0.0
        }
    
    # Calculate mean bearing (vector sum)
    sin_s = sum(np.sin(np.radians(b)) for b in bearings)
    cos_s = sum(np.cos(np.radians(b)) for b in bearings)
    mean_b = np.degrees(np.arctan2(sin_s, cos_s)) % 360
    spread_b = (mean_b + 180) % 360
    
    # Confidence based on number of sensors
    confidence = len(bearings) / 4.0
    
    origins = [bearing_to_cardinal(b) for b in bearings]
    spread = bearing_to_cardinal(spread_b)
    
    return {
        "fire_detected": True,
        "origin_directions": origins,
        "spread_direction": spread,
        "spread_bearing_deg": round(spread_b, 1),
        "confidence": round(confidence, 2)
    }


# ─────────────────────────────────────────────
# PREDICTION LOOP (15-minute aggregation)
# ─────────────────────────────────────────────
def prediction_loop():
    """Run predictions every 15 minutes"""
    while True:
        time.sleep(PREDICT_INTERVAL)
        log.info("=" * 60)
        log.info("PREDICTION CYCLE STARTED")
        log.info("=" * 60)
        
        with state_lock:
            local_copy = {nid: list(recs) for nid, recs in raw_buffer.items() 
                         if recs}
            raw_buffer.clear()
        
        for node_id, records in local_copy.items():
            try:
                # Extract readings
                soil_vals = [r.soil_moisture for r in records]
                vib_x = [r.vib_x for r in records]
                vib_y = [r.vib_y for r in records]
                vib_z = [r.vib_z for r in records]
                hum_vals = [r.humidity for r in records]
                
                # Calculate aggregate statistics
                soil_avg = float(np.mean(soil_vals))
                vib_max = max(max(vib_x), max(vib_y), max(vib_z))
                vib_rms = float(np.sqrt(np.mean(
                    [x**2 + y**2 + z**2 for x, y, z in zip(vib_x, vib_y, vib_z)]
                )))
                hum_avg = float(np.mean(hum_vals))
                
                # Location
                lat, lon = records[-1].lat, records[-1].lon
                
                # Fetch real-time data with caching
                with state_lock:
                    if node_id not in soil_cache:
                        soil_data = fetch_soil_data(lat, lon)
                        soil_cache[node_id] = soil_data
                    else:
                        soil_data = soil_cache[node_id]
                    
                    if node_id not in weather_cache:
                        weather_data = fetch_weather_data(lat, lon)
                        weather_cache[node_id] = weather_data
                    else:
                        weather_data = weather_cache[node_id]
                
                # Node properties
                props = NODE_PROPS.get(node_id, NODE_PROPS[1])
                
                # Build feature vector
                features = [
                    soil_avg,                          # soil_moisture
                    vib_max,                           # vib_max
                    vib_rms,                           # vib_rms
                    hum_avg,                           # humidity
                    weather_data.rainfall,             # rainfall
                    weather_data.temperature,          # temperature
                    weather_data.wind_speed,           # wind_speed
                    props.soil_type,                   # soil_type
                    props.soil_capacity,               # soil_capacity
                    props.slope,                       # slope
                    props.land_use,                    # land_use
                    props.ndvi                         # ndvi
                ]
                
                # ML prediction
                prob = ml_predict(features)
                risk = risk_level(prob)
                
                # Fire analysis
                merged_flame = {"front": 0, "right": 0, "back": 0, "left": 0}
                for r in records:
                    for direction, val in r.flame.items():
                        if val:
                            merged_flame[direction] = 1
                
                fire_info = analyse_fire_direction(merged_flame)
                
                now_str = datetime.now().isoformat()
                
                # Store result for dashboard
                with state_lock:
                    result_db[node_id] = PredictionResult(
                        node_id=node_id,
                        probability=prob,
                        risk_level=risk,
                        fire_detected=fire_info["fire_detected"],
                        fire_origin=fire_info["origin_directions"],
                        fire_spread=fire_info.get("spread_direction"),
                        features={
                            "soil_moisture": round(soil_avg, 2),
                            "vib_max": round(vib_max, 4),
                            "vib_rms": round(vib_rms, 4),
                            "humidity": round(hum_avg, 2),
                            "rainfall": round(weather_data.rainfall, 2),
                            "temperature": round(weather_data.temperature, 2),
                            "wind_speed": round(weather_data.wind_speed, 2),
                        },
                        timestamp=datetime.now()
                    )
                
                # Save to CSV
                csv_row = {
                    "soil_moisture": round(soil_avg, 3),
                    "vib_max": round(vib_max, 4),
                    "vib_rms": round(vib_rms, 4),
                    "humidity": round(hum_avg, 3),
                    "rainfall": round(weather_data.rainfall, 2),
                    "temperature": round(weather_data.temperature, 2),
                    "wind_speed": round(weather_data.wind_speed, 2),
                    "soil_type": props.soil_type,
                    "soil_capacity": props.soil_capacity,
                    "slope": props.slope,
                    "land_use": props.land_use,
                    "ndvi": props.ndvi,
                    "label": "",  # To be filled by expert
                    "fire_detected": int(fire_info["fire_detected"]),
                    "fire_origin": ",".join(fire_info["origin_directions"]),
                    "fire_spread": fire_info.get("spread_direction", ""),
                    "node_id": node_id,
                    "lat": round(lat, 6),
                    "lon": round(lon, 6),
                    "timestamp": now_str,
                }
                append_to_csv(csv_row)
                
                log.info(
                    f"Node {node_id} | Risk={risk} ({prob*100:.1f}%) | "
                    f"Fire={fire_info['fire_detected']} | "
                    f"Weather: {weather_data.temperature:.1f}°C, {weather_data.humidity}% RH"
                )
                
            except Exception as e:
                log.error(f"Prediction failed for node {node_id}: {e}", exc_info=True)


# ─────────────────────────────────────────────
# AUTO-RETRAIN LOOP (24 hours)
# ─────────────────────────────────────────────
def retrain_loop():
    """Retrain model every 24 hours"""
    global model, scaler
    
    while True:
        time.sleep(RETRAIN_INTERVAL)
        log.info("=" * 60)
        log.info("RETRAIN CYCLE STARTED")
        log.info("=" * 60)
        
        try:
            df = load_training_df()
            new_model, new_scaler = train_model(df)
            
            if new_model and new_scaler:
                try:
                    joblib.dump(new_model, MODEL_PATH)
                    joblib.dump(new_scaler, SCALER_PATH)
                    
                    with state_lock:
                        model = new_model
                        scaler = new_scaler
                    
                    labelled_count = len(df.dropna(subset=["label"]))
                    log.info(f"✓ Model retrained and saved "
                            f"({labelled_count} labelled samples)")
                except Exception as e:
                    log.error(f"Failed to save retrained model: {e}")
            else:
                log.info("Retrain skipped — insufficient labelled data")
                
        except Exception as e:
            log.error(f"Retrain failed: {e}", exc_info=True)


# ─────────────────────────────────────────────
# CACHE REFRESH LOOP (Soil data)
# ─────────────────────────────────────────────
def cache_refresh_loop():
    """Refresh soil data cache periodically"""
    while True:
        time.sleep(SOIL_FETCH_INTERVAL)
        log.info("Refreshing soil data cache...")
        
        with state_lock:
            for node_id in list(soil_cache.keys()):
                try:
                    props = NODE_PROPS.get(node_id, NODE_PROPS[1])
                    if node_id in raw_buffer and raw_buffer[node_id]:
                        latest_record = raw_buffer[node_id][-1]
                        soil_data = fetch_soil_data(
                            latest_record.lat, 
                            latest_record.lon
                        )
                        soil_cache[node_id] = soil_data
                except Exception as e:
                    log.warning(f"Cache refresh failed for node {node_id}: {e}")


# ─────────────────────────────────────────────
# FLASK APP
# ─────────────────────────────────────────────
app = Flask(__name__)


@app.route("/node-data", methods=["POST"])
def receive_node_data():
    """Receive sensor data from IoT gateway"""
    try:
        data = request.get_json(force=True)
        
        if data is None:
            return jsonify({"error": "No JSON received"}), 400
        
        # Validate required fields
        required = ["node_id", "soil_moisture", "vib_x", "vib_y", 
                   "vib_z", "lat", "lon"]
        if not all(field in data for field in required):
            return jsonify({"error": "Missing required fields"}), 400
        
        node_id = int(data["node_id"])
        
        # Create sensor reading
        reading = SensorReading(
            node_id=node_id,
            soil_moisture=float(data["soil_moisture"]),
            vib_x=float(data["vib_x"]),
            vib_y=float(data["vib_y"]),
            vib_z=float(data["vib_z"]),
            humidity=float(data.get("humidity", 60)),
            lat=float(data["lat"]),
            lon=float(data["lon"]),
            flame=data.get("flame", {"front": 0, "right": 0, 
                                    "back": 0, "left": 0}),
            timestamp=datetime.now()
        )
        
        # Buffer the reading
        with state_lock:
            raw_buffer.setdefault(node_id, []).append(reading)
        
        log.info(f"Received data from node {node_id}: "
                f"soil={reading.soil_moisture:.1f}%, "
                f"vib_max={max(abs(reading.vib_x), abs(reading.vib_y), abs(reading.vib_z)):.3f}g")
        
        return jsonify({"status": "received", "node_id": node_id}), 200
        
    except ValueError as e:
        return jsonify({"error": f"Invalid data type: {e}"}), 400
    except Exception as e:
        log.error(f"POST /node-data error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/data")
def api_data():
    """Latest prediction per node (REST API)"""
    with state_lock:
        data = {}
        for node_id, pred in result_db.items():
            data[str(node_id)] = {
                "node_id": pred.node_id,
                "risk": pred.risk_level,
                "probability": round(pred.probability * 100, 2),
                "fire_detected": pred.fire_detected,
                "fire_origin": pred.fire_origin,
                "fire_spread": pred.fire_spread,
                "features": pred.features,
                "timestamp": pred.timestamp.isoformat()
            }
    
    return jsonify(data)


@app.route("/api/realtime")
def api_realtime():
    """Real-time sensor data with fire analysis"""
    out = {}
    with state_lock:
        for node_id, records in raw_buffer.items():
            if not records:
                continue
            
            latest = records[-1]
            vib_max = max(abs(latest.vib_x), abs(latest.vib_y), abs(latest.vib_z))
            
            fire_info = analyse_fire_direction(latest.flame)
            
            out[str(node_id)] = {
                "node_id": node_id,
                "soil_moisture": round(latest.soil_moisture, 2),
                "vibration_max_g": round(vib_max, 4),
                "humidity": round(latest.humidity, 2),
                "location": {"lat": latest.lat, "lon": latest.lon},
                "fire": fire_info,
                "timestamp": latest.timestamp.isoformat()
            }
    
    return jsonify(out)


@app.route("/api/training-data")
def api_training_data():
    """Last 100 training rows as JSON"""
    try:
        df = load_training_df().tail(100)
        return jsonify(df.to_dict(orient="records"))
    except Exception as e:
        log.error(f"Failed to get training data: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/label", methods=["POST"])
def api_label():
    """
    Assign ground-truth label to a prediction
    POST: {"timestamp": "2024-01-01T12:00:00", "node_id": 1, "label": 1}
    """
    try:
        body = request.json
        ts = body.get("timestamp")
        node_id = body.get("node_id")
        label_val = body.get("label")
        
        if ts is None or label_val is None:
            return jsonify({"error": "timestamp and label required"}), 400
        
        df = load_training_df()
        
        mask = (df["timestamp"] == ts)
        if node_id is not None:
            mask &= (df["node_id"] == node_id)
        
        if mask.sum() == 0:
            return jsonify({"error": "No matching row found"}), 404
        
        df.loc[mask, "label"] = int(label_val)
        df.to_csv(TRAINING_CSV, index=False)
        
        log.info(f"Labelled {mask.sum()} row(s) at {ts}")
        return jsonify({"updated": int(mask.sum())})
        
    except Exception as e:
        log.error(f"Labelling failed: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/model-stats")
def api_model_stats():
    """Get model performance statistics"""
    try:
        df = load_training_df()
        labelled = df.dropna(subset=["label"])
        
        return jsonify({
            "total_rows": len(df),
            "labelled_rows": len(labelled),
            "unlabelled_rows": len(df) - len(labelled),
            "fire_events": int(df["fire_detected"].sum()),
            "landslide_labels": int(labelled[labelled["label"] == 1].shape[0]),
            "no_landslide_labels": int(labelled[labelled["label"] == 0].shape[0]),
            "ready_for_retrain": len(labelled) >= MIN_ROWS_RETRAIN
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/")
def index():
    """Serve dashboard HTML"""
    return render_template("index.html")


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    ensure_csv()
    
    # Start background threads
    threads = [
        ("PredictionLoop", prediction_loop),
        ("RetrainLoop", retrain_loop),
        ("CacheRefreshLoop", cache_refresh_loop),
    ]
    
    for name, target in threads:
        t = threading.Thread(target=target, daemon=True, name=name)
        t.start()
        log.info(f"Started {name}")
    
    log.info("="*60)
    log.info("SERVER STARTING")
    log.info("="*60)
    log.info(f"Predictions every {PREDICT_INTERVAL//60} minutes")
    log.info(f"Retrain every {RETRAIN_INTERVAL//3600} hours")
    log.info(f"Serving on http://0.0.0.0:5000")
    
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)