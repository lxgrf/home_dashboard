import os
import requests
from io import BytesIO
from PIL import Image

CACHE_DIR = "/tmp/weather_icons"
os.makedirs(CACHE_DIR, exist_ok=True)

# Map WMO weather code to OpenWeatherMap icon ID base
WMO_TO_OWM = {
    0: "01",
    1: "02",
    2: "03",
    3: "04",
    45: "50", 48: "50",
    51: "09", 53: "09", 55: "09", 56: "09", 57: "09",
    61: "10", 63: "10", 65: "10", 66: "10", 67: "10",
    80: "10", 81: "10", 82: "10",
    71: "13", 73: "13", 75: "13", 77: "13", 85: "13", 86: "13",
    95: "11", 96: "11", 99: "11"
}

def get_icon_id(wmo_code, is_day):
    base = WMO_TO_OWM.get(wmo_code, "03") # default to somewhat cloudy if unknown
    suffix = "d" if is_day else "n"
    return f"{base}{suffix}"

def get_weather_icon(wmo_code, is_day, size="2x"):
    """
    Downloads or fetches from cache the OpenWeatherMap PNG icon.
    Returns a Pillow Image object (RGBA).
    """
    icon_id = get_icon_id(wmo_code, is_day)
    cache_path = os.path.join(CACHE_DIR, f"{icon_id}_{size}.png")
    
    if os.path.exists(cache_path):
        try:
            return Image.open(cache_path).convert("RGBA")
        except Exception:
            pass # corrupted cache, re-download
            
    # Download
    url = f"https://openweathermap.org/img/wn/{icon_id}@{size}.png"
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content)).convert("RGBA")
        img.save(cache_path)
        return img
    except Exception as e:
        print(f"Failed to fetch icon {icon_id}: {e}")
        # Return a blank transparent 50x50 image as fallback
        return Image.new("RGBA", (50, 50), (255, 255, 255, 0))
