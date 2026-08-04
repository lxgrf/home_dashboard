import os
import sys

# The app modules import each other flat (as they do inside the container),
# so app/ needs to be importable directly.
APP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app")
sys.path.insert(0, APP_DIR)

# On macOS the DejaVu fonts the container ships with aren't present, so point
# the renderer at something local. Must happen BEFORE importing the renderer.
_MAC_FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"
_MAC_FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
if os.path.exists(_MAC_FONT):
    os.environ.setdefault("FONT_PATH", _MAC_FONT)
    os.environ.setdefault("FONT_BOLD_PATH", _MAC_FONT_BOLD)

import requests
import datetime
from weather import weather_state
from mqtt_client import sensor_state, UPSTAIRS, DOWNSTAIRS, CONSERVATORY
from renderer import render_dashboard

OUT_PATH = os.environ.get(
    "DEMO_OUT", os.path.join(os.path.dirname(os.path.abspath(__file__)), "weather.png")
)

# Stand-in readings so the layout can be checked without a Zigbee network
MOCK_ZONES = {
    UPSTAIRS: {"temperature": 19.4, "humidity": 58.0},
    DOWNSTAIRS: {"temperature": 20.1, "humidity": 55.0},
    CONSERVATORY: {"temperature": 24.3, "humidity": 48.0},
}


def run_demo():
    # 1. Fetch real weather data from Open-Meteo
    lat = os.environ.get("LATITUDE", "51.5072")
    lon = os.environ.get("LONGITUDE", "-0.1276")
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,relative_humidity_2m,weather_code,is_day"
        "&daily=weather_code,temperature_2m_max,temperature_2m_min"
        "&hourly=temperature_2m,relative_humidity_2m,weather_code,is_day&timezone=auto"
    )
    print("Fetching weather info...")
    response = requests.get(url, timeout=10)
    data = response.json()

    weather_state.current_temp = data["current"]["temperature_2m"]
    weather_state.current_rh = data["current"]["relative_humidity_2m"]
    weather_state.weather_code = data["current"]["weather_code"]
    weather_state.is_day = data["current"].get("is_day", 1)
    weather_state.daily_max = data["daily"]["temperature_2m_max"][0]
    weather_state.daily_min = data["daily"]["temperature_2m_min"][0]

    # Process hourly forecast correctly for demo
    hourly_times = data["hourly"]["time"]
    now_str = data["current"]["time"]
    try:
        current_idx = next(i for i, t in enumerate(hourly_times) if t[:13] == now_str[:13])
    except StopIteration:
        current_idx = 0

    forecasts = []
    for offset in range(1, 25):
        idx = current_idx + offset
        if idx < len(hourly_times):
            forecasts.append({
                # Full ISO timestamp: the renderer needs the date to tell
                # "14:00 today" from "14:00 tomorrow"
                "time": hourly_times[idx],
                "temp": data["hourly"]["temperature_2m"][idx],
                "rh": data["hourly"]["relative_humidity_2m"][idx],
                "code": data["hourly"]["weather_code"][idx],
                "is_day": data["hourly"]["is_day"][idx],
            })
    weather_state.hourly_forecast = forecasts
    weather_state.last_update = datetime.datetime.now().timestamp()

    # 2. Mock the sensor states
    for name, payload in MOCK_ZONES.items():
        sensor_state.update(name, payload)

    print(f"Weather: {weather_state.current_temp}C, {weather_state.current_rh}%")
    for slot, payload in MOCK_ZONES.items():
        print(f"{slot.title()}: {payload['temperature']}C, {payload['humidity']}%")

    # 3. Render
    print("Rendering...")
    img = render_dashboard(weather_state, sensor_state)

    # 4. Save
    img.save(OUT_PATH)
    print(f"Saved to {OUT_PATH}")


if __name__ == "__main__":
    run_demo()
