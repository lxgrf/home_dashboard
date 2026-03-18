import time
import requests
import io
import os
import sys
from PIL import Image

try:
    from inky.auto import auto
except ImportError:
    print("Inky library not found! Is it installed?")
    sys.exit(1)

# Configuration from environment variables
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://192.168.1.125:5000/dashboard.png")
UPDATE_INTERVAL = int(os.environ.get("UPDATE_INTERVAL", 600))  # 10 minutes default
MAX_RETRIES = 5

print("Initializing Inky pHAT/wHAT display over SPI/I2C...")
try:
    display = auto()
    print(f"Success! Detected ePaper Display: {display.resolution[0]}x{display.resolution[1]} ({display.color})")
except Exception as e:
    print(f"CRITICAL: Failed to auto-detect Inky screen hardware. Is SPI/I2C mapped correctly? Error: {e}")
    sys.exit(1)

def fetch_and_draw():
    retries = 0
    while retries < MAX_RETRIES:
        try:
            print(f"[{time.strftime('%H:%M:%S')}] Fetching latest dashboard from {DASHBOARD_URL}")
            response = requests.get(DASHBOARD_URL, timeout=15)
            response.raise_for_status()
            
            # Load the byte stream into Pillow
            image = Image.open(io.BytesIO(response.content))
            
            # Ensure the image fits the recognized display bounds
            if image.size != display.resolution:
                print(f"Warning: Image size {image.size} doesn't precisely match hardware {display.resolution}. Pillow will attempt to draw anyway.")
            
            # Flush image buffer natively to the ePaper controller
            display.set_image(image)
            display.show()
            print(f"[{time.strftime('%H:%M:%S')}] Hardware refresh complete. Sleeping for {UPDATE_INTERVAL // 60} minutes.")
            return True
            
        except Exception as e:
            retries += 1
            print(f"Network or display error (Attempt {retries}/{MAX_RETRIES}): {e}")
            time.sleep(10) # 10s cooldown before retry
            
    print(f"[{time.strftime('%H:%M:%S')}] Failed to update screen after {MAX_RETRIES} attempts.")
    return False

if __name__ == "__main__":
    print(f"--- Started Remote Inky Dashboard Viewer ---")
    
    # Infinite Poll Loop
    while True:
        fetch_and_draw()
        time.sleep(UPDATE_INTERVAL)
