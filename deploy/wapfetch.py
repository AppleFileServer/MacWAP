#!/usr/bin/env python3
"""Prepares the WAP decks in advance.

Run every few minutes by wapfetch.timer. Fetches weather and news from
the internet, keeps the last good copy of each, and writes finished WML
decks to /srv/wap, so the page server only ever hands over a file. The
gateway allows about 3 seconds per request; nothing may be fetched at
request time.

Decks written:
    index.wml   Today: date, weather in two lines, menu
    w.wml       Weather: a card per place, then the days ahead
    n.wml       News headlines (BBC)
    ns.wml      The first stories with their summaries

Settings: /etc/wapgateway/services.conf (see services.conf.example).
"""
import configparser
import datetime
import json
import os
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

CONF = os.environ.get("WAPFETCH_CONF", "/etc/wapgateway/services.conf")
OUT = os.environ.get("WAP_ROOT", "/srv/wap")
STATE = os.environ.get("STATE_DIRECTORY", "/var/lib/wapgateway")
AGENT = "MacWAP/1.0"

# ---------------------------------------------------------------- helpers

PLAIN = {
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "…": "..", " ": " ",
    "€": "EUR",
}


def wml(text):
    """Text made safe for a WML deck: ASCII only, markup escaped."""
    out = []
    for ch in text:
        ch = PLAIN.get(ch, ch)
        for c in ch:
            if c == "&":
                out.append("&amp;")
            elif c == "<":
                out.append("&lt;")
            elif c == ">":
                out.append("&gt;")
            elif c == '"':
                out.append("&quot;")
            elif c == "$":
                out.append("$$")
            elif 32 <= ord(c) < 127:
                out.append(c)
            elif 160 <= ord(c) < 256:
                out.append(f"&#{ord(c)};")   # Latin-1, e.g. the pound sign
            elif c in "\n\t":
                out.append(" ")
            # anything else is dropped: the phone cannot show it
    return "".join(out)


def shorten(text, limit):
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[:limit - 1]
    if " " in cut:
        cut = cut[:cut.rindex(" ")]
    return cut.rstrip(" ,;:-") + ".."


def deck(cards):
    """cards: list of (id, title, body-wml). One Back key for all cards."""
    parts = ['<?xml version="1.0"?>\n'
             '<!DOCTYPE wml PUBLIC "-//WAPFORUM//DTD WML 1.1//EN" '
             '"http://www.wapforum.org/DTD/wml_1.1.xml">\n<wml>\n'
             '<template><do type="prev" label="Back"><prev/></do></template>\n']
    for cid, title, body in cards:
        parts.append(f'<card id="{cid}" title="{wml(title)}"><p>{body}</p></card>\n')
    parts.append("</wml>\n")
    return "".join(parts)


def write(name, text):
    path = os.path.join(OUT, name)
    tmp = path + ".new"
    with open(tmp, "w", encoding="ascii") as f:
        f.write(text)
    os.replace(tmp, path)


def http_get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def cached(name, max_age_min, fetch):
    """Return (data, fetched-at). Refetch when stale; on failure keep the
    last good copy, however old."""
    path = os.path.join(STATE, name + ".json")
    old = None
    try:
        with open(path) as f:
            old = json.load(f)
    except (OSError, ValueError):
        pass
    now = datetime.datetime.now(datetime.timezone.utc)
    if old:
        age = now - datetime.datetime.fromisoformat(old["at"])
        if age < datetime.timedelta(minutes=max_age_min):
            return old["data"], datetime.datetime.fromisoformat(old["at"])
    try:
        data = fetch()
    except Exception as e:                      # network, format, anything
        print(f"wapfetch: {name}: {e}", file=sys.stderr)
        if old:
            return old["data"], datetime.datetime.fromisoformat(old["at"])
        return None, None
    tmp = path + ".new"
    with open(tmp, "w") as f:
        json.dump({"at": now.isoformat(), "data": data}, f)
    os.replace(tmp, path)
    return data, now


# ---------------------------------------------------------------- weather

SKY = {
    0: "clear", 1: "fair", 2: "part cloud", 3: "cloudy", 45: "fog", 48: "fog",
    51: "lt drizzle", 53: "drizzle", 55: "drizzle", 56: "frz drizzle",
    57: "frz drizzle", 61: "lt rain", 63: "rain", 65: "hvy rain",
    66: "frz rain", 67: "frz rain", 71: "lt snow", 73: "snow",
    75: "hvy snow", 77: "snow", 80: "lt showers", 81: "showers",
    82: "hvy showers", 85: "snow shwrs", 86: "snow shwrs", 95: "thunder",
    96: "thunder", 99: "thunder",
}
WIND = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def sky(code):
    return SKY.get(int(code), "?")


def compass(deg):
    return WIND[int((float(deg) + 22.5) // 45) % 8]


def deg(x):
    return f"{round(float(x))}"


def fetch_weather(places, tz):
    q = urllib.parse.urlencode({
        "latitude": ",".join(p[1] for p in places),
        "longitude": ",".join(p[2] for p in places),
        "models": "ukmo_seamless",
        "current": "temperature_2m,weather_code,wind_speed_10m,wind_direction_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                 "precipitation_probability_max,sunrise,sunset,wind_speed_10m_max",
        "timezone": tz, "wind_speed_unit": "mph", "forecast_days": "5",
    })
    data = json.loads(http_get("https://api.open-meteo.com/v1/forecast?" + q))
    if isinstance(data, dict):
        if data.get("error"):
            raise RuntimeError(data.get("reason", "weather service error"))
        data = [data]
    return data


def day_line(d, i, label):
    rain = d["precipitation_probability_max"][i]
    rain = f" {round(rain)}%" if rain is not None else ""
    return (f"{label} {deg(d['temperature_2m_max'][i])}/"
            f"{deg(d['temperature_2m_min'][i])}C {sky(d['weather_code'][i])}{rain}")


def weather_cards(places, data, stamp):
    cards = []
    for n, (place, w) in enumerate(zip(places, data)):
        c, d = w["current"], w["daily"]
        lines = [
            f"Now {deg(c['temperature_2m'])}C {sky(c['weather_code'])}, "
            f"{compass(c['wind_direction_10m'])} {round(c['wind_speed_10m'])}mph",
            day_line(d, 0, "Today"),
            day_line(d, 1, "Tmrw"),
            f"Sun {d['sunrise'][0][11:16]}-{d['sunset'][0][11:16]}",
        ]
        body = "<br/>".join(wml(x) for x in lines)
        if n + 1 < len(places):
            body += f'<br/><a href="#p{n + 2}">{wml(places[n + 1][0])}</a>'
        if n == 0:
            body += '<br/><a href="#d">Days ahead</a>'
        cards.append((f"p{n + 1}", place[0], body))
    d = data[0]["daily"]
    lines = []
    for i in range(2, len(d["time"])):
        day = datetime.date.fromisoformat(d["time"][i]).strftime("%a")
        lines.append(day_line(d, i, day))
    lines.append(f"{places[0][0]}, at {stamp}")
    cards.append(("d", "Days ahead", "<br/>".join(wml(x) for x in lines)))
    return cards


# ------------------------------------------------------------------- news

def fetch_feed(url):
    root = ET.fromstring(http_get(url))
    items = []
    for it in root.findall("channel/item")[:12]:
        title = (it.findtext("title") or "").strip()
        desc = (it.findtext("description") or "").strip()
        if title:
            items.append([title, desc])
    if not items:
        raise RuntimeError("feed has no stories")
    return items


def news_decks(items, stamp, source):
    heads = [f"{i + 1}. {wml(shorten(t, 70))}" for i, (t, _) in enumerate(items[:5])]
    body = "<br/>".join(heads) + f'<br/><a href="ns">Summaries</a><br/>{wml(source)} {stamp}'
    headlines = deck([("n", "News", body)])
    cards = []
    for i, (t, dsc) in enumerate(items[:3]):
        body = f"{wml(shorten(t, 80))}<br/>{wml(shorten(dsc, 150))}"
        if i < 2:
            body += f'<br/><a href="#s{i + 2}">Next</a>'
        cards.append((f"s{i + 1}", f"Story {i + 1}", body))
    return headlines, deck(cards)


# ------------------------------------------------------------------ today

def today_deck(now, places, weather, items):
    lines = [now.strftime("%a %d %b %H:%M")]
    if weather:
        c, d = weather[0]["current"], weather[0]["daily"]
        lines.append(f"{places[0][0]} {deg(c['temperature_2m'])}C {sky(c['weather_code'])}")
        lines.append(day_line(d, 0, "Today"))
    body = "<br/>".join(wml(x) for x in lines)
    if weather:
        body += '<br/><a href="w">Weather</a>'
    if items:
        body += '<br/><a href="n">News</a>'
    return deck([("t", "Today", body)])


# ------------------------------------------------------------------- main

def main():
    conf = configparser.ConfigParser()
    if not conf.read(CONF):
        sys.exit(f"wapfetch: cannot read {CONF}")
    tz = conf.get("general", "timezone", fallback="Europe/London")
    now = datetime.datetime.now(ZoneInfo(tz))
    os.makedirs(STATE, exist_ok=True)

    def stamp(at):
        return at.astimezone(ZoneInfo(tz)).strftime("%H:%M")

    places = []
    for key in ("place1", "place2"):
        value = conf.get("weather", key, fallback="")
        if value:
            name, lat, lon = [x.strip() for x in value.split(",")]
            places.append((name, lat, lon))
    weather = None
    if places:
        weather, at = cached("weather", 55, lambda: fetch_weather(places, tz))
        if weather:
            write("w.wml", deck(weather_cards(places, weather, stamp(at))))

    items = None
    feed = conf.get("news", "bbc", fallback="")
    if feed:
        items, at = cached("news-bbc", 14, lambda: fetch_feed(feed))
        if items:
            headlines, stories = news_decks(items, stamp(at), "BBC News")
            write("n.wml", headlines)
            write("ns.wml", stories)

    write("index.wml", today_deck(now, places, weather, items))


if __name__ == "__main__":
    main()
