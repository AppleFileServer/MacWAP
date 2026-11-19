"""Plain-text SMS command service.

A fallback for the WAP service: the phone texts a short command to the
Pi's SIM and gets one or two ordinary texts back. It works on an ordinary
network (no WAP bearer), so it keeps going where WAP-over-SMS cannot, and
abroad.

It shares its data with the WAP decks. Weather and news come from the same
files wapfetch.py prepares; calories and cash are the same journals
wapapp.py uses, so an entry made by text shows up on the WAP side too.

Commands (the first word; case does not matter):
    w                weather for the home place
    w Berlin         weather for any town, looked up as you ask
                     (w St Helens AU: a country code picks between
                     towns of the same name)
    n                the latest news headlines
    t   (or blank)   today: time, weather, calories so far
    c                calories today        c 250   add 250
                                            c undo  remove the last today
    m                cash: total and last  m 650 bus   add 6.50 "bus"
                                            m undo  remove the last entry
    help  or  ?      this list

Several entries can go in one message: "c 654 bites. c 250 pigs" logs
both, and the number may sit before or after its label.

Every reply is kept inside one text message (the 7110 shows a long
message as several), and at most two are sent for one command.
"""
import datetime
import json
import os
import time
import unicodedata
import urllib.parse

import wapapp
import wapfetch as wf

LIMIT = 160          # one GSM text
MAX_REPLIES = 2      # never flood the phone


def plain(text):
    """GSM-safe plain text: smart punctuation folded, non-GSM dropped."""
    out = []
    for ch in text:
        ch = wf.PLAIN.get(ch, ch)
        for c in ch:
            if c == "£" or 32 <= ord(c) < 127:   # keep the pound sign
                out.append(c)
            elif c in "\n\t":
                out.append(" ")
    return " ".join("".join(out).split())


def fit(text, limit=LIMIT):
    return plain(text)[:limit]


def _amount(args, hi):
    """Index of the first whole-number token in args within 1..hi, or None.
    Lets a label sit before or after it (c 654 bites, c bites 654)."""
    return next((i for i, a in enumerate(args)
                 if a.isdigit() and 0 < int(a) <= hi), None)


def _weather_all():
    """The prepared weather: one entry per configured place, or []."""
    try:
        with open(wapapp._path("weather.json")) as f:
            return json.load(f)["data"]
    except (OSError, ValueError, KeyError):
        return []


def _weather_data():
    data = _weather_all()
    return data[0] if data else None


def _place():
    value = wapapp._conf().get("weather", "place1", fallback="Weather")
    return value.split(",")[0].strip()


def _conf_places():
    """Names of the configured places, in the order of the prepared data."""
    conf = wapapp._conf()
    names = []
    for key in ("place1", "place2"):
        value = conf.get("weather", key, fallback="")
        if value:
            names.append(value.split(",")[0].strip())
    return names


def _weather_line(name, w):
    c, d = w["current"], w["daily"]
    return (f"{name} now {wf.deg(c['temperature_2m'])}C "
            f"{wf.sky(c['weather_code'])}, {wf.compass(c['wind_direction_10m'])} "
            f"{round(c['wind_speed_10m'])}mph. "
            f"{wf.day_line(d, 0, 'Today')}. {wf.day_line(d, 1, 'Tmrw')}")


# Weather for a named town is fetched when asked for. A text reply is not
# held to the WAP gateway's three seconds, so there is time: about a second
# for the two requests below. Both are Open-Meteo services and need no key.
GEOCODE = "https://geocoding-api.open-meteo.com/v1/search?"
FORECAST = "https://api.open-meteo.com/v1/forecast?"
NET_TIMEOUT = 8              # seconds for each request
FRESH = 20 * 60              # a looked-up forecast is reused for this long
COUNTRY_ALIAS = {"UK": "GB"}
_found = {}                  # folded query -> (name, country, lat, lon)
_fetched = {}                # (lat, lon) -> (time, forecast)


def _fold(text):
    """Accents removed, so a name can be compared and sent as a text."""
    flat = unicodedata.normalize("NFKD", text)
    return "".join(c for c in flat if not unicodedata.combining(c))


def _search(name, count):
    q = urllib.parse.urlencode({"name": name, "count": count,
                                "language": "en", "format": "json"})
    reply = json.loads(wf.http_get(GEOCODE + q, timeout=NET_TIMEOUT))
    return reply.get("results") or []


def _find_place(query):
    """(name, country code, latitude, longitude) for a town, or None when
    there is no such place. A network failure raises."""
    key = _fold(query).lower()
    if key in _found:
        return _found[key]
    hit = None
    words = query.split()
    if len(words) > 1 and len(words[-1]) == 2 and words[-1].isalpha():
        # "St Helens AU": the search itself does not understand a country
        # code, so ask for the name alone and pick the match in that country.
        country = COUNTRY_ALIAS.get(words[-1].upper(), words[-1].upper())
        for r in _search(" ".join(words[:-1]), 10):
            if r.get("country_code") == country:
                hit = r
                break
    if hit is None:
        results = _search(query, 1)
        hit = results[0] if results else None
    if hit is None:
        return None
    place = (hit["name"], hit.get("country_code", ""),
             hit["latitude"], hit["longitude"])
    if len(_found) > 500:
        _found.clear()
    _found[key] = place
    return place


def _forecast(country, lat, lon):
    key = (lat, lon)
    kept = _fetched.get(key)
    if kept and time.monotonic() - kept[0] < FRESH:
        return kept[1]
    fields = {
        "latitude": lat, "longitude": lon,
        "current": "temperature_2m,weather_code,wind_speed_10m,wind_direction_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                 "precipitation_probability_max",
        "timezone": "auto",          # today and tomorrow by the place's clock
        "wind_speed_unit": "mph", "forecast_days": "2",
    }
    if country == "GB":
        fields["models"] = "ukmo_seamless"   # as for the home place
    w = json.loads(wf.http_get(FORECAST + urllib.parse.urlencode(fields),
                               timeout=NET_TIMEOUT))
    if w.get("error"):
        raise RuntimeError(w.get("reason", "weather service error"))
    if len(_fetched) > 100:
        _fetched.clear()
    _fetched[key] = (time.monotonic(), w)
    return w


def weather(args):
    query = " ".join(args or []).strip(" .,;:!?")[:40]
    if not query:
        w = _weather_data()
        if not w:
            return ["Weather not available yet."]
        return [fit(_weather_line(_place(), w))]
    # A configured place is answered from the prepared file: no waiting,
    # and it works when the internet does not.
    data = _weather_all()
    for i, name in enumerate(_conf_places()):
        if _fold(name).lower() == _fold(query).lower() and i < len(data):
            return [fit(_weather_line(name, data[i]))]
    shown = plain(_fold(query))
    try:
        place = _find_place(query)
        if place is None:
            return [fit(f"No place found called {shown}.")]
        name, country, lat, lon = place
        w = _forecast(country, lat, lon)
        label = f"{plain(_fold(name))[:24]} {country}".strip()
        return [fit(_weather_line(label, w))]
    except Exception:
        return [fit(f"Weather for {shown} not available just now.")]


def news(_args):
    try:
        with open(wapapp._path("news-bbc.json")) as f:
            items = json.load(f)["data"]
    except (OSError, ValueError, KeyError):
        return ["News not available yet."]
    heads = [f"{i}. {wf.shorten(plain(title), 55)}"
             for i, (title, _desc) in enumerate(items, 1)]
    # Pack the headlines greedily into at most two texts (the second with no
    # "BBC:" prefix). The phone shows each as its own message.
    msgs, cur = [], "BBC:"
    for h in heads:
        add = (" " if cur else "") + h
        if len(cur) + len(add) > LIMIT:
            if cur:
                msgs.append(cur)
            if len(msgs) >= MAX_REPLIES:
                cur = ""
                break
            cur = h
        else:
            cur += add
    if cur and len(msgs) < MAX_REPLIES:
        msgs.append(cur)
    return msgs or ["No headlines."]


def today(_args):
    now = wapapp._now()
    bits = [now.strftime("%a %d %b %H:%M")]
    w = _weather_data()
    if w:
        c, d = w["current"], w["daily"]
        bits.append(f"{_place()} {wf.deg(c['temperature_2m'])}C {wf.sky(c['weather_code'])}")
        bits.append(wf.day_line(d, 0, "Today"))
    kcal = wapapp.kcal_today()
    if kcal:
        bits.append(f"{kcal} kcal")
    return [fit(". ".join(bits))]


def calories(args):
    if not args:
        return [f"Calories today: {wapapp.kcal_today()} kcal. (c 250 to add, c undo)"]
    if args[0].lower() == "undo":
        last = wapapp.cal_undo(today_only=True)
        if last is None:
            return ["Nothing entered today."]
        return [f"Removed {last[3]}. Today {wapapp.kcal_today()} kcal"]
    idx = _amount(args, 9999)       # amount may sit before or after a label
    if idx is not None:
        k = int(args[idx])
        label = " ".join(args[:idx] + args[idx + 1:]).strip(" .,;")[:40]
        wapapp.cal_add(k, label)
        return [f"Added {k}. Today {wapapp.kcal_today()} kcal"]
    return ["Calories: c (today), c 250 (add), c undo."]


def _cash_reply(lead):
    rows = wapapp._cash()
    total = wapapp._cash_total(rows).replace("Spent ", "Spent £")
    out = f"{lead} {total}."
    if rows:
        when, pence, what = rows[-1]
        day = datetime.date.fromisoformat(when[:10]).strftime("%d %b").lstrip("0")
        out += f" Last: {what} £{wapapp.money(pence)} ({day})"
    return [fit(out)]


def cash(args):
    if not args:
        return _cash_reply("Cash:")
    if args[0].lower() == "undo":
        rows = wapapp._read("cash.tsv")
        if not rows:
            return ["Nothing logged."]
        last = rows.pop()
        wapapp._write("cash.tsv", rows)
        what = last[2] if len(last) > 2 else ""
        return _cash_reply(f"Removed {what} £{wapapp.money(int(last[1]))}.")
    idx = _amount(args, 999999)
    if idx is not None:             # amount anywhere; the rest is the note
        pence = int(args[idx])
        what = " ".join(args[:idx] + args[idx + 1:]).strip(" .,;")[:24] or "-"
        wapapp._append("cash.tsv", [wapapp._now().isoformat(sep=" "), str(pence), what])
        return _cash_reply(f"Added {what} £{wapapp.money(pence)}.")
    return ["Cash: m (total), m 650 bus (add 6.50), m undo."]


def help_(_args):
    return ["MacWAP: w weather (w Berlin), n news, t today, c calories (c 250 add, c undo), "
            "m cash (m 650 bus, m undo)."]


COMMANDS = {
    "w": weather, "weather": weather,
    "n": news, "news": news,
    "t": today, "today": today, "": today,
    "c": calories, "cal": calories, "calories": calories,
    "m": cash, "cash": cash, "money": cash,
    "help": help_, "?": help_, "h": help_,
}


# Data-entry commands may be chained in one message. A new command starts
# at each of these keywords; a query command (w, n, t, help) is not a split
# point, because it is more likely a word in a cash note ("m 300 t shirt").
# A ';' or a new line forces a split anywhere. A weather command keeps all
# its words, as a place name may contain one of the keywords.
ENTRY = {"c", "cal", "calories", "m", "cash", "money"}
WHOLE = {"w", "weather"}


def _split_commands(text):
    """Split one message into its separate commands.
    'C 654 Bites. C 250 Pigs' -> [['C','654','Bites.'], ['C','250','Pigs']]."""
    groups, cur = [], []
    for raw in (text or "").replace("\n", " ; ").replace(";", " ; ").split():
        if raw == ";":
            if cur:
                groups.append(cur)
                cur = []
            continue
        if (cur and raw.strip(".,:;").lower() in ENTRY
                and cur[0].strip(".,:;").lower() not in WHOLE):
            groups.append(cur)
            cur = [raw]
        else:
            cur.append(raw)
    if cur:
        groups.append(cur)
    return groups or [[]]


def _run(parts):
    word = parts[0].strip(".,:;").lower() if parts else ""
    fn = COMMANDS.get(word)
    if fn is None:
        return help_(None)
    try:
        replies = fn(parts[1:])
    except Exception:                     # never leave the phone unanswered
        return ["Sorry, that failed."]
    return [fit(m) for m in replies[:MAX_REPLIES]]


def handle(text):
    """Return the reply messages for a command text (always at least one).
    One message may hold several chained commands; each is run in turn, and
    at most two texts go back. The sender has already been checked."""
    groups = _split_commands(text)
    if len(groups) == 1:
        return _run(groups[0])
    replies = []
    for g in groups:
        replies.extend(_run(g))
    if len(replies) > MAX_REPLIES:        # keep the most recent, incl. final total
        replies = replies[-MAX_REPLIES:]
    return [fit(m) for m in replies]


if __name__ == "__main__":          # quick local check: smscmd.py "w"
    import sys
    for m in handle(" ".join(sys.argv[1:])):
        print(f"[{len(m)}] {m}")
