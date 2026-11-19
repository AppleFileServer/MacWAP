#!/usr/bin/env python3
"""Offline check of the SMS weather command. No network: the two
Open-Meteo services are replaced by canned answers.

    python3 tests/test_weather.py
"""
import json
import os
import sys
import tempfile
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "deploy"))

tmp = tempfile.mkdtemp()
os.environ["STATE_DIRECTORY"] = tmp
os.environ["WAPFETCH_CONF"] = os.path.join(tmp, "services.conf")
with open(os.environ["WAPFETCH_CONF"], "w") as f:
    f.write("[general]\ntimezone = Europe/London\n"
            "[weather]\nplace1 = Greenwich, 51.48, 0.0\n"
            "place2 = Edinburgh, 55.95, -3.19\n")


def forecast(temp):
    return {"current": {"temperature_2m": temp, "weather_code": 3,
                        "wind_speed_10m": 9.6, "wind_direction_10m": 140},
            "daily": {"weather_code": [61, 3],
                      "temperature_2m_max": [temp + 1, temp],
                      "temperature_2m_min": [temp - 3, temp - 4],
                      "precipitation_probability_max": [98, None]}}


with open(os.path.join(tmp, "weather.json"), "w") as f:
    json.dump({"at": "2026-11-19T10:00:00+00:00",
               "data": [forecast(6), forecast(2)]}, f)

import smscmd                                            # noqa: E402

PLACES = {
    "berlin": [("Berlin", "DE", 52.52, 13.41)],
    "koln": [("Cologne", "DE", 50.93, 6.95)],
    "st helens": [("St Helens", "GB", 53.45, -2.73),
                  ("St Helens", "AU", -41.32, 148.24)],
    "san jose m": [("San José M", "MX", 20.0, -100.0)],
    "ho chi minh": [("Thành phố Hồ Chí Minh with a very long name", "VN", 10.8, 106.6)],
}
calls = []
down = False


def fake_get(url, timeout=20):
    if down:
        raise OSError("network is down")
    parts = urllib.parse.urlsplit(url)
    q = dict(urllib.parse.parse_qsl(parts.query))
    calls.append((parts.netloc, q))
    if parts.netloc.startswith("geocoding"):
        found = PLACES.get(q["name"].lower(), [])[:int(q["count"])]
        if not found:
            return b"{}"
        return json.dumps({"results": [
            {"name": n, "country_code": c, "latitude": la, "longitude": lo}
            for n, c, la, lo in found]}).encode()
    return json.dumps(forecast(float(q["latitude"]) // 10)).encode()


smscmd.wf.http_get = fake_get
failures = 0


def check(what, got, want):
    global failures
    ok = want(got) if callable(want) else got == want
    if not ok:
        failures += 1
    print(("ok   " if ok else "FAIL ") + what + ("" if ok else f"\n     got {got!r}"))


def one(text):
    replies = smscmd.handle(text)
    assert all(len(m) <= 160 for m in replies), replies
    return replies[0] if len(replies) == 1 else replies


HOME = "Greenwich now 6C cloudy, SE 10mph. Today 7/3C lt rain 98%. Tmrw 6/2C cloudy"
check("w alone is the home place", one("w"), HOME)
check("W. with a full stop", one("W."), HOME)
check("no network used for home", calls, [])
check("second configured place from the file", one("W edinburgh"),
      lambda m: m.startswith("Edinburgh now 2C") and not calls)
check("configured place by name", one("weather GREENWICH"), HOME)

check("w Berlin", one("W Berlin"),
      "Berlin DE now 5C cloudy, SE 10mph. Today 6/2C lt rain 98%. Tmrw 5/1C cloudy")
check("  asked with timezone auto, no UK model",
      calls[-1][1].get("timezone") == "auto" and "models" not in calls[-1][1], True)
n = len(calls)
check("asked again soon: nothing fetched", (one("w berlin."), len(calls) - n),
      lambda r: r[0].startswith("Berlin DE now") and r[1] == 0)
check("name comes back in English", one("w Koln"), lambda m: m.startswith("Cologne DE now"))
check("first match wins", one("w St Helens"), lambda m: m.startswith("St Helens GB now"))
check("  UK place uses the UK model", calls[-1][1].get("models"), "ukmo_seamless")
check("country code picks the other", one("w St Helens AU"),
      lambda m: m.startswith("St Helens AU now -5C"))
check("uk means GB", one("w st helens uk"), lambda m: m.startswith("St Helens GB now"))
check("code with no match falls back to the whole name", one("w Berlin ZZ"),
      "No place found called Berlin ZZ.")
check("unknown place", one("w Xyzzyq"), "No place found called Xyzzyq.")
check("keyword inside a place name is not split off", one("w San Jose M"),
      lambda m: m.startswith("San Jose M MX now"))
check("long accented name folded and cut", one("w Ho Chi Minh"),
      lambda m: m.startswith("Thanh pho Ho Chi Minh wi VN now"))
check("entries still chain", one("c 100 tea. c 50 milk"),
      lambda r: isinstance(r, list) and r[-1] == "Added 50. Today 150 kcal")
check("cash note with t stays whole", one("m 300 t shirt"),
      lambda m: m.startswith("Added t shirt"))
check("help mentions it", one("help"), lambda m: "w Berlin" in m)

down = True
check("network down, new place", one("w Paris"), "Weather for Paris not available just now.")
check("network down, home still answers", one("w"), HOME)

print("\nall passed" if not failures else f"\n{failures} FAILED")
sys.exit(1 if failures else 0)
