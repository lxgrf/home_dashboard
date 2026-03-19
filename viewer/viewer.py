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
INKY_COLOR = os.environ.get("INKY_COLOR", "red")

print("Initializing Inky pHAT/wHAT display over SPI/I2C...")
try:
    display = auto()
    print(f"Success! Detected ePaper Display: {display.resolution[0]}x{display.resolution[1]} ({display.colour})")
except Exception as e:
    print(f"Auto-detect failed ({e}). Falling back to manual InkyWHAT initialization...")
    from inky import InkyWHAT
    
    # Defaults to 'red' corresponding to Black/White/Red wHATs, but can be overridden
    inky_color = os.environ.get("INKY_COLOR", "red")
    display = InkyWHAT(inky_color)
    print(f"Success! Manually initialized InkyWHAT ({inky_color})")

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
            display.set_border(display.WHITE)
            display.set_image(image)
            display.show()
            print(f"[{time.strftime('%H:%M:%S')}] Hardware refresh complete. Sleeping for {UPDATE_INTERVAL // 60} minutes.")
            return True
            
        except Exception as e:
            retries += 1
            import traceback
            print(f"Network or display error (Attempt {retries}/{MAX_RETRIES}): {e}")
            traceback.print_exc()
            time.sleep(10) # 10s cooldown before retry
            
    print(f"[{time.strftime('%H:%M:%S')}] Failed to update screen after {MAX_RETRIES} attempts.")
    return False

if __name__ == "__main__":
    print(f"--- Started Remote Inky Dashboard Viewer ---")
    
    # Infinite Poll Loop
    while True:
        fetch_and_draw()
        time.sleep(UPDATE_INTERVAL)
