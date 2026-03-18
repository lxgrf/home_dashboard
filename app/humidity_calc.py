import math

def calculate_absolute_humidity(temp_c: float, rh_percent: float) -> float:
    """
    Calculate Absolute Humidity (g/m^3) given Temperature (C) and Relative Humidity (%).
    Uses the Magnus-Tetens approximation.
    """
    # Saturation vapor pressure in hPa
    es = 6.112 * math.exp((17.67 * temp_c) / (temp_c + 243.5))
    # Actual vapor pressure
    e = es * (rh_percent / 100.0)
    # Absolute humidity in g/m^3
    ah = (e * 2.1674 * 1000) / (temp_c + 273.15)
    return ah

def calculate_resulting_rh(ah: float, target_temp_c: float) -> float:
    """
    Calculate resulting Relative Humidity (%) if air with a given Absolute Humidity
    is brought to a target Temperature (C).
    """
    # Calculate actual vapor pressure from absolute humidity
    e = (ah * (target_temp_c + 273.15)) / (2.1674 * 1000)
    # Saturation vapor pressure at target temperature
    es = 6.112 * math.exp((17.67 * target_temp_c) / (target_temp_c + 243.5))
    
    # Resulting relative humidity
    rh = (e / es) * 100.0
    return max(0.0, min(100.0, rh))

def window_open_reduces_rh(outside_temp: float, outside_rh: float, inside_temp: float, target_rh_threshold: float = 55.0) -> bool:
    """
    Determines if bringing outside air inside and letting it reach inside_temp
    will result in a relative humidity below the target threshold.
    """
    outside_ah = calculate_absolute_humidity(outside_temp, outside_rh)
    resulting_indoor_rh = calculate_resulting_rh(outside_ah, inside_temp)
    return resulting_indoor_rh < target_rh_threshold

def get_resulting_indoor_rh(outside_temp: float, outside_rh: float, inside_temp: float) -> float:
    outside_ah = calculate_absolute_humidity(outside_temp, outside_rh)
    return calculate_resulting_rh(outside_ah, inside_temp)
