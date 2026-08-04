import paho.mqtt.client as mqtt
import json
import os
import threading
import time
import logging

logger = logging.getLogger("MQTT")

MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "zigbee2mqtt/+")

# A reading older than this is treated as unusable and shown as "--"
STALE_AFTER = float(os.getenv("STALE_AFTER", 30 * 60))

# The three zones the dashboard knows about. Upstairs drives the window
# decision (the dehumidifier lives there); the others are reported for interest.
UPSTAIRS = "upstairs"
DOWNSTAIRS = "downstairs"
CONSERVATORY = "conservatory"
ZONE_SLOTS = (UPSTAIRS, DOWNSTAIRS, CONSERVATORY)

ZONE_LABELS = {
    UPSTAIRS: "UPSTAIRS",
    DOWNSTAIRS: "DOWNSTAIRS",
    CONSERVATORY: "CONSERVATORY",
}

# ZONE_UPSTAIRS / ZONE_DOWNSTAIRS / ZONE_CONSERVATORY map a zigbee2mqtt friendly
# name onto a slot. Unset means "the device is already named after its slot".
# docker-compose passes these through as empty strings when absent from .env,
# so blank is treated as unset rather than as a device named "".
_ZONE_ENV = {slot: os.getenv(f"ZONE_{slot.upper()}", "").strip() for slot in ZONE_SLOTS}
ZONE_SOURCES = {slot: (_ZONE_ENV[slot] or slot) for slot in ZONE_SLOTS}
ZONE_CONFIGURED = {slot: bool(_ZONE_ENV[slot]) for slot in ZONE_SLOTS}

# The wildcard portion of MQTT_TOPIC is the device's friendly name, so the base
# is whatever precedes it: "zigbee2mqtt/+" -> "zigbee2mqtt".
_TOPIC_BASE = MQTT_TOPIC.split("+")[0].split("#")[0].rstrip("/")


def device_from_topic(topic: str):
    """
    Extract the zigbee2mqtt friendly name from a topic, or None if the topic
    isn't a device state message.

    Rejects bridge traffic ("zigbee2mqtt/bridge/devices") and per-device
    sub-topics ("zigbee2mqtt/upstairs/availability"), both of which carry
    payloads we must not mistake for readings.
    """
    if _TOPIC_BASE:
        prefix = _TOPIC_BASE + "/"
        if not topic.startswith(prefix):
            return None
        rest = topic[len(prefix):]
    else:
        rest = topic

    if not rest or "/" in rest or rest == "bridge":
        return None
    return rest


class ZoneReading:
    def __init__(self, name):
        self.name = name
        self.temp = None
        self.rh = None
        self.battery = None
        self.last_update = 0.0

    @property
    def age(self):
        return time.time() - self.last_update

    @property
    def is_stale(self):
        return self.last_update == 0.0 or self.age > STALE_AFTER

    def as_dict(self):
        return {
            "name": self.name,
            "temperature": self.temp,
            "humidity": self.rh,
            "battery": self.battery,
            "age_seconds": round(self.age, 1),
            "stale": self.is_stale,
        }


class SensorState:
    def __init__(self):
        self.sensors = {}  # friendly name -> ZoneReading
        self.lock = threading.Lock()
        self._warned_fallback = False

    def update(self, name, payload):
        with self.lock:
            reading = self.sensors.get(name)
            if reading is None:
                reading = ZoneReading(name)
                self.sensors[name] = reading
                logger.info(f"Discovered Zigbee sensor '{name}'")
            reading.temp = payload["temperature"]
            reading.rh = payload["humidity"]
            reading.battery = payload.get("battery")
            reading.last_update = time.time()
        return reading

    def _resolve(self, slot):
        """Find the reading for a slot. Caller holds the lock."""
        reading = self.sensors.get(ZONE_SOURCES[slot])
        if reading is not None:
            return reading

        # Before the extra sensors are installed there is exactly one device,
        # very likely still named after its IEEE address. Treat it as Upstairs
        # so the existing display keeps working untouched.
        if slot == UPSTAIRS and not ZONE_CONFIGURED[UPSTAIRS] and len(self.sensors) == 1:
            only = next(iter(self.sensors.values()))
            if not self._warned_fallback:
                logger.warning(
                    f"No sensor named '{ZONE_SOURCES[UPSTAIRS]}'; falling back to the only "
                    f"sensor present ('{only.name}') for Upstairs. Rename it in zigbee2mqtt "
                    f"or set ZONE_UPSTAIRS to silence this."
                )
                self._warned_fallback = True
            return only
        return None

    def zone(self, slot):
        """Current reading for a zone, or None if no sensor is mapped to it."""
        with self.lock:
            return self._resolve(slot)

    def zones(self):
        with self.lock:
            return {slot: self._resolve(slot) for slot in ZONE_SLOTS}

    def all_sensors(self):
        with self.lock:
            return [r.as_dict() for r in self.sensors.values()]

    # Kept so demo.py, /health and anything else reading a single indoor value
    # continue to work. Upstairs is the zone that matters for the decision.
    @property
    def inside_temp(self):
        reading = self.zone(UPSTAIRS)
        return reading.temp if reading else None

    @property
    def inside_rh(self):
        reading = self.zone(UPSTAIRS)
        return reading.rh if reading else None

    @property
    def last_update(self):
        reading = self.zone(UPSTAIRS)
        return reading.last_update if reading else 0.0


sensor_state = SensorState()


def on_connect(client, userdata, flags, rc):
    logger.info(f"Connected to Mosquitto broker with code {rc}. Subscribing to {MQTT_TOPIC}")
    client.subscribe(MQTT_TOPIC)


def on_message(client, userdata, msg):
    name = device_from_topic(msg.topic)
    if name is None:
        return

    try:
        payload = json.loads(msg.payload.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return

    # Many Zigbee temperature/humidity sensors output "temperature" and "humidity"
    if not isinstance(payload, dict):
        return
    if "temperature" not in payload or "humidity" not in payload:
        return

    reading = sensor_state.update(name, payload)
    logger.info(f"'{reading.name}': {reading.temp}C, RH {reading.rh}%")


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
