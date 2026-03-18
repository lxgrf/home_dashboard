from flask import Flask, send_file
import io
import time
from weather import start_weather_thread, weather_state
from mqtt_client import start_mqtt_client, sensor_state
from renderer import render_dashboard

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
    
    # Disable cache to ensure display gets newest image
    response = send_file(img_byte_arr, mimetype='image/png')
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response

@app.route('/health')
def health():
    return {"status": "ok", "weather_updated_ago": time.time() - weather_state.last_update}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
