import time

import pytest

import mqtt_client
from mqtt_client import (
    SensorState,
    device_from_topic,
    UPSTAIRS,
    DOWNSTAIRS,
    CONSERVATORY,
)


READING = {"temperature": 20.1, "humidity": 55.0}


@pytest.fixture
def state():
    return SensorState()


# --- topic parsing -----------------------------------------------------------

@pytest.mark.parametrize("topic,expected", [
    ("zigbee2mqtt/upstairs", "upstairs"),
    ("zigbee2mqtt/0x00158d0001234567", "0x00158d0001234567"),
    # Bridge traffic and sub-topics carry payloads we must not read as sensors
    ("zigbee2mqtt/bridge", None),
    ("zigbee2mqtt/bridge/devices", None),
    ("zigbee2mqtt/upstairs/availability", None),
    ("zigbee2mqtt/upstairs/set", None),
    ("zigbee2mqtt", None),
    ("othertopic/upstairs", None),
])
def test_device_from_topic(topic, expected):
    assert device_from_topic(topic) == expected


# --- zone resolution ---------------------------------------------------------

def test_zones_resolve_by_friendly_name(state):
    state.update("upstairs", {"temperature": 19.4, "humidity": 58.0})
    state.update("conservatory", {"temperature": 24.3, "humidity": 48.0})

    zones = state.zones()
    assert zones[UPSTAIRS].temp == 19.4
    assert zones[CONSERVATORY].rh == 48.0
    # Not installed yet, and that must not error
    assert zones[DOWNSTAIRS] is None


def test_single_unnamed_sensor_falls_back_to_upstairs(state):
    """The pre-existing sensor is still on its IEEE name; keep it working."""
    state.update("0x00158d0001234567", READING)

    assert state.zones()[UPSTAIRS].name == "0x00158d0001234567"
    assert state.inside_temp == 20.1


def test_fallback_stops_once_a_second_sensor_appears(state):
    """With two unnamed sensors we cannot guess, so refuse to."""
    state.update("0x00158d0001234567", READING)
    state.update("0x00158d0007654321", READING)

    assert state.zones()[UPSTAIRS] is None


def test_explicit_config_disables_the_fallback(state, monkeypatch):
    monkeypatch.setitem(mqtt_client.ZONE_SOURCES, UPSTAIRS, "0xdeadbeef")
    monkeypatch.setitem(mqtt_client.ZONE_CONFIGURED, UPSTAIRS, True)

    state.update("0x00158d0001234567", READING)
    assert state.zones()[UPSTAIRS] is None

    state.update("0xdeadbeef", READING)
    assert state.zones()[UPSTAIRS].name == "0xdeadbeef"


def test_blank_env_is_treated_as_unset(monkeypatch):
    """docker-compose passes absent vars through as empty strings."""
    monkeypatch.setenv("ZONE_UPSTAIRS", "")
    import importlib
    reloaded = importlib.reload(mqtt_client)
    try:
        assert reloaded.ZONE_SOURCES[UPSTAIRS] == "upstairs"
        assert reloaded.ZONE_CONFIGURED[UPSTAIRS] is False
    finally:
        monkeypatch.undo()
        importlib.reload(mqtt_client)


# --- staleness ---------------------------------------------------------------

def test_fresh_reading_is_not_stale(state):
    reading = state.update("upstairs", READING)
    assert not reading.is_stale


def test_reading_goes_stale(state, monkeypatch):
    reading = state.update("upstairs", READING)
    monkeypatch.setattr(mqtt_client, "STALE_AFTER", 60)
    reading.last_update = time.time() - 120
    assert reading.is_stale


def test_never_seen_reading_is_stale():
    assert mqtt_client.ZoneReading("nobody").is_stale
