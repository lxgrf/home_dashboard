import os
import requests
import datetime
from app.weather import weather_state
from app.mqtt_client import sensor_state
from app.renderer import render_dashboard

# We are on macOS, so tell renderer to use a local font for demo
os.environ["FONT_PATH"] = "/System/Library/Fonts/Supplemental/Arial.ttf"
os.environ["FONT_BOLD_PATH"] = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

def run_demo():
    # 1. Fetch real weather data from Open-Meteo
    url = f"https://api.open-meteo.com/v1/forecast?latitude=51.5072&longitude=-0.1276&current=temperature_2m,relative_humidity_2m,weather_code,is_day&daily=weather_code,temperature_2m_max,temperature_2m_min&hourly=temperature_2m,relative_humidity_2m,weather_code,is_day&timezone=auto"
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
    except Exception:
        current_idx = 0

    forecasts = []
    for offset in range(1, 25):
        idx = current_idx + offset
        if idx < len(hourly_times):
            t_str = hourly_times[idx].split('T')[1]
            forecasts.append({
                "time": t_str,
                "temp": data["hourly"]["temperature_2m"][idx],
                "rh": data["hourly"]["relative_humidity_2m"][idx],
                "code": data["hourly"]["weather_code"][idx],
                "is_day": data["hourly"]["is_day"][idx]
            })
    weather_state.hourly_forecast = forecasts
    weather_state.last_update = datetime.datetime.now().timestamp()
    
    # 2. Mock the sensor states
    sensor_state.inside_temp = 19.0
    sensor_state.inside_rh = 50.0
    
    print(f"Weather: {weather_state.current_temp}C, {weather_state.current_rh}%")
    print(f"Inside: {sensor_state.inside_temp}C, {sensor_state.inside_rh}%")
    
    # 3. Render
    print("Rendering...")
    img = render_dashboard(weather_state, sensor_state)
    
    # 4. Save
    out_path = "/Users/lxgrf/Code/home_dashboard/weather.png"
    img.save(out_path)
    print(f"Saved to {out_path}")

    # 5. Copy to artifacts for display
    artifact_path = "/Users/lxgrf/.gemini/antigravity/brain/a1223a09-420b-4bb2-b200-7c5fa708332f/rendered_dashboard.png"
    img.save(artifact_path)
    print(f"Saved to {artifact_path}")

if __name__ == "__main__":
    run_demo()
