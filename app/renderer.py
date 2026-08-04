from PIL import Image, ImageDraw, ImageFont
import os
import time
from datetime import datetime, date, timedelta
from humidity_calc import get_resulting_indoor_rh
from icons import get_weather_icon
from mqtt_client import (
    ZONE_LABELS,
    UPSTAIRS,
    DOWNSTAIRS,
    CONSERVATORY,
    STALE_AFTER,
)

FONT_PATH = os.environ.get("FONT_PATH", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
FONT_BOLD_PATH = os.environ.get("FONT_BOLD_PATH", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
TARGET_HUMIDITY = float(os.environ.get("TARGET_HUMIDITY", 55.0))

BLACK = (0, 0, 0)
GREY = (90, 90, 90)
LIGHT_GREY = (160, 160, 160)
RED = (220, 0, 0)
WHITE = (255, 255, 255)

# Band boundaries on the 400x300 panel
OUTDOOR_TOP = 0
SPLIT_Y = 120
UPSTAIRS_TOP = 124
ZONE_RULE_Y = 236
SECONDARY_TOP = 240
FOOTER_Y = 286

# Both secondary zones share the strip, split down the middle
SECONDARY_SPLIT_X = 200


def _fmt_rh(value):
    """Whole-percent humidity: the decimal place is noise at a glance."""
    if value is None:
        return "RH --%"
    try:
        return f"RH {round(float(value))}%"
    except (TypeError, ValueError):
        return "RH --%"


def _fmt_reading(reading):
    """A zone's values as display text, or placeholders when missing/stale."""
    if reading is None or reading.is_stale:
        return "--°", "RH --%"
    return f"{reading.temp}°", _fmt_rh(reading.rh)


def _fmt_flip(iso_time):
    """
    Format the hour at which the window verdict changes. Times beyond today get
    a weekday prefix so "06:00" can't be misread as this morning.
    """
    try:
        dt = datetime.fromisoformat(iso_time)
    except (TypeError, ValueError):
        return iso_time

    if dt.date() == date.today():
        return dt.strftime("%H:%M")
    if dt.date() == date.today() + timedelta(days=1):
        return dt.strftime("%a %H:%M")
    return dt.strftime("%a %H:%M")


def _window_verdict(weather_state, inside_temp):
    """
    Decide whether opening up would dry the house out, and when that flips.

    Returns (is_safe_now, message). The message deliberately omits open/closed
    wording because the window glyph drawn beside it already carries that, and
    the full phrasing does not fit the panel width.
    """
    w_temp = weather_state.current_temp
    w_rh = weather_state.current_rh

    if None in (w_temp, w_rh, inside_temp):
        return False, "no data"

    try:
        current_resulting_rh = get_resulting_indoor_rh(w_temp, w_rh, inside_temp)
    except (TypeError, ValueError):
        return False, "no data"

    is_safe_now = current_resulting_rh < TARGET_HUMIDITY

    flip_time = None
    for fcast in getattr(weather_state, "hourly_forecast", []) or []:
        try:
            f_rh = get_resulting_indoor_rh(fcast["temp"], fcast["rh"], inside_temp)
        except (TypeError, ValueError, KeyError):
            continue

        if (f_rh < TARGET_HUMIDITY) != is_safe_now:
            flip_time = fcast.get("time", "--:--")
            break

    if flip_time:
        return is_safe_now, f"until {_fmt_flip(flip_time)}"
    return is_safe_now, "all day"


def _draw_window(draw, is_open):
    """
    Open window in black, closed window in red, on the Upstairs band.

    Returns a fixed bottom edge covering the open state's swung panes, which
    overhang the frame. Keeping it fixed stops the caption below from shifting
    position every time the verdict changes.
    """
    wx, wy = 310 - 40, 130
    ww, wh = 80, 68
    pane_overhang = 12

    if is_open:
        draw.rectangle((wx, wy, wx + ww, wy + wh), outline=BLACK, width=6)
        # Left swung pane
        draw.polygon(
            [(wx, wy), (wx + 20, wy - pane_overhang), (wx + 20, wy + wh + pane_overhang), (wx, wy + wh)],
            fill=BLACK,
        )
        # Right swung pane
        draw.polygon(
            [
                (wx + ww, wy),
                (wx + ww - 20, wy - pane_overhang),
                (wx + ww - 20, wy + wh + pane_overhang),
                (wx + ww, wy + wh),
            ],
            fill=BLACK,
        )
    else:
        draw.rectangle((wx, wy, wx + ww, wy + wh), fill=RED)
        pane_w = (ww - 16) // 2
        pane_h = (wh - 16) // 2
        draw.rectangle((wx + 6, wy + 6, wx + 6 + pane_w, wy + 6 + pane_h), fill=WHITE)
        draw.rectangle((wx + 10 + pane_w, wy + 6, wx + 10 + pane_w + pane_w, wy + 6 + pane_h), fill=WHITE)
        draw.rectangle((wx + 6, wy + 10 + pane_h, wx + 6 + pane_w, wy + 10 + pane_h + pane_h), fill=WHITE)
        draw.rectangle(
            (wx + 10 + pane_w, wy + 10 + pane_h, wx + 10 + pane_w + pane_w, wy + 10 + pane_h + pane_h),
            fill=WHITE,
        )

    return wy + wh + pane_overhang


def _is_anything_stale(weather_state, zones):
    """
    True when a data source that was working has stopped. Zones that have never
    reported are ignored, so an uninstalled sensor doesn't raise a false alarm.
    """
    if time.time() - weather_state.last_update > STALE_AFTER:
        return True
    for reading in zones.values():
        if reading is not None and reading.last_update > 0 and reading.is_stale:
            return True
    return False


def render_dashboard(weather_state, sensor_state):
    # Create 400x300 image (monochrome compatible colors)
    img = Image.new("RGB", (400, 300), color=WHITE)
    draw = ImageDraw.Draw(img)

    try:
        font_huge = ImageFont.truetype(FONT_BOLD_PATH, 48)
        font_big = ImageFont.truetype(FONT_BOLD_PATH, 44)
        font_med = ImageFont.truetype(FONT_BOLD_PATH, 24)
        font_small = ImageFont.truetype(FONT_PATH, 20)
        font_zone = ImageFont.truetype(FONT_BOLD_PATH, 14)
        font_zone_val = ImageFont.truetype(FONT_PATH, 20)
        font_tiny = ImageFont.truetype(FONT_PATH, 12)
    except Exception:
        font_huge = font_big = font_med = font_small = ImageFont.load_default()
        font_zone = font_zone_val = font_tiny = font_small

    zones = sensor_state.zones()
    upstairs = zones.get(UPSTAIRS)

    w_temp = weather_state.current_temp if weather_state.current_temp is not None else "--"

    # ========= TOP BAND: Outdoor =========
    draw.text((12, OUTDOOR_TOP + 6), "OUTDOOR", font=font_med, fill=BLACK)
    draw.text((12, OUTDOOR_TOP + 30), f"{w_temp}°", font=font_big, fill=BLACK)
    draw.text((18, OUTDOOR_TOP + 86), _fmt_rh(weather_state.current_rh), font=font_small, fill=GREY)

    if weather_state.weather_code is not None:
        try:
            icon = get_weather_icon(weather_state.weather_code, weather_state.is_day, size="4x")
            icon = icon.resize((110, 110), Image.Resampling.LANCZOS)
            img.paste(icon, (310 - 55, OUTDOOR_TOP + 4), mask=icon if icon.mode == "RGBA" else None)
        except Exception:
            pass

    draw.line((0, SPLIT_Y, 400, SPLIT_Y), fill=RED, width=3)

    # ========= UPSTAIRS: drives the window decision =========
    # The dehumidifier lives upstairs, so that zone alone decides the verdict.
    inside_temp = upstairs.temp if (upstairs and not upstairs.is_stale) else None
    is_safe_now, timing_msg = _window_verdict(weather_state, inside_temp)

    up_temp, up_rh = _fmt_reading(upstairs)
    draw.text((12, UPSTAIRS_TOP + 2), ZONE_LABELS[UPSTAIRS], font=font_med, fill=BLACK)
    draw.text((12, UPSTAIRS_TOP + 26), up_temp, font=font_huge, fill=BLACK)
    draw.text((18, UPSTAIRS_TOP + 82), up_rh, font=font_small, fill=GREY)

    window_bottom = _draw_window(draw, is_safe_now)
    draw.text((310, window_bottom + 4), timing_msg, font=font_small, fill=BLACK, anchor="ma")

    # ========= SECONDARY STRIP: reported for interest only =========
    draw.line((0, ZONE_RULE_Y, 400, ZONE_RULE_Y), fill=LIGHT_GREY, width=1)
    draw.line(
        (SECONDARY_SPLIT_X, SECONDARY_TOP, SECONDARY_SPLIT_X, FOOTER_Y - 4),
        fill=LIGHT_GREY,
        width=1,
    )

    for x, slot in ((12, DOWNSTAIRS), (SECONDARY_SPLIT_X + 12, CONSERVATORY)):
        temp_txt, rh_txt = _fmt_reading(zones.get(slot))
        draw.text((x, SECONDARY_TOP), ZONE_LABELS[slot], font=font_zone, fill=BLACK)
        draw.text((x, SECONDARY_TOP + 16), f"{temp_txt} {rh_txt}", font=font_zone_val, fill=GREY)

    # ========= FOOTER: render clock, so a frozen screen is obvious =========
    stamp_colour = RED if _is_anything_stale(weather_state, zones) else LIGHT_GREY
    draw.text(
        (392, FOOTER_Y),
        datetime.now().strftime("%H:%M"),
        font=font_tiny,
        fill=stamp_colour,
        anchor="ra",
    )

    return img
