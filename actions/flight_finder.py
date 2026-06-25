#flight_finder.py
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from config import is_windows, is_mac, is_linux

def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR        = _get_base_dir()


def _get_api_key() -> str:
    from config import get_api_key
    return get_api_key()

_MONTH_MAP: dict[str, int] = {

    "january": 1, "february": 2, "march": 3,     "april": 4,
    "may": 5,     "june": 6,     "july": 7,       "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "ocak": 1,  "şubat": 2,  "mart": 3,   "nisan": 4,
    "mayıs": 5, "haziran": 6, "temmuz": 7, "ağustos": 8,
    "eylül": 9, "ekim": 10,  "kasım": 11, "aralık": 12,
}

_CITY_CODES: dict[str, str] = {}  # dynamic — populated by _geocode_city()


def _geocode_city(city_name: str) -> str:
    """Resolve city name to IATA airport code via Gemini + basic mapping.
    Falls back to uppercase first 3 letters of the city name."""
    name = (city_name or "").strip()
    if not name:
        return ""
    if len(name) == 3 and name.isalpha():
        return name.upper()
    # Quick local lookup first (common cities)
    _known = {
        "delhi": "DEL", "new delhi": "DEL", "mumbai": "BOM", "bangalore": "BLR",
        "bengaluru": "BLR", "chennai": "MAA", "kolkata": "CCU", "hyderabad": "HYD",
        "dubai": "DXB", "abu dhabi": "AUH", "london": "LHR", "new york": "JFK",
        "nyc": "JFK", "los angeles": "LAX", "la": "LAX", "san francisco": "SFO",
        "singapore": "SIN", "bangkok": "BKK", "tokyo": "NRT", "paris": "CDG",
        "sydney": "SYD", "toronto": "YYZ", "istanbul": "IST", "doha": "DOH",
    }
    code = _known.get(name.lower())
    if code:
        return code
    # Try Gemini geocoding for unknown cities
    try:
        from core.llm import ask
        from core.models import PRIMARY
        code = ask(
            f"What is the primary IATA airport code for {name}? "
            "Return ONLY the 3-letter code, nothing else.",
            model=PRIMARY,
        ).strip().upper()[:3]
        if len(code) == 3 and code.isalpha():
            return code
    except Exception:
        pass
    return name.upper()[:3]


def city_to_code(city: str) -> str:
    """Resolve a city name to IATA code dynamically."""
    return _geocode_city(city)


def infer_date_from_text(text: str) -> str | None:
    if not text:
        return None
    lower = text.lower()
    today = datetime.now()
    if "next week" in lower:
        return (today + timedelta(days=7)).strftime("%Y-%m-%d")
    if "this week" in lower:
        return (today + timedelta(days=3)).strftime("%Y-%m-%d")
    if "tomorrow" in lower or "yarın" in lower:
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")
    if "today" in lower or "bugün" in lower:
        return today.strftime("%Y-%m-%d")
    return None


def _parse_date(raw: str) -> str:

    raw   = raw.strip()
    lower = raw.lower()
    today = datetime.now()

    if re.match(r"\d{4}-\d{2}-\d{2}", raw):
        return raw
    for fmt in ("%d/%m/%Y", "%m/%d/%Y", "%d.%m.%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass

    relative = {
        "today": today, "bugün": today,
        "tomorrow": today + timedelta(days=1),
        "yarın":    today + timedelta(days=1),
        "next week": today + timedelta(days=7),
        "this week": today + timedelta(days=3),
    }
    for key, val in relative.items():
        if key in lower:
            return val.strftime("%Y-%m-%d")

    try:
        from core.llm import ask
        from core.models import PRIMARY, RESEARCH

        result = ask(
            f"Today is {today.strftime('%Y-%m-%d')}. "
            f"Convert this date expression to YYYY-MM-DD: '{raw}'. "
            f"Return ONLY the date string, nothing else.",
            model=PRIMARY,
        )
        if re.match(r"\d{4}-\d{2}-\d{2}", result):
            return result
    except Exception as e:
        print(f"[FlightFinder] ⚠️ Gemini date parse failed: {e}")

    for month_name, month_num in _MONTH_MAP.items():
        if month_name in lower:
            day_match = re.search(r"\d{1,2}", raw)
            if day_match:
                day  = int(day_match.group())
                year = today.year if month_num >= today.month else today.year + 1
                return f"{year}-{month_num:02d}-{day:02d}"

    # Default: one week out when user gave a vague timeframe
    print(f"[FlightFinder] ⚠️ Could not parse date '{raw}' — using next week.")
    return (today + timedelta(days=7)).strftime("%Y-%m-%d")

_CABIN_CODE: dict[str, str] = {
    "economy":  "1",
    "premium":  "2",
    "business": "3",
    "first":    "4",
}


def _build_google_flights_url(
    origin:      str,
    destination: str,
    date:        str,
    return_date: str | None = None,
    passengers:  int        = 1,
    cabin:       str        = "economy",
) -> str:
    cabin_code = _CABIN_CODE.get(cabin.lower(), "1")
    base       = "https://www.google.com/travel/flights"

    # Google Flights accepts these query params for pre-filling
    if return_date:
        trip = f"Flights+from+{origin}+to+{destination}+on+{date}+returning+{return_date}"
    else:
        trip = f"Flights+from+{origin}+to+{destination}+on+{date}"

    return (
        f"{base}"
        f"?q={trip.replace(' ', '+')}"
        f"&curr=USD"
        f"&cabin={cabin_code}"
        f"&adults={passengers}"
    )



def _search_flights_browser(
    origin:      str,
    destination: str,
    date:        str,
    return_date: str | None,
    passengers:  int,
    cabin:       str,
) -> tuple[str, str]:
    import time
    from actions.browser_control import browser_control

    url = _build_google_flights_url(
        origin, destination, date, return_date, passengers, cabin
    )

    print(f"[FlightFinder] 🌐 Opening: {url}")
    browser_control({"action": "go_to", "url": url})
    time.sleep(5)

    raw = browser_control({"action": "get_text"})
    return (raw or ""), url

def _parse_flights_with_gemini(
    raw_text:    str,
    origin:      str,
    destination: str,
    date:        str,
) -> list[dict]:
    from core.llm import ask_json

    prompt = (
        f"Extract flight options from {origin} to {destination} on {date} "
        f"from this Google Flights page text:\n\n{raw_text[:12000]}\n\n"
        f"Return a JSON array of up to 5 flights:\n"
        f'[{{"airline":"...","departure":"HH:MM","arrival":"HH:MM",'
        f'"duration":"Xh Ym","stops":0,"price":"...","currency":"USD"}}]\n'
        f"If no flights found, return: []"
    )

    try:
        from core.models import RESEARCH

        flights = ask_json(
            prompt,
            model=RESEARCH,
            system=(
                "You are a flight data extraction expert. "
                "Extract flight information from raw webpage text. "
                "Return ONLY valid JSON — no markdown, no explanation."
            ),
        )
        return flights if isinstance(flights, list) else []
    except Exception as e:
        print(f"[FlightFinder] ⚠️ Gemini parse failed: {e}")
        return []

def _format_spoken(
    flights:     list[dict],
    origin:      str,
    destination: str,
    date:        str,
) -> str:
    if not flights:
        return (
            f"I couldn't find any flights from {origin} to {destination} "
            f"on {date}, sir. The page may not have loaded correctly."
        )

    lines = [f"Here are the top flights from {origin} to {destination} on {date}, sir."]

    for i, f in enumerate(flights[:5], 1):
        airline   = f.get("airline",   "Unknown airline")
        departure = f.get("departure", "--:--")
        arrival   = f.get("arrival",   "--:--")
        duration  = f.get("duration",  "")
        stops     = f.get("stops",     0)
        price     = f.get("price",     "")
        currency  = f.get("currency",  "")

        stop_str  = "non-stop" if stops == 0 else f"{stops} stop{'s' if stops > 1 else ''}"
        price_str = f"{price} {currency}".strip() if price else "price unavailable"
        dur_str   = f", {duration}" if duration else ""

        lines.append(
            f"Option {i}: {airline}, departing {departure}, "
            f"arriving {arrival}{dur_str}, {stop_str}, {price_str}."
        )

    # Cheapest — strip non-digits for comparison
    priced = [f for f in flights if f.get("price")]
    if priced:
        cheapest = min(
            priced,
            key=lambda x: int(re.sub(r"[^\d]", "", str(x["price"])) or "999999"),
        )
        lines.append(
            f"The cheapest option is {cheapest.get('airline')} "
            f"at {cheapest.get('price')} {cheapest.get('currency', '')}."
        )

    return " ".join(lines)


def _format_text_report(
    flights:     list[dict],
    origin:      str,
    destination: str,
    date:        str,
    return_date: str | None,
    page_url:    str,
) -> str:
    lines = [
        "NEO — Flight Search Results",
        "─" * 50,
        f"Route     : {origin} → {destination}",
        f"Date      : {date}",
    ]
    if return_date:
        lines.append(f"Return    : {return_date}")
    lines += [
        f"Searched  : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Source    : {page_url}",
        "─" * 50,
        "",
    ]

    if not flights:
        lines.append("No flights found.")
    else:
        for i, f in enumerate(flights, 1):
            stops    = f.get("stops", 0)
            stop_str = "Non-stop" if stops == 0 else f"{stops} stop(s)"
            lines += [
                f"Flight {i}:",
                f"  Airline   : {f.get('airline',   'N/A')}",
                f"  Departure : {f.get('departure', 'N/A')}",
                f"  Arrival   : {f.get('arrival',   'N/A')}",
                f"  Duration  : {f.get('duration',  'N/A')}",
                f"  Stops     : {stop_str}",
                f"  Price     : {f.get('price', 'N/A')} {f.get('currency', '')}",
                "",
            ]

    return "\n".join(lines)

def _save_to_desktop(content: str, origin: str, destination: str) -> str:
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"flights_{origin}_{destination}_{ts}.txt".replace(" ", "_")
    desktop  = Path.home() / "Desktop"
    desktop.mkdir(parents=True, exist_ok=True)
    filepath = desktop / filename

    filepath.write_text(content, encoding="utf-8")
    print(f"[FlightFinder] 💾 Saved: {filepath}")

    try:
        if is_windows():
            subprocess.Popen(["notepad.exe", str(filepath)])
        elif is_mac():
            subprocess.Popen(["open", "-t", str(filepath)])
        else:
            subprocess.Popen(["xdg-open", str(filepath)])
    except Exception as e:
        print(f"[FlightFinder] ⚠️ Could not open text editor: {e}")

    return str(filepath)


def flight_finder(parameters: dict, player=None, speak=None) -> str:
    params = parameters or {}

    origin      = params.get("origin",      "").strip()
    destination = params.get("destination", "").strip()
    date_raw    = params.get("date",        "").strip()
    return_raw  = (params.get("return_date") or "").strip()
    passengers  = max(1, int(params.get("passengers", 1)))
    cabin       = params.get("cabin", "economy").strip().lower()
    save        = bool(params.get("save", False))

    if not origin or not destination:
        return "Please provide both origin and destination, sir."

    if not date_raw:
        combined = f"{origin} {destination} {params.get('query', '')}"
        date_raw = infer_date_from_text(combined) or "next week"

    # Normalise cabin value
    if cabin not in _CABIN_CODE:
        cabin = "economy"

    date        = _parse_date(date_raw)
    return_date = _parse_date(return_raw) if return_raw else None

    if player:
        player.write_log(f"[FlightFinder] {origin} → {destination} on {date}")

    if speak:
        speak(f"Searching flights from {origin} to {destination} on {date}, sir.")

    print(
        f"[FlightFinder] ▶️ {origin} → {destination} | {date}"
        f"{' → ' + return_date if return_date else ''}"
        f" | {cabin} | {passengers} pax"
    )

    try:
        raw_text, page_url = _search_flights_browser(
            origin, destination, date, return_date, passengers, cabin
        )

        if not raw_text:
            return "Could not retrieve flight data, sir. The page may not have loaded."

        if speak:
            speak("Analysing the results now, sir.")

        flights = _parse_flights_with_gemini(raw_text, origin, destination, date)
        spoken  = _format_spoken(flights, origin, destination, date)

        cheapest_airline = cheapest_price = ""
        priced = [f for f in flights if f.get("price")]
        if priced:
            cheapest = min(
                priced,
                key=lambda x: int(re.sub(r"[^\d]", "", str(x["price"])) or "999999"),
            )
            cheapest_airline = str(cheapest.get("airline", ""))
            cheapest_price = f"{cheapest.get('price', '')} {cheapest.get('currency', '')}".strip()

        try:
            from core.action_context import set_flight

            set_flight(
                origin=origin,
                destination=destination,
                date=date,
                page_url=page_url,
                cheapest_airline=cheapest_airline,
                cheapest_price=cheapest_price,
                passengers=passengers,
            )
        except Exception as e:
            print(f"[FlightFinder] ⚠️ action_context: {e}")

        if speak:
            speak(spoken)

        result = spoken
        result += (
            f" Search page: {page_url}."
            f" Say 'open the link' or 'goibibo link' to open the booking page."
        )

        if save and flights:
            report     = _format_text_report(flights, origin, destination, date, return_date, page_url)
            saved_path = _save_to_desktop(report, origin, destination)
            result    += f" Results saved to Desktop: {saved_path}"

        return result

    except Exception as e:
        print(f"[FlightFinder] ❌ {e}")
        return f"Flight search failed, sir: {e}"
