from flask import Flask, send_file
import io
import time
import logging
from weather import start_weather_thread, weather_state
from mqtt_client import start_mqtt_client, sensor_state, ZONE_SLOTS, ZONE_SOURCES
from renderer import render_dashboard

# Configure global logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(threadName)s | %(message)s')
logger = logging.getLogger("Dashboard")

app = Flask(__name__)

# Start background sync threads
start_weather_thread()
start_mqtt_client()

@app.route('/dashboard.png')
def get_dashboard():
    # Attempt to render
    img = render_dashboard(weather_state, sensor_state)
    
    # Save Image to byte buffer
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    
    logger.info("Rendered and successfully served /dashboard.png")
    
    # Disable cache to ensure display gets newest image
    response = send_file(img_byte_arr, mimetype='image/png')
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response

@app.route('/health')
def health():
    zones = sensor_state.zones()
    return {
        "status": "ok",
        "weather_updated_ago": time.time() - weather_state.last_update,
        "zones": {
            slot: (None if reading is None else {
                "sensor": reading.name,
                "age_seconds": round(reading.age, 1),
                "stale": reading.is_stale,
            })
            for slot, reading in zones.items()
        },
    }

@app.route('/sensors')
def sensors():
    """
    Every sensor the dashboard has actually heard from, and how each zone
    resolves. Use this when a zone reads '--' to tell a dead sensor apart from
    a friendly name that doesn't match what the app is looking for.
    """
    zones = sensor_state.zones()
    return {
        "sensors": sensor_state.all_sensors(),
        "zones": {
            slot: {
                "looking_for": ZONE_SOURCES[slot],
                "matched": zones[slot].name if zones[slot] else None,
            }
            for slot in ZONE_SLOTS
        },
    }

if __name__ == '__main__':
    logger.info("Starting Dashboard Application Server...")
    app.run(host='0.0.0.0', port=5000)
