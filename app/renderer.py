from PIL import Image, ImageDraw, ImageFont
import os
from humidity_calc import get_resulting_indoor_rh
from icons import get_weather_icon

FONT_PATH = os.environ.get("FONT_PATH", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
FONT_BOLD_PATH = os.environ.get("FONT_BOLD_PATH", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
TARGET_HUMIDITY = float(os.environ.get("TARGET_HUMIDITY", 55.0))

def render_dashboard(weather_state, sensor_state):
    # Create 400x300 image (monochrome compatible colors)
    img = Image.new('RGB', (400, 300), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    try:
        font_huge = ImageFont.truetype(FONT_BOLD_PATH, 52)
        font_large = ImageFont.truetype(FONT_BOLD_PATH, 32)
        font_med = ImageFont.truetype(FONT_BOLD_PATH, 24)
        font_small = ImageFont.truetype(FONT_PATH, 20)
    except Exception:
        font_huge = font_large = font_med = font_small = ImageFont.load_default()

    # Raw numeric values for calculations
    w_temp_raw = weather_state.current_temp
    w_rh_raw = weather_state.current_rh
    in_temp_raw = sensor_state.inside_temp
    in_rh_raw = sensor_state.inside_rh

    # Display-safe values
    w_temp = w_temp_raw if w_temp_raw is not None else "--"
    w_rh = w_rh_raw if w_rh_raw is not None else "--"
    w_code = weather_state.weather_code
    w_day = weather_state.is_day

    in_temp = in_temp_raw if in_temp_raw is not None else "--"
    in_rh = in_rh_raw if in_rh_raw is not None else "--"

    top_y = 0
    split_y = 150
    bottom_y = split_y + 8

    # ========= TOP BAND: Outdoor =========
    draw.text((12, top_y + 8), "OUTDOOR", font=font_med, fill=(0, 0, 0))
    draw.text((12, top_y + 34), f"{w_temp}°", font=font_huge, fill=(0, 0, 0))
    draw.text((18, top_y + 94), f"RH {w_rh}%", font=font_small, fill=(90, 90, 90))

    if w_code is not None:
        try:
            # Huge 4x icon scaled and centered on the right pane's axis (x=310)
            icon = get_weather_icon(w_code, w_day, size="4x")
            icon = icon.resize((140, 140), Image.Resampling.LANCZOS)
            img.paste(icon, (310 - 70, top_y + 6), mask=icon if icon.mode == 'RGBA' else None)
        except Exception:
            pass

    # ========= Window Decision =========
    if None in (w_temp_raw, w_rh_raw, in_temp_raw):
        is_safe_now = False # Default
        timing_msg = "Wait data"
    else:
        try:
            current_resulting_rh = get_resulting_indoor_rh(w_temp_raw, w_rh_raw, in_temp_raw)
        except (TypeError, ValueError):
            current_resulting_rh = None

        if current_resulting_rh is None:
            is_safe_now = False
            timing_msg = "Wait data"
        else:
            is_safe_now = current_resulting_rh < TARGET_HUMIDITY

            flip_time = None
            for fcast in getattr(weather_state, 'hourly_forecast', []) or []:
                try:
                    f_rh = get_resulting_indoor_rh(fcast['temp'], fcast['rh'], in_temp_raw)
                except (TypeError, ValueError, KeyError):
                    continue

                f_safe = f_rh < TARGET_HUMIDITY
                if f_safe != is_safe_now:
                    flip_time = fcast.get('time', '--:--')
                    break

            if is_safe_now:
                timing_msg = f"Close at {flip_time}" if flip_time else "Open All Day"
            else:
                timing_msg = f"Open at {flip_time}" if flip_time else "Closed All Day"

    # ========= BOTTOM BAND: Indoor =========
    draw.line((0, split_y, 400, split_y), fill=(220, 0, 0), width=3)
    draw.text((12, bottom_y + 2), "INDOOR", font=font_med, fill=(0, 0, 0))
    draw.text((12, bottom_y + 28), f"{in_temp}°", font=font_huge, fill=(0, 0, 0))
    draw.text((18, bottom_y + 88), f"RH {in_rh}%", font=font_small, fill=(90, 90, 90))

    wx, wy = 310 - 40, 166
    ww, wh = 80, 72
    
    if is_safe_now:
        # BLACK OPEN WINDOW (Polygons)
        frame_color = (0, 0, 0)
        draw.rectangle((wx, wy, wx+ww, wy+wh), outline=frame_color, width=6)
        # Left swung pane
        draw.polygon([(wx, wy), (wx+20, wy-12), (wx+20, wy+wh+12), (wx, wy+wh)], fill=frame_color)
        # Right swung pane
        draw.polygon([(wx+ww, wy), (wx+ww-20, wy-12), (wx+ww-20, wy+wh+12), (wx+ww, wy+wh)], fill=frame_color)
        
    else:
        # RED CLOSED WINDOW
        frame_color = (220, 0, 0)
        draw.rectangle((wx, wy, wx+ww, wy+wh), fill=frame_color)
        pane_w = (ww - 16) // 2
        pane_h = (wh - 16) // 2
        draw.rectangle((wx+6, wy+6, wx+6+pane_w, wy+6+pane_h), fill=(255, 255, 255))
        draw.rectangle((wx+10+pane_w, wy+6, wx+10+pane_w+pane_w, wy+6+pane_h), fill=(255, 255, 255))
        draw.rectangle((wx+6, wy+10+pane_h, wx+6+pane_w, wy+10+pane_h+pane_h), fill=(255, 255, 255))
        draw.rectangle((wx+10+pane_w, wy+10+pane_h, wx+10+pane_w+pane_w, wy+10+pane_h+pane_h), fill=(255, 255, 255))

    draw.text((310, wy + wh + 20), timing_msg, fill=(0, 0, 0), font=font_med, anchor="ma")

    return img
