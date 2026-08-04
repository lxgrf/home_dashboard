import time
from datetime import date, timedelta

import pytest

import renderer
from mqtt_client import SensorState, UPSTAIRS, DOWNSTAIRS, CONSERVATORY
from renderer import render_dashboard, _window_verdict, _fmt_flip, _is_anything_stale


class FakeWeather:
    def __init__(self, temp=14.0, rh=82.0, forecast=None, age=0):
        self.current_temp = temp
        self.current_rh = rh
        self.weather_code = 3
        self.is_day = 1
        self.daily_max = 18.0
        self.daily_min = 9.0
        self.hourly_forecast = forecast or []
        self.last_update = time.time() - age


def _hours(*specs):
    """Build hourly forecast entries from (hour, temp, rh) triples."""
    today = date.today().isoformat()
    return [{"time": f"{today}T{h:02d}:00", "temp": t, "rh": r} for h, t, r in specs]


@pytest.fixture
def state():
    s = SensorState()
    s.update("upstairs", {"temperature": 19.4, "humidity": 58.0})
    s.update("downstairs", {"temperature": 20.1, "humidity": 55.0})
    s.update("conservatory", {"temperature": 24.3, "humidity": 48.0})
    return s


# --- the verdict -------------------------------------------------------------

def test_dry_outside_air_means_open():
    # Cold and dry: warming it indoors drops the RH well below target
    is_safe, msg = _window_verdict(FakeWeather(temp=5.0, rh=50.0), 19.4)
    assert is_safe
    assert msg == "all day"


def test_muggy_outside_air_means_closed():
    is_safe, msg = _window_verdict(FakeWeather(temp=20.0, rh=95.0), 19.4)
    assert not is_safe


def test_missing_indoor_temp_is_not_a_guess():
    """A dead upstairs sensor must not produce a confident verdict."""
    is_safe, msg = _window_verdict(FakeWeather(), None)
    assert not is_safe
    assert msg == "no data"


def test_missing_weather_is_not_a_guess():
    is_safe, msg = _window_verdict(FakeWeather(temp=None, rh=None), 19.4)
    assert not is_safe
    assert msg == "no data"


def test_flip_time_is_reported():
    # Dry now, turning muggy at 15:00
    weather = FakeWeather(temp=5.0, rh=50.0, forecast=_hours((14, 5.0, 50.0), (15, 20.0, 98.0)))
    is_safe, msg = _window_verdict(weather, 19.4)
    assert is_safe
    assert msg == "until 15:00"


def test_forecast_entries_with_holes_are_skipped():
    weather = FakeWeather(temp=5.0, rh=50.0, forecast=[{"time": "x"}, {"temp": None, "rh": None}])
    is_safe, msg = _window_verdict(weather, 19.4)
    assert is_safe
    assert msg == "all day"


# --- flip time formatting ----------------------------------------------------

def test_today_shows_bare_time():
    assert _fmt_flip(f"{date.today().isoformat()}T14:00") == "14:00"


def test_tomorrow_is_distinguishable_from_today():
    tomorrow = date.today() + timedelta(days=1)
    formatted = _fmt_flip(f"{tomorrow.isoformat()}T06:00")
    assert formatted == tomorrow.strftime("%a 06:00")
    assert formatted != "06:00"


def test_unparseable_time_passes_through():
    assert _fmt_flip("--:--") == "--:--"


# --- staleness signalling ----------------------------------------------------

def test_nothing_stale_when_all_fresh(state):
    assert not _is_anything_stale(FakeWeather(), state.zones())


def test_stale_weather_is_flagged(state):
    assert _is_anything_stale(FakeWeather(age=99999), state.zones())


def test_uninstalled_zone_does_not_raise_a_false_alarm():
    """A zone with no sensor yet is expected, not a fault."""
    s = SensorState()
    s.update("upstairs", {"temperature": 19.4, "humidity": 58.0})
    zones = s.zones()
    assert zones[CONSERVATORY] is None
    assert not _is_anything_stale(FakeWeather(), zones)


def test_sensor_that_stopped_reporting_is_flagged(state, monkeypatch):
    monkeypatch.setattr(renderer, "STALE_AFTER", 60)
    import mqtt_client
    monkeypatch.setattr(mqtt_client, "STALE_AFTER", 60)
    state.sensors["conservatory"].last_update = time.time() - 600
    assert _is_anything_stale(FakeWeather(), state.zones())


# --- rendering ---------------------------------------------------------------

def test_renders_at_panel_resolution(state):
    img = render_dashboard(FakeWeather(), state)
    assert img.size == (400, 300)


def test_renders_with_no_sensors_at_all():
    img = render_dashboard(FakeWeather(), SensorState())
    assert img.size == (400, 300)


def test_renders_with_no_weather_yet(state):
    img = render_dashboard(FakeWeather(temp=None, rh=None), state)
    assert img.size == (400, 300)


def test_renders_with_only_upstairs_installed():
    s = SensorState()
    s.update("upstairs", {"temperature": 19.4, "humidity": 58.0})
    assert render_dashboard(FakeWeather(), s).size == (400, 300)


def test_introduces_no_colour_the_panel_cannot_show(state):
    """
    The Inky wHAT has black, white and red ink, and dithers greys onto them.
    Antialiasing legitimately produces greys and red/white blends; anything
    with a green or blue cast would dither unpredictably, so guard that.
    """
    img = render_dashboard(FakeWeather(), state)
    for _, (r, g, b) in img.getcolors(maxcolors=100000):
        assert g == b and r >= g, f"non red/grey colour on the panel: {(r, g, b)}"
