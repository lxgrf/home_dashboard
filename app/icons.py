import math
import os
from PIL import Image, ImageDraw

CACHE_DIR = "/tmp/weather_icons"
os.makedirs(CACHE_DIR, exist_ok=True)

# Map WMO weather code to icon type base
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

_SIZE = 128
_BLACK = (0, 0, 0, 255)
_CLEAR = (255, 255, 255, 0)

# Fallback icon type when the WMO code is not in the mapping (partly cloudy)
_DEFAULT_ICON_TYPE = "03"


def get_icon_id(wmo_code, is_day):
    base = WMO_TO_OWM.get(wmo_code, _DEFAULT_ICON_TYPE)
    suffix = "d" if is_day else "n"
    return f"{base}{suffix}"


def _draw_sun(draw, cx, cy, r=28):
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=_BLACK)
    for i in range(8):
        angle = i * math.pi / 4
        x1 = cx + (r + 5) * math.cos(angle)
        y1 = cy + (r + 5) * math.sin(angle)
        x2 = cx + (r + 18) * math.cos(angle)
        y2 = cy + (r + 18) * math.sin(angle)
        draw.line([(x1, y1), (x2, y2)], fill=_BLACK, width=5)


def _draw_moon(draw, cx, cy, r=30):
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=_BLACK)
    # Erase an offset circle to create a crescent shape
    offset = int(r * 0.55)
    draw.ellipse(
        (cx - r + offset, cy - r - int(r * 0.15),
         cx + r + offset, cy + r - int(r * 0.15)),
        fill=_CLEAR,
    )


def _draw_cloud(draw, cx, cy, scale=1.0):
    s = scale
    bx, by = int(cx - 44 * s), int(cy - 10 * s)
    bw, bh = int(88 * s), int(26 * s)
    draw.rectangle((bx, by, bx + bw, by + bh), fill=_BLACK)
    draw.ellipse((bx - int(14 * s), by - int(4 * s),
                  bx + int(28 * s), by + bh), fill=_BLACK)
    draw.ellipse((bx + int(18 * s), by - int(20 * s),
                  bx + int(54 * s), by + int(16 * s)), fill=_BLACK)
    draw.ellipse((bx + int(42 * s), by - int(14 * s),
                  bx + int(80 * s), by + int(18 * s)), fill=_BLACK)
    draw.ellipse((bx + int(60 * s), by - int(4 * s),
                  bx + int(102 * s), by + bh), fill=_BLACK)


def _draw_rain_drops(draw, cx, base_y, count=3):
    spacing = 20
    start_x = cx - (count - 1) * spacing // 2
    for i in range(count):
        x = start_x + i * spacing
        draw.line([(x, base_y), (x - 5, base_y + 18)], fill=_BLACK, width=4)


def _draw_snow_dots(draw, cx, base_y, count=3):
    spacing = 22
    start_x = cx - (count - 1) * spacing // 2
    for i in range(count):
        x = start_x + i * spacing
        r = 5
        draw.ellipse((x - r, base_y - r, x + r, base_y + r), fill=_BLACK)
        draw.ellipse((x - r, base_y + 14 - r, x + r, base_y + 14 + r), fill=_BLACK)


def _draw_lightning(draw, cx, base_y):
    pts = [
        (cx + 8, base_y),
        (cx - 4, base_y + 18),
        (cx + 4, base_y + 18),
        (cx - 10, base_y + 38),
        (cx + 16, base_y + 16),
        (cx + 6, base_y + 16),
    ]
    draw.polygon(pts, fill=_BLACK)


def _make_icon(icon_type, is_day):
    img = Image.new("RGBA", (_SIZE, _SIZE), _CLEAR)
    draw = ImageDraw.Draw(img)
    cx, cy = _SIZE // 2, _SIZE // 2

    if icon_type == "01":  # Clear sky
        if is_day:
            _draw_sun(draw, cx, cy, r=30)
        else:
            _draw_moon(draw, cx, cy, r=32)

    elif icon_type == "02":  # Mainly clear — sun/moon + small cloud
        if is_day:
            _draw_sun(draw, cx - 14, cy - 16, r=22)
        else:
            _draw_moon(draw, cx - 14, cy - 16, r=24)
        _draw_cloud(draw, cx + 10, cy + 16, scale=0.7)

    elif icon_type == "03":  # Partly cloudy
        _draw_cloud(draw, cx, cy, scale=0.85)

    elif icon_type == "04":  # Overcast — two stacked clouds
        _draw_cloud(draw, cx - 8, cy - 12, scale=0.7)
        _draw_cloud(draw, cx + 4, cy + 12, scale=0.85)

    elif icon_type == "09":  # Drizzle / showers
        _draw_cloud(draw, cx, cy - 18, scale=0.85)
        _draw_rain_drops(draw, cx, cy + 32, count=3)

    elif icon_type == "10":  # Rain
        _draw_cloud(draw, cx, cy - 22, scale=0.85)
        _draw_rain_drops(draw, cx - 10, cy + 26, count=2)
        _draw_rain_drops(draw, cx + 10, cy + 36, count=2)

    elif icon_type == "11":  # Thunderstorm
        _draw_cloud(draw, cx, cy - 24, scale=0.85)
        _draw_lightning(draw, cx - 8, cy + 22)

    elif icon_type == "13":  # Snow
        _draw_cloud(draw, cx, cy - 18, scale=0.85)
        _draw_snow_dots(draw, cx, cy + 36, count=3)

    elif icon_type == "50":  # Fog / mist — horizontal bars
        for idx, (y_off, w) in enumerate(
            [(-24, 88), (-8, 72), (8, 80), (24, 64)]
        ):
            y = cy + y_off
            draw.line([(cx - w // 2, y), (cx + w // 2, y)], fill=_BLACK, width=12)

    return img


def get_weather_icon(wmo_code, is_day, size="2x"):
    """
    Generates a monochrome (black & white) weather icon.
    Returns a Pillow RGBA Image object.
    The size parameter is accepted for API compatibility but ignored.
    """
    icon_id = get_icon_id(wmo_code, is_day)
    # icon_id is always "{base}{suffix}", e.g. "01d" or "13n"
    base = icon_id[:-1] if len(icon_id) >= 2 else _DEFAULT_ICON_TYPE
    cache_path = os.path.join(CACHE_DIR, f"{icon_id}_mono.png")

    if os.path.exists(cache_path):
        try:
            return Image.open(cache_path).convert("RGBA")
        except Exception as e:
            print(f"Cached icon {cache_path} is corrupt, regenerating: {e}")

    img = _make_icon(base, is_day)
    img.save(cache_path)
    return img
