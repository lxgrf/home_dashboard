from PIL import Image, ImageDraw, ImageFont
import os
import requests
import datetime
from humidity_calc import get_resulting_indoor_rh
from icons import get_weather_icon

FONT_PATH = os.environ.get("FONT_PATH", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
FONT_BOLD_PATH = os.environ.get("FONT_BOLD_PATH", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")

def render_dashboard(weather_state, sensor_state):
    # Create 400x300 image (monochrome compatible colors)
    img = Image.new('RGB', (400, 300), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    try:
        font_huge = ImageFont.truetype(FONT_BOLD_PATH, 60)
        font_large = ImageFont.truetype(FONT_BOLD_PATH, 32)
        font_med = ImageFont.truetype(FONT_BOLD_PATH, 24)
        font_small = ImageFont.truetype(FONT_PATH, 20)
        font_xsmall = ImageFont.truetype(FONT_PATH, 16)
    except Exception:
        font_huge = font_large = font_med = font_small = font_xsmall = ImageFont.load_default()

    # Variables
    w_temp = weather_state.current_temp if weather_state.current_temp is not None else "--"
    w_rh = weather_state.current_rh if weather_state.current_rh is not None else "--"
    w_code = weather_state.weather_code
    w_day = weather_state.is_day

    in_temp = sensor_state.inside_temp if sensor_state.inside_temp is not None else "--"
    in_rh = sensor_state.inside_rh if sensor_state.inside_rh is not None else "--"

    # ========= LEFT PANE: Weather & Sensor (x: 0-190) =========
    # Outdoor
    draw.text((10, 0), "OUTDOOR", font=font_med, fill=(0, 0, 0))
    if w_code is not None:
        try:
            icon = get_weather_icon(w_code, w_day, size="2x")
            # Shrink icon slightly so it doesn't overlap larger text
            icon = icon.resize((80, 80), Image.Resampling.LANCZOS)
            img.paste(icon, (110, 10), mask=icon if icon.mode == 'RGBA' else None)
        except Exception:
            pass
            
    draw.text((10, 24), f"{w_temp}°", font=font_huge, fill=(0, 0, 0))
    draw.text((10, 88), f"RH: {w_rh}%", font=font_small, fill=(100, 100, 100))

    # Indoor
    draw.text((10, 116), "INDOOR", font=font_med, fill=(0, 0, 0))
    draw.text((10, 140), f"{in_temp}°", font=font_huge, fill=(0, 0, 0))
    # Place RH below the INDOOR temp but nicely aligned
    draw.text((10, 204), f"RH: {in_rh}%", font=font_small, fill=(100, 100, 100))

    draw.line((210, 10, 210, 290), fill=(0, 0, 0), width=3)

    # Forecast Row (Bottom Left - Space out wider)
    draw.text((10, 236), "FORECAST", font=font_xsmall, fill=(0, 0, 0))
    if hasattr(weather_state, 'hourly_forecast') and weather_state.hourly_forecast:
        x_off = 10
        for idx in [2, 5, 8]:
            if idx < len(weather_state.hourly_forecast):
                fcast = weather_state.hourly_forecast[idx]
                t_str = fcast["time"]
                draw.text((x_off, 256), t_str, font=font_xsmall, fill=(0, 0, 0))
                draw.text((x_off, 276), f"{round(fcast['temp'])}°", font=font_small, fill=(0, 0, 0))
                x_off += 65

    # ========= RIGHT PANE: Window Decision (x: 210-400) =========
    if None in (w_temp, weather_state.current_rh, in_temp):
        is_safe_now = False # Default
        timing_msg = "Wait data"
    else:
        current_resulting_rh = get_resulting_indoor_rh(w_temp, weather_state.current_rh, in_temp)
        is_safe_now = current_resulting_rh < 55.0
        
        flip_time = None
        for fcast in weather_state.hourly_forecast:
            f_rh = get_resulting_indoor_rh(fcast['temp'], fcast['rh'], in_temp)
            f_safe = f_rh < 55.0
            if f_safe != is_safe_now:
                flip_time = fcast['time']
                break
                
        if is_safe_now:
            timing_msg = f"Close\n{flip_time}" if flip_time else "Open\nAll Day"
        else:
            timing_msg = f"Open\n{flip_time}" if flip_time else "Closed\nAll Day"

    # Draw Window Graphic centrally on right pane
    wx, wy = 230, 20
    ww, wh = 150, 150
    
    if is_safe_now:
        # GREEN OPEN WINDOW (Polygons)
        frame_color = (0, 180, 0)
        draw.rectangle((wx, wy, wx+ww, wy+wh), outline=frame_color, width=8)
        # Left swung pane
        draw.polygon([(wx, wy), (wx+35, wy-20), (wx+35, wy+wh+20), (wx, wy+wh)], fill=frame_color)
        # Right swung pane
        draw.polygon([(wx+ww, wy), (wx+ww-35, wy-20), (wx+ww-35, wy+wh+20), (wx+ww, wy+wh)], fill=frame_color)
        
    else:
        # RED CLOSED WINDOW
        frame_color = (220, 0, 0)
        draw.rectangle((wx, wy, wx+ww, wy+wh), fill=frame_color)
        pane_w = (ww - 24) // 2
        pane_h = (wh - 24) // 2
        draw.rectangle((wx+8, wy+8, wx+8+pane_w, wy+8+pane_h), fill=(255, 255, 255))
        draw.rectangle((wx+16+pane_w, wy+8, wx+16+pane_w+pane_w, wy+8+pane_h), fill=(255, 255, 255))
        draw.rectangle((wx+8, wy+16+pane_h, wx+8+pane_w, wy+16+pane_h+pane_h), fill=(255, 255, 255))
        draw.rectangle((wx+16+pane_w, wy+16+pane_h, wx+16+pane_w+pane_w, wy+16+pane_h+pane_h), fill=(255, 255, 255))

    # Add big centered Timing prompt beneath window
    draw.multiline_text((wx+ww//2, 210), timing_msg, fill=(0, 0, 0), font=font_large, align="center", anchor="ma")

    return img
