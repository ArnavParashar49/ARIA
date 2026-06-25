"""Speak weather aloud via Open-Meteo — no browser, no LLM search."""

from __future__ import annotations

import requests
from urllib.parse import quote_plus

_WMO: dict[int, str] = {
    0: "clear",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "foggy",
    48: "foggy",
    51: "light drizzle",
    53: "drizzle",
    55: "heavy drizzle",
    61: "light rain",
    63: "rain",
    65: "heavy rain",
    71: "snow",
    73: "snow",
    75: "heavy snow",
    80: "rain showers",
    81: "rain showers",
    82: "heavy rain showers",
    95: "thunderstorms",
    96: "thunderstorms with hail",
    99: "thunderstorms with hail",
}


def _describe(code: int | None) -> str:
    if code is None:
        return "unknown conditions"
    return _WMO.get(int(code), "mixed conditions")


def resolve_city(city: str | None) -> str | None:
    """User city arg → env/config default → None."""
    explicit = (city or "").strip()
    if explicit:
        return explicit
    from config import get_default_location

    return get_default_location()


def fetch_weather(city: str, when: str = "today") -> str:
    """Fetch weather from Open-Meteo (geocoding + forecast). Returns spoken text."""
    when = (when or "today").strip().lower()
    day_index = 1 if when in {"tomorrow", "tmrw"} else 0

    geo_url = (
        "https://geocoding-api.open-meteo.com/v1/search"
        f"?name={quote_plus(city)}&count=1&language=en&format=json"
    )
    geo_res = requests.get(geo_url, timeout=6).json()
    results = geo_res.get("results") or []
    if not results:
        return f"I couldn't find a city called {city}."

    place = results[0]
    lat = place["latitude"]
    lon = place["longitude"]
    name = place.get("name", city)
    admin = place.get("admin1") or place.get("country") or ""
    label = f"{name}, {admin}".strip(", ")

    forecast_url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,apparent_temperature,relative_humidity_2m,"
        "weather_code,wind_speed_10m"
        "&daily=temperature_2m_max,temperature_2m_min,weather_code"
        "&temperature_unit=celsius&wind_speed_unit=kmh&forecast_days=2"
    )
    w_res = requests.get(forecast_url, timeout=6).json()
    curr = w_res.get("current") or {}
    daily = w_res.get("daily") or {}

    temp = curr.get("temperature_2m")
    feels = curr.get("apparent_temperature")
    humidity = curr.get("relative_humidity_2m")
    wind = curr.get("wind_speed_10m")
    condition = _describe(curr.get("weather_code"))

    highs = daily.get("temperature_2m_max") or []
    lows = daily.get("temperature_2m_min") or []
    hi = highs[day_index] if len(highs) > day_index else None
    lo = lows[day_index] if len(lows) > day_index else None

    if when in {"tomorrow", "tmrw"} and hi is not None:
        tmrw_cond = _describe(
            (daily.get("weather_code") or [None])[day_index]
        )
        return (
            f"Tomorrow in {label}: {tmrw_cond}, high {round(hi)}°C"
            f"{f', low {round(lo)}°C' if lo is not None else ''}."
        )

    parts = [f"In {label} it's {round(temp)}°C and {condition}" if temp is not None
             else f"In {label} it's {condition}"]
    if feels is not None and temp is not None and abs(feels - temp) >= 2:
        parts.append(f"feels like {round(feels)}°C")
    if hi is not None and lo is not None:
        parts.append(f"high {round(hi)}°C, low {round(lo)}°C today")
    if wind is not None:
        parts.append(f"wind {round(wind)} km/h")
    if humidity is not None:
        parts.append(f"humidity {round(humidity)}%")

    text = ", ".join(parts) + "."
    return text[0].upper() + text[1:]


def weather_action(
    parameters: dict,
    player=None,
    session_memory=None,
) -> str:
    from config import get_default_location, set_default_location

    city = resolve_city(parameters.get("city"))
    when = parameters.get("time", "today")

    if not city:
        msg = (
            "Which city should I check? "
            "You can set a default in .env with NEO_DEFAULT_LOCATION=Your City."
        )
        _log(msg, player)
        return msg

    explicit = (parameters.get("city") or "").strip()
    if explicit:
        try:
            set_default_location(explicit)
        except Exception:
            pass
    elif not get_default_location():
        try:
            set_default_location(city)
        except Exception:
            pass

    try:
        msg = fetch_weather(city, when)
    except Exception as e:
        msg = f"I couldn't get the weather for {city} right now."
        print(f"[Weather] ❌ {e}")

    _log(msg, player)

    if session_memory:
        try:
            session_memory.set_last_search(query=f"weather {city}", response=msg)
        except Exception:
            pass

    return msg


def _log(message: str, player=None) -> None:
    print(f"[Weather] {message}")
    if player:
        try:
            player.write_log(f"Neo: {message}")
        except Exception:
            pass
