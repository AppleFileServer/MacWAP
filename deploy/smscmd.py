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


def _weather_data():
    try:
        with open(wapapp._path("weather.json")) as f:
            return json.load(f)["data"][0]
    except (OSError, ValueError, KeyError, IndexError):
        return None


def _place():
    value = wapapp._conf().get("weather", "place1", fallback="Weather")
    return value.split(",")[0].strip()


def weather(_args):
    w = _weather_data()
    if not w:
        return ["Weather not available yet."]
    c, d = w["current"], w["daily"]
    line = (f"{_place()} now {wf.deg(c['temperature_2m'])}C "
            f"{wf.sky(c['weather_code'])}, {wf.compass(c['wind_direction_10m'])} "
            f"{round(c['wind_speed_10m'])}mph. "
            f"{wf.day_line(d, 0, 'Today')}. {wf.day_line(d, 1, 'Tmrw')}")
    return [fit(line)]


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
    return ["MacWAP: w weather, n news, t today, c calories (c 250 add, c undo), "
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
# A ';' or a new line forces a split anywhere.
ENTRY = {"c", "cal", "calories", "m", "cash", "money"}


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
        if cur and raw.strip(".,:;").lower() in ENTRY:
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
