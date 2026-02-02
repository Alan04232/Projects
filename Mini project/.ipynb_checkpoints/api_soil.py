import requests
from datetime import datetime

LAT = 8.95
LON = 76.78

# ---------------- FREE WEATHER API ----------------
weather_url = (
    f"https://api.open-meteo.com/v1/forecast?"
    f"latitude={LAT}&longitude={LON}"
    f"&current=temperature_2m,relativehumidity_2m,precipitation,pressure_msl"
)

weather = requests.get(weather_url, timeout=10).json()["current"]

# ---------------- FREE ELEVATION API ----------------
elevation = requests.get(
    f"https://api.open-meteo.com/v1/elevation?"
    f"latitude={LAT}&longitude={LON}",
    timeout=10
).json()["elevation"]

"""wind_speed = requests.get(
    f"https://api.open-meteo.com/v1/wind_speed_10m?"
    f"latitude={LAT}&longitude={LON}",
    timeout=10
).json()["wind_speed"]"""

# ---------------- SOIL BASELINE (STATIC / OFFLINE) ----------------
soil_baseline = {
    "soil_type": "Lateritic clay",
    "water_holding_capacity": "High",
    "soil_ph": 5.6,
    "drainage": "Poor to Moderate"
}

# ---------------- DISPLAY DATA ----------------
print("\n📊 DISASTER DATA FUSION (SAFE MODE)")
print("----------------------------------")
print("Time:", datetime.now())

print("\n🌦 Weather (API)")
print("Temperature (°C):", weather["temperature_2m"])
print("Humidity (%):", weather["relativehumidity_2m"])
print("Rainfall (mm):", weather["precipitation"])
print("Pressure (hPa):", weather["pressure_msl"])

print("\n⛰ Terrain")
print("Elevation (m):", elevation)
#print("wind_speed:", wind_speed)

print("\n🌱 Soil Baseline (Static)")
print("Soil Type:", soil_baseline["soil_type"])
print("Water Holding Capacity:", soil_baseline["water_holding_capacity"])
print("Soil pH:", soil_baseline["soil_ph"])
print("Drainage:", soil_baseline["drainage"])

print("----------------------------------")
