from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)
latest_data = {}

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>IoT Node Monitoring</title>
</head>
<body>
    <h1>ESP32 Node Data</h1>
    {% if data %}
    <ul>
        <li><b>Node ID:</b> {{ data.node_id }}</li>
        <li><b>Latitude:</b> {{ data.lat }}</li>
        <li><b>Longitude:</b> {{ data.lon }}</li>
        <li><b>Soil Moisture (%):</b> {{ data.soil_moisture }}</li>
        <li><b>Vibration X:</b> {{ data.vibration_x }}</li>
        <li><b>Vibration Y:</b> {{ data.vibration_y }}</li>
        <li><b>Vibration Z:</b> {{ data.vibration_z }}</li>
    </ul>
    {% else %}
    <p>No data received yet.</p>
    {% endif %}
</body>
</html>
"""

@app.route("/data", methods=["POST"])
def receive_data():
    global latest_data
    latest_data = request.json
    print("Received:", latest_data)
    return jsonify({"status": "OK"})

@app.route("/")
def dashboard():
    return render_template_string(HTML, data=latest_data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
