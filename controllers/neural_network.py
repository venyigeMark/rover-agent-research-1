import json
import socket
import uuid
import time
import numpy as np
import tensorflow as tf

HOST = '127.0.0.1'
PORT = 8765

def send_request(sock, request_dict):
    payload = json.dumps(request_dict).encode('utf-8')
    # A C# szerver a frame hosszát 4 bájtban várja (hosszPuffer)
    prefix = len(payload).to_bytes(4, byteorder='big')
    sock.sendall(prefix + payload)

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

def create_actor_model(input_size, output_size=2):
    return tf.keras.Sequential([
        tf.keras.layers.InputLayer(input_shape=(input_size,)),
        tf.keras.layers.Dense(128, activation='relu'),
        tf.keras.layers.Dense(64, activation='relu'),
        tf.keras.layers.Dense(64, activation='relu'),
        tf.keras.layers.Dense(32, activation='relu'),
        tf.keras.layers.Dense(output_size, activation='tanh')
    ])

def train_rover_rl():
    input_size = 12 # 3 szín + 6 LiDAR + 1 sebesség + 2 GPS (szimulált)
    actor = create_actor_model(input_size)
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        print("Sikeres TCP kapcsolat a Unityvel!")
        
        for episode in range(1, 2001):
            print(f"--- {episode}. Epizód indul ---")
            
            # Pálya és akadályok alaphelyzetbe állítása
            send_request(s, {"request_id": str(uuid.uuid4()), "command": "reset_position"})
            receive_response(s)
            
            done = False
            lpesek_szama = 0
            
            while not done and lpesek_szama < 100:
                lpesek_szama += 1
                
                # Állapot lekérése
                send_request(s, {"request_id": str(uuid.uuid4()), "command": "observe"})
                state_resp = receive_response(s)
                
                if not state_resp or state_resp.get('status') != 'completed':
                    continue
                
                # Szenzoradatok kinyerése
                sensor_left = 1.0 if state_resp['sensor_left']['white'] else 0.0
                sensor_center = 1.0 if state_resp['sensor_center']['white'] else 0.0
                sensor_right = 1.0 if state_resp['sensor_right']['white'] else 0.0
                speed = state_resp['speed']
                lidar_min = state_resp['lidar_szektor_min']
                
                # Jelenleg a GPS vektort véletlenszerűen szimuláljuk, amíg nincs beépítve a backendbe
                gps_vektor = [np.random.rand(), np.random.rand()] 
                
                current_state = np.array([[sensor_left, sensor_center, sensor_right] + lidar_min + [speed] + gps_vektor], dtype=np.float32)
                
                # Akció kiválasztása zajjal (felfedezés)
                action = actor(current_state).numpy()[0]
                noise = np.random.normal(0, 0.2, size=2)
                action = np.clip(action + noise, -1.0, 1.0)
                steering, throttle = action[0], action[1]
                
                # Mozgás vagy fordulás parancs küldése
                cmd_req_id = str(uuid.uuid4())
                if abs(steering) > 0.1:
                    angle = float(steering * 20.0)
                    send_request(s, {
                        "request_id": cmd_req_id, "command": "turn", 
                        "angle_deg": angle, "max_angular_speed": 45.0
                    })
                else:
                    dist = float(max(0.01, throttle * 0.2))
                    send_request(s, {
                        "request_id": cmd_req_id, "command": "move", 
                        "distance_m": dist, "max_speed": 0.5
                    })
                
                # Parancs befejezésének megvárása
                receive_response(s)
                
                # (Itt történne a jutalom kiszámítása és a hálózat súlyainak frissítése)
                
                # Együtközés megszakítja az epizódot
                if state_resp.get('collision_occurred', False):
                    done = True

if __name__ == "__main__":
    train_rover_rl()