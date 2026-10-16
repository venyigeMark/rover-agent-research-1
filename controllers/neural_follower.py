import json
import socket
import uuid
import time
import numpy as np
import tensorflow as tf

# 1. A betanított TensorFlow modell betöltése
MODEL_PATH = 'rover_tf_model.keras'
model = tf.keras.models.load_model(MODEL_PATH)
print("Neurális háló sikeresen betöltve!")

# TCP Kapcsolat beállításai a RoverGatewayServer.cs alapján
HOST = '127.0.0.1'
PORT = 8765

# Segédfüggvény: Kérés küldése a 4 bájtos big-endian prefixszel
def send_request(sock, request_dict):
    json_str = json.dumps(request_dict)
    payload = json_str.encode('utf-8')
    # A C# szerver a frame hosszát 4 bájtban várja (hosszPuffer)
    prefix = len(payload).to_bytes(4, byteorder='big')
    sock.sendall(prefix + payload)

# Segédfüggvény: Válasz fogadása
def receive_response(sock):
    prefix = sock.recv(4)
    if not prefix:
        return None
    length = int.from_bytes(prefix, byteorder='big')
    payload = b""
    while len(payload) < length:
        chunk = sock.recv(length - len(payload))
        if not chunk:
            break
        payload += chunk
    return json.loads(payload.decode('utf-8'))

def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        print(f"Sikeresen kapcsolódva a Unity RoverGatewayServer-hez a {PORT}-es porton!")

        while True:
            # 1. Állapot lekérdezése (observe parancs)
            req_id = str(uuid.uuid4())
            send_request(s, {"request_id": req_id, "command": "observe"})
            state = receive_response(s)

            if not state or state.get('status') != 'completed':
                time.sleep(0.1)
                continue

            # 2. Bemeneti vektor összeállítása a szenzorokból (SensorArray és LidarSensor)
            # A C# ObserveValasz osztálya alapján nyerjük ki az adatokat
            sensor_left = state['sensor_left']['intensity']
            sensor_center = state['sensor_center']['intensity']
            sensor_right = state['sensor_right']['intensity']
            speed = state['speed']
            lidar_min = state['lidar_szektor_min'] # Ez egy tömb, alapértelmezetten 6 szektorral

            # A 10 dimenziós bemeneti tömb a neurális hálónak (3 szín + 6 LiDAR + 1 sebesség)
            input_features = [sensor_left, sensor_center, sensor_right] + lidar_min + [speed]
            input_tensor = np.array([input_features], dtype=np.float32)

            # 3. Neurális háló futtatása (Inference)
            action = model.predict(input_tensor, verbose=0)[0]
            steering = action[0] # -1.0 és 1.0 közötti érték
            throttle = action[1] # -1.0 és 1.0 közötti érték

            # 4. Modell kimenetének megfeleltetése a RoverGatewayServer protokolljának
            # Mivel a szerver diszkrét lépéseket vár (move vagy turn), döntenünk kell:
            cmd_req_id = str(uuid.uuid4())
            
            if abs(steering) > 0.1: 
                # Ha a háló szerint kanyarodni kell, kiadjuk a 'turn' parancsot
                # A C# turn parancs angle_deg-t (fokot) és max_angular_speed-et vár
                angle = float(steering * 20.0) # max 20 fokos fordulás
                send_request(s, {
                    "request_id": cmd_req_id,
                    "command": "turn",
                    "angle_deg": angle,
                    "max_angular_speed": 45.0 # Maximálisan engedélyezett érték
                })
            else: 
                # Ha egyenesen kell menni, kiadjuk a 'move' parancsot
                # A C# move parancs distance_m-t és max_speed-et vár
                dist = float(max(0.01, throttle * 0.2)) # max 20 centi előre
                send_request(s, {
                    "request_id": cmd_req_id,
                    "command": "move",
                    "distance_m": dist,
                    "max_speed": 0.5 # Maximálisan engedélyezett érték
                })
            
            # 5. Megvárjuk, amíg a mozgás / fordulás befejeződik, mielőtt újabb ciklust indítunk
            receive_response(s)

if __name__ == "__main__":
    main()