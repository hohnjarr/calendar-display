# Calendar Display

A MangoDisplay-style dashboard for a smart TV: shows today's Google
Calendar events, the week ahead, a live clock, and Atlanta weather, in
big type on a dark background. The page refreshes itself every
5 minutes, so it can stay open on the TV all day.

## How it works

- The app reads a Google Calendar feed (iCal format) from the
  `CALENDAR_ICS_URL` environment variable and renders it. No database,
  no OAuth setup, no Google Cloud project needed.
- Weather comes from Open-Meteo (free, no API key).
- Without `CALENDAR_ICS_URL` set, the app runs in demo mode with
  sample events so the design can be previewed.

## Setup

### 1. Create the GitHub repo

Create an **empty** repo named `calendar-display` on GitHub
(the GitHub app cannot create repos, so this is a manual step).
Then tell Milo and he will push this code to it.

### 2. Deploy on Render

- In the Render dashboard, **New +** → **Web Service** → connect the
  `calendar-display` repo. Or use the Blueprint: **New +** →
  **Blueprint** → connect the repo (the `render.yaml` in this repo
  defines the service).
- Free tier is fine. No database is needed.
- Python environment, build command `pip install -r requirements.txt`,
  start command `gunicorn app:app` (both already in `render.yaml`).

### 3. Connect your calendar (your step, private)

Your calendar link is a secret URL, so add it yourself in Render and
it never passes through chat or Milo:

1. Open [Google Calendar settings](https://calendar.google.com/calendar/u/0/r/settings)
   → pick your calendar under "Settings for my calendars".
2. Scroll to **"Secret address in iCal format"** and copy that URL.
3. In Render, open the service → **Environment** → add
   `CALENDAR_ICS_URL` with that URL as the value → save (the service
   redeploys).
4. Open the Render URL and your real events should appear. If the
   page still shows the demo banner, the variable is not set yet.

To stop sharing, change the secret address in Google Calendar
settings (that invalidates the old URL) or remove the variable in
Render.

## 4. Put it on the TV

Open the Render URL in the TV's built-in browser (Samsung, LG, and
most others have one), or cast the page from your phone. The page is
plain HTML/CSS, so it works in any browser, and it reloads itself
every 5 minutes.

## Local test

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# demo mode (no calendar link):
PORT=5000 .venv/bin/python app.py
# with your calendar:
CALENDAR_ICS_URL="<secret ical url>" PORT=5000 .venv/bin/python app.py
```

## Status

- Built and tested locally 2026-11-23 (demo mode and a test ICS feed
  with timed, all-day, and recurring events all render correctly).
- Awaiting: GitHub repo creation, push, Render deploy, calendar link.
