import requests
import time
import os
import threading

# Configuration
LATITUDE = os.getenv("LATITUDE", "51.5072")
LONGITUDE = os.getenv("LONGITUDE", "-0.1276")

# Global state to share between modules
class WeatherState:
    def __init__(self):
        self.current_temp = None
        self.current_rh = None
        self.weather_code = None
        self.is_day = 1
        self.daily_max = None
        self.daily_min = None
        self.hourly_forecast = [] # list of dicts: {'time': str, 'temp': float, 'rh': float, 'code': int, 'is_day': int}
        self.last_update = 0
        self.lock = threading.Lock()

weather_state = WeatherState()

def fetch_weather_loop():
    while True:
        try:
            # Added hourly=relative_humidity_2m
            url = f"https://api.open-meteo.com/v1/forecast?latitude={LATITUDE}&longitude={LONGITUDE}&current=temperature_2m,relative_humidity_2m,weather_code,is_day&daily=weather_code,temperature_2m_max,temperature_2m_min&hourly=temperature_2m,relative_humidity_2m,weather_code,is_day&timezone=auto"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Extract next 12 hours of forecast details
            # Find the current hour index from hourly times
            now_str = data["current"]["time"] if "time" in data["current"] else None
            hourly_times = data["hourly"]["time"]
            
            try:
                # Find the index closest to current, fallback to 0
                # "time" format is usually '2023-10-25T14:00'
                current_idx = 0
                for i, ht in enumerate(hourly_times):
                    # We can just match the first 14 chars 'YYYY-MM-DDTHH'
                    if now_str and ht[:13] == now_str[:13]:
                        current_idx = i
                        break
            except Exception:
                current_idx = 0

            forecasts = []
            # We fetch the next 24 hours to find when things flip
            for offset in range(1, 25):
                idx = current_idx + offset
                if idx < len(hourly_times):
                    # time is "YYYY-MM-DDTHH:MM", we only want the HH:MM or HH
                    t_str = hourly_times[idx].split('T')[1]
                    forecasts.append({
                        "time": t_str,
                        "temp": data["hourly"]["temperature_2m"][idx],
                        "rh": data["hourly"]["relative_humidity_2m"][idx],
                        "code": data["hourly"]["weather_code"][idx],
                        "is_day": data["hourly"]["is_day"][idx]
                    })
            
            with weather_state.lock:
                weather_state.current_temp = data["current"]["temperature_2m"]
                weather_state.current_rh = data["current"]["relative_humidity_2m"]
                weather_state.weather_code = data["current"]["weather_code"]
                weather_state.is_day = data["current"].get("is_day", 1)
                weather_state.daily_max = data["daily"]["temperature_2m_max"][0]
                weather_state.daily_min = data["daily"]["temperature_2m_min"][0]
                weather_state.hourly_forecast = forecasts
                weather_state.last_update = time.time()
                
            print(f"Weather updated: {weather_state.current_temp}C, {weather_state.current_rh}% RH")
        except Exception as e:
            print(f"Error fetching weather: {e}")
            
        # Poll every 15 minutes
        time.sleep(15 * 60)

def start_weather_thread():
    t = threading.Thread(target=fetch_weather_loop, daemon=True)
    t.start()
