"""The decks that are built at request time: Today, Calories, Cash.

Everything here works from files on the Pi, so a reply takes
milliseconds; nothing may wait on the internet (the gateway allows about
3 seconds).

Addresses (all under http://pi/):
    (none)       Today
    c            Calories: today's total, entry field, last 7 days
    ca?k=N       add N calories              cu   undo the last one today
    m            Cash: total, entry fields, recent entries
    ma?a=P&d=T   add P pence, described T    mu   undo the last entry
    mc           clear the cash log (it is kept in an archive file)
    i            Texts: the latest ordinary texts the Pi's SIM received

Every form carries a short token "t". A second request with the same
token and the same values inside ten minutes is treated as a repeat of
the first (a retry after a lost reply), not as a new entry.

Journals, in the state directory, one entry per line, tab-separated:
    calories.tsv    time, calories
    cash.tsv        time, pence, description
"""
import configparser
import datetime
import json
import os
import secrets
import threading
import time
import urllib.parse
from zoneinfo import ZoneInfo

import wapfetch as wf

CONF = os.environ.get("WAPFETCH_CONF", "/etc/wapgateway/services.conf")
STATE = os.environ.get("STATE_DIRECTORY", "/var/lib/wapgateway")
REPEAT_WINDOW = 600          # seconds

_lock = threading.Lock()
_seen = {}                   # (action, token, values) -> (time, reply text)


def _conf():
    conf = configparser.ConfigParser()
    conf.read(CONF)
    return conf


def _now():
    tz = _conf().get("general", "timezone", fallback="Europe/London")
    return datetime.datetime.now(ZoneInfo(tz)).replace(microsecond=0, tzinfo=None)


def _path(name):
    return os.path.join(STATE, name)


def _read(name):
    rows = []
    try:
        with open(_path(name), encoding="utf-8") as f:
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) >= 2:
                    rows.append(parts)
    except OSError:
        pass
    return rows


def _write(name, rows):
    tmp = _path(name) + ".new"
    with open(tmp, "w", encoding="utf-8") as f:
        for r in rows:
            f.write("\t".join(r) + "\n")
    os.replace(tmp, _path(name))


def _append(name, row):
    os.makedirs(STATE, exist_ok=True)
    with open(_path(name), "a", encoding="utf-8") as f:
        f.write("\t".join(row) + "\n")


def _repeat(key):
    """The earlier reply if this exact request was seen recently."""
    now = time.time()
    for k in [k for k, (t, _) in _seen.items() if now - t > REPEAT_WINDOW]:
        del _seen[k]
    hit = _seen.get(key)
    return hit[1] if hit else None


def _remember(key, text):
    _seen[key] = (time.time(), text)


def _note(title, text, links=""):
    """A deck small enough for one text message."""
    return wf.deck([("r", title, wf.wml(text) + links)])


def _number(q, name, most):
    value = q.get(name, [""])[0].strip()
    if not value.isdigit() or not 0 < int(value) <= most:
        return None
    return int(value)


def money(pence):
    return f"{pence // 100}.{pence % 100:02d}"


# --------------------------------------------------------------- calories

def _kcal_by_day():
    days = {}
    for r in _read("calories.tsv"):
        try:
            days[r[0][:10]] = days.get(r[0][:10], 0) + int(r[1])
        except ValueError:
            pass
    return days


def kcal_today():
    return _kcal_by_day().get(_now().date().isoformat(), 0)


def calories(q):
    t = secrets.token_hex(2)
    days = _kcal_by_day()
    today = _now().date()
    body = (f"Today {days.get(today.isoformat(), 0)} kcal<br/>"
            'kcal: <input name="k" title="kcal" format="*N" maxlength="4"/><br/>'
            f'<a href="ca?k=$(k)&amp;t={t}">Add</a><br/>'
            '<a href="#h">7 days</a><br/>'
            f'<a href="cu?t={t}">Undo last</a>')
    lines = []
    for i in range(7):
        d = today - datetime.timedelta(days=i)
        lines.append(f"{d.strftime('%a %d')} {days.get(d.isoformat(), 0)}")
    return wf.deck([("c", "Calories", body),
                    ("h", "7 days", "<br/>".join(lines))])


def calories_add(q):
    k = _number(q, "k", 9999)
    if k is None:
        return _note("Calories", "Enter a number, 1 to 9999.")
    key = ("ca", q.get("t", [""])[0], k)
    if "f" not in q:
        earlier = _repeat(key)
        if earlier:
            again = urllib.parse.urlencode({"k": k, "t": key[1], "f": 1})
            return _note("Repeat", "Already added. " + earlier,
                         f'<br/><a href="ca?{wf.wml(again)}">Add again</a>')
    _append("calories.tsv", [_now().isoformat(sep=" "), str(k)])
    text = f"Today {kcal_today()} kcal"
    _remember(key, text)
    return _note("Added", f"{k} added. {text}")


def calories_undo(q):
    key = ("cu", q.get("t", [""])[0], 0)
    if _repeat(key):
        return _note("Undo", "Already undone. " + _repeat(key))
    rows = _read("calories.tsv")
    today = _now().date().isoformat()
    if not rows or rows[-1][0][:10] != today:
        return _note("Undo", "Nothing entered today.")
    last = rows.pop()
    _write("calories.tsv", rows)
    text = f"Today {kcal_today()} kcal"
    _remember(key, text)
    return _note("Undone", f"{last[1]} removed. {text}")


# ------------------------------------------------------------------- cash

def _cash():
    rows = []
    for r in _read("cash.tsv"):
        try:
            rows.append((r[0], int(r[1]), r[2] if len(r) > 2 else ""))
        except ValueError:
            pass
    return rows


def _cash_total(rows):
    """'Spent 12.34 since 10 Nov' for the present log."""
    since = None
    try:
        with open(_path("cash.cleared")) as f:
            since = f.read().strip()[:10]
    except OSError:
        if rows:
            since = rows[0][0][:10]
    if since is None:
        return "Nothing logged"
    day = datetime.date.fromisoformat(since).strftime("%d %b").lstrip("0")
    return f"Spent {money(sum(r[1] for r in rows))} since {day}"


def cash(q):
    t = secrets.token_hex(2)
    rows = _cash()
    body = (f"{wf.wml(_cash_total(rows))}<br/>"
            'What: <input name="d" title="What" maxlength="16"/><br/>'
            'Pence: <input name="a" title="Pence" format="*N" maxlength="6"/><br/>'
            f'<a href="ma?a=$(a)&amp;d=$(d:e)&amp;t={t}">Add</a><br/>'
            '<a href="#r">Recent</a><br/>'
            f'<a href="mu?t={t}">Undo last</a><br/>'
            '<a href="#x">Clear log</a>')
    recent = []
    for when, pence, what in reversed(rows[-5:]):
        day = datetime.date.fromisoformat(when[:10]).strftime("%d %b").lstrip("0")
        recent.append(wf.wml(f"{day} {what} {money(pence)}"))
    clear = (f"Clear {len(rows)} entries, {money(sum(r[1] for r in rows))}?<br/>"
             f'<a href="mc?t={t}">Yes, clear</a>')
    return wf.deck([("m", "Cash", body),
                    ("r", "Recent", "<br/>".join(recent) or "Nothing logged"),
                    ("x", "Clear?", clear)])


def cash_add(q):
    a = _number(q, "a", 999999)
    if a is None:
        return _note("Cash", "Enter pence: 650 is 6.50.")
    what = " ".join(q.get("d", [""])[0].split())[:24] or "-"
    key = ("ma", q.get("t", [""])[0], (a, what))
    if "f" not in q:
        earlier = _repeat(key)
        if earlier:
            again = urllib.parse.urlencode({"a": a, "d": what, "t": key[1], "f": 1})
            return _note("Repeat", "Already added. " + earlier,
                         f'<br/><a href="ma?{wf.wml(again)}">Add again</a>')
    _append("cash.tsv", [_now().isoformat(sep=" "), str(a), what])
    text = _cash_total(_cash())
    _remember(key, text)
    return _note("Added", f"{what} {money(a)}. {text}")


def cash_undo(q):
    key = ("mu", q.get("t", [""])[0], 0)
    if _repeat(key):
        return _note("Undo", "Already undone. " + _repeat(key))
    rows = _read("cash.tsv")
    if not rows:
        return _note("Undo", "Nothing logged.")
    last = rows.pop()
    _write("cash.tsv", rows)
    text = _cash_total(_cash())
    _remember(key, text)
    what = last[2] if len(last) > 2 else ""
    return _note("Undone", f"{what} {money(int(last[1]))} removed. {text}")


def cash_clear(q):
    key = ("mc", q.get("t", [""])[0], 0)
    if _repeat(key):
        return _note("Cash", "Already cleared.")
    rows = _read("cash.tsv")
    with open(_path("cash-archive.tsv"), "a", encoding="utf-8") as f:
        for r in rows:
            f.write("\t".join(r) + "\n")
    _write("cash.tsv", [])
    with open(_path("cash.cleared"), "w") as f:
        f.write(_now().isoformat(sep=" ") + "\n")
    _remember(key, "cleared")
    return _note("Cash", f"Cleared {len(rows)} entries.")


# ------------------------------------------------------------------ inbox

def _inbox():
    return [r for r in _read("sms-inbox.tsv") if len(r) >= 3]


def inbox(q):
    """The latest ordinary texts received by the Pi's own SIM."""
    rows = _inbox()[-3:]
    if not rows:
        return _note("Texts", "No texts received.")
    cards = []
    for i, (when, sender, text) in enumerate(reversed(rows)):
        body = wf.wml(f"{when[11:16]} {when[8:10]}/{when[5:7]} {sender}: {wf.shorten(text, 160)}")
        if i + 1 < len(rows):
            body += f'<br/><a href="#i{i + 2}">Older</a>'
        cards.append((f"i{i + 1}", "Texts", body))
    return wf.deck(cards)


# ------------------------------------------------------------------ today

def today(q):
    conf = _conf()
    places = []
    value = conf.get("weather", "place1", fallback="")
    if value:
        places.append(tuple(x.strip() for x in value.split(",")))
    weather = None
    try:
        with open(_path("weather.json")) as f:
            weather = json.load(f)["data"]
    except (OSError, ValueError, KeyError):
        pass
    news = os.path.exists(os.path.join(wf.OUT, "n.wml"))
    return wf.today_deck(_now(), places, weather if places else None, news,
                         kcal=kcal_today(), texts=bool(_inbox()))


ROUTES = {
    "": today, "index.wml": today,
    "c": calories, "ca": calories_add, "cu": calories_undo,
    "m": cash, "ma": cash_add, "mu": cash_undo, "mc": cash_clear,
    "i": inbox,
}


def handle(route, query):
    """WML text for a route, or None if the route is not one of ours."""
    fn = ROUTES.get(route)
    if fn is None:
        return None
    with _lock:
        os.makedirs(STATE, exist_ok=True)
        return fn(urllib.parse.parse_qs(query, keep_blank_values=True))
