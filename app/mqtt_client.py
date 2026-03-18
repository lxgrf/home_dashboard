import paho.mqtt.client as mqtt
import json
import os
import threading
import time
import logging

logger = logging.getLogger("MQTT")

MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "zigbee2mqtt/+/settings")

class SensorState:
    def __init__(self):
        self.inside_temp = None
        self.inside_rh = None
        self.last_update = 0
        self.lock = threading.Lock()

sensor_state = SensorState()

def on_connect(client, userdata, flags, rc):
    logger.info(f"Connected to Mosquitto broker with code {rc}. Listening for Zigbee sensors...")
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
            logger.info(f"Zigbee payload matched: Inside Temp {sensor_state.inside_temp}C, RH {sensor_state.inside_rh}%")
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
                logger.error(f"MQTT disconnected, retrying in 5s... ({e})")
                time.sleep(5)
                
    t = threading.Thread(target=loop_forever, name="MQTTThread", daemon=True)
    t.start()
