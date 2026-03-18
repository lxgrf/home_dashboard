import paho.mqtt.client as mqtt
import json
import os
import threading
import time

MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "zigbee2mqtt/+/settings") # Customize topic later based on sensor name
# Typical format for Z2M sensor: zigbee2mqtt/Sensor_Name
# We can listen to all and filter, or configure this strictly.
# A broader string like 'zigbee2mqtt/#' lets us catch all sensors in case user doesn't know name.

class SensorState:
    def __init__(self):
        self.inside_temp = None
        self.inside_rh = None
        self.last_update = 0
        self.lock = threading.Lock()

sensor_state = SensorState()

def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT broker with result code {rc}")
    # Subscribe to z2m root to find all temp/humidity sensors if they emit payload
    client.subscribe("zigbee2mqtt/+")

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode('utf-8'))
        # Many Zigbee temperature/humidity sensors output "temperature" and "humidity"
        if "temperature" in payload and "humidity" in payload:
            with sensor_state.lock:
                sensor_state.inside_temp = payload["temperature"]
                sensor_state.inside_rh = payload["humidity"]
                sensor_state.last_update = time.time()
            print(f"Sensor updated: {sensor_state.inside_temp}C, {sensor_state.inside_rh}% RH")
    except Exception as e:
        # Ignore messages that aren't JSON or don't have temp/humidity
        pass

def start_mqtt_client():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    
    def loop_forever():
        while True:
            try:
                client.connect(MQTT_HOST, MQTT_PORT, 60)
                client.loop_forever()
            except Exception as e:
                print(f"MQTT connection failed, retrying in 5 seconds... ({e})")
                time.sleep(5)
                
    t = threading.Thread(target=loop_forever, daemon=True)
    t.start()
