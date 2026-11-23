"""Calendar display for a smart TV.

A small Flask app that reads a Google Calendar feed and renders a
big, TV-friendly dashboard: today's events, the week ahead, a live
clock, and Atlanta weather. The page auto-refreshes every 5 minutes.

Data source: the calendar's secret iCal address, set as the
CALENDAR_ICS_URL environment variable. Without it the app runs in
demo mode with sample events so the design can be previewed.
"""

import os
import time
from datetime import datetime, timedelta, date, time as dtime

import requests
from flask import Flask, render_template

TZ_NAME = "America/New_York"

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo(TZ_NAME)
except Exception:  # pragma: no cover
    TZ = None

app = Flask(__name__)

_ics_cache = {"data": None, "fetched_at": 0}
_weather_cache = {"data": None, "fetched_at": 0}

ICS_TTL_SECONDS = 300
WEATHER_TTL_SECONDS = 900


def _fetch_ics_bytes():
    """Return raw ICS bytes, using a 5-minute in-memory cache."""
    now = time.time()
    if _ics_cache["data"] is not None and now - _ics_cache["fetched_at"] < ICS_TTL_SECONDS:
        return _ics_cache["data"], None
    url = os.environ.get("CALENDAR_ICS_URL", "").strip()
    if not url:
        return None, None
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        _ics_cache["data"] = resp.content
        _ics_cache["fetched_at"] = now
        return resp.content, None
    except Exception as exc:  # noqa: BLE001 - surface as a banner, keep rendering
        if _ics_cache["data"] is not None:
            return _ics_cache["data"], f"Calendar feed failed to refresh ({exc}); showing cached events."
        return None, f"Could not load the calendar feed: {exc}"


def _to_local(value):
    """Normalize an ICS date/datetime to an aware datetime in local time.

    Returns (datetime, is_all_day).
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            # Google normally stamps UTC; treat a naive value as UTC.
            from datetime import timezone

            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(TZ), False
    if isinstance(value, date):
        return datetime.combine(value, dtime.min, tzinfo=TZ), True
    return None, False


def _parse_events(ics_bytes):
    from icalendar import Calendar
    import recurring_ical_events

    cal = Calendar.from_ical(ics_bytes)
    now = datetime.now(TZ)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=7)
    raw = recurring_ical_events.of(cal).between(start, end)
    events = []
    for ev in raw:
        dtstart = ev.get("DTSTART")
        dtend = ev.get("DTEND")
        if dtstart is None:
            continue
        start_dt, all_day = _to_local(dtstart.dt)
        if start_dt is None:
            continue
        if dtend is not None:
            end_dt, _ = _to_local(dtend.dt)
        else:
            end_dt = start_dt + timedelta(hours=1)
        # recurring-ical-events returns all-day end dates as exclusive;
        # keep the displayed end as-is, it is only used for "now" checks.
        events.append(
            {
                "title": str(ev.get("SUMMARY", "(No title)")),
                "start": start_dt,
                "end": end_dt,
                "all_day": all_day,
                "location": str(ev.get("LOCATION", "")) if ev.get("LOCATION") else "",
            }
        )
    events.sort(key=lambda e: (e["start"], e["title"]))
    return events


def _demo_events():
    """Sample events relative to today, so the design can be previewed."""
    now = datetime.now(TZ)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    demo = [
        ("Morning briefing", today + timedelta(hours=7, minutes=24), today + timedelta(hours=7, minutes=30), False, ""),
        ("Vidalia Barking Hound drop-off", today + timedelta(hours=12), today + timedelta(hours=12, minutes=30), False, "Barking Hound Village Decatur"),
        ("ASO Chorus rehearsal", today + timedelta(hours=19), today + timedelta(hours=22), False, "Goizueta Stage"),
        ("Thanksgiving", today + timedelta(days=3), today + timedelta(days=4), True, ""),
        ("Festival Singers: Holiday Memories", today + timedelta(days=12, hours=16), today + timedelta(days=12, hours=17, minutes=30), False, "Saint Mark UMC"),
        ("Magnificat", today + timedelta(days=20, hours=10), today + timedelta(days=20, hours=11, minutes=30), False, "Saint Mark UMC"),
    ]
    return [
        {"title": t, "start": s, "end": e, "all_day": a, "location": loc}
        for t, s, e, a, loc in demo
    ]


def _fetch_weather():
    """Current conditions + today's high/low for Atlanta via Open-Meteo (no key)."""
    now = time.time()
    if _weather_cache["data"] is not None and now - _weather_cache["fetched_at"] < WEATHER_TTL_SECONDS:
        return _weather_cache["data"]
    url = (
        "https://api.open-meteo.com/v1/forecast"
        "?latitude=33.749&longitude=-84.388"
        "&current=temperature_2m,weather_code"
        "&daily=temperature_2m_max,temperature_2m_min"
        "&temperature_unit=fahrenheit&timezone=America%2FNew_York&forecast_days=1"
    )
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        payload = resp.json()
        current = payload.get("current", {})
        daily = payload.get("daily", {})
        weather = {
            "temp": round(current.get("temperature_2m")) if current.get("temperature_2m") is not None else None,
            "high": round(daily["temperature_2m_max"][0]) if daily.get("temperature_2m_max") else None,
            "low": round(daily["temperature_2m_min"][0]) if daily.get("temperature_2m_min") else None,
            "code": current.get("weather_code"),
        }
        _weather_cache["data"] = weather
        _weather_cache["fetched_at"] = now
        return weather
    except Exception:  # noqa: BLE001 - weather is a nice-to-have
        return None


WEATHER_LABELS = {
    0: "Clear",
    1: "Mostly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Foggy",
    48: "Foggy",
    51: "Light drizzle",
    53: "Drizzle",
    55: "Drizzle",
    61: "Light rain",
    63: "Rain",
    65: "Heavy rain",
    71: "Light snow",
    73: "Snow",
    75: "Heavy snow",
    80: "Rain showers",
    81: "Rain showers",
    82: "Heavy showers",
    85: "Snow showers",
    86: "Snow showers",
    95: "Thunderstorms",
    96: "Thunderstorms",
    99: "Thunderstorms",
}


@app.route("/")
def index():
    now = datetime.now(TZ)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    demo_mode = not os.environ.get("CALENDAR_ICS_URL", "").strip()
    error = None
    if demo_mode:
        events = _demo_events()
    else:
        ics_bytes, error = _fetch_ics_bytes()
        if ics_bytes is None:
            events = []
        else:
            try:
                events = _parse_events(ics_bytes)
            except Exception as exc:  # noqa: BLE001 - keep the page up
                events = []
                error = f"Could not read the calendar feed: {exc}"

    # Group events by day for the next 7 days.
    days = []
    for offset in range(7):
        day_start = today + timedelta(days=offset)
        day_end = day_start + timedelta(days=1)
        day_events = [e for e in events if day_start <= e["start"] < day_end]
        # All-day events spanning multiple days: include if the day falls
        # within their range.
        for e in events:
            if e["all_day"] and e["start"] < day_start < e["end"] and e not in day_events:
                day_events.append(e)
        day_events.sort(key=lambda e: (e["start"], e["title"]))
        days.append({"date": day_start, "events": day_events})

    today_events = days[0]["events"]
    upcoming = None
    for e in today_events:
        if e["end"] > now:
            upcoming = e
            break

    weather = _fetch_weather()
    if weather is not None and weather.get("code") is not None:
        weather["label"] = WEATHER_LABELS.get(weather["code"], "")
    else:
        if weather is not None:
            weather["label"] = ""

    return render_template(
        "index.html",
        now=now,
        today=today,
        days=days,
        today_events=today_events,
        upcoming=upcoming,
        weather=weather,
        demo_mode=demo_mode,
        error=error,
    )


@app.route("/health")
def health():
    return "ok", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
