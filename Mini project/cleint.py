import socket

esp32_ip = "192.168.1.50"  # Replace with your ESP32 IP
port = 80

# Create a socket connection
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect((esp32_ip, port))

# Send data
client.sendall(b"Hello ESP32")

# Receive response
response = client.recv(1024)
print("Received:", response.decode())

client.close()