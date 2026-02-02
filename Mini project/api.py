import requests

LAT = 9.896
LON =76.96

# Open-Meteo (Weather)
weather_url = (
    f"https://api.open-meteo.com/v1/forecast?"
    f"latitude={LAT}&longitude={LON}"
    f"&hourly=temperature_2m,relativehumidity_2m,precipitation,pressure_msl"
)

weather_data = requests.get(weather_url).json()

# NASA POWER (Satellite Rainfall)
nasa_url = (
    f"https://power.larc.nasa.gov/api/temporal/daily/point?"
    f"parameters=PRECTOT&latitude={LAT}&longitude={LON}&format=JSON"
)

nasa_data = requests.get(nasa_url).json()

print("\n🌦 Weather Data (Open-Meteo)")
print("Temperature:", weather_data["hourly"]["temperature_2m"][0])
print("Humidity:", weather_data["hourly"]["relativehumidity_2m"][0])
print("Rainfall:", weather_data["hourly"]["precipitation"][0])
print("Pressure:", weather_data["hourly"]["pressure_msl"][0])

