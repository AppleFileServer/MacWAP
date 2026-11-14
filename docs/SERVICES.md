# MacWAP: services

The list of services planned for the phone. A living document: add to it
freely. Started 14 November 2026.

**Built so far (14 November 2026):** Today, Weather and News (BBC),
prepared every 15 minutes by `deploy/wapfetch.py` and measured through
the gateway: Today 140 bytes (2 texts back), Weather 393 (4), News
headlines 447 (5), News summaries 741 (7).

Also built that day, in `deploy/wapapp.py` (decks made at request time
from files on the Pi): Calories and Cash, each a form deck of 3 texts
with every add, undo and clear answered in 1 text; and the Today deck
now shows the calorie total and links to both (2 texts).

None of it has been seen on the phone yet. To check there first: that
the phone fills the typed values into the address, that a description
with spaces arrives intact, and that it fetches a form afresh each time
instead of showing a stored copy.

Sizes and message counts follow `LIMITS.md`. "Texts" means messages out
from the phone + messages back from the Pi, per fetch, and all are
estimates until the first test.

Place names, operators, stops and other personal details are kept out of
this file, because the repository is public. They live in
`private/SERVICES-LOCAL.md`, which is not tracked.

## Status key

- **Built**: running on the Pi (not necessarily tried on the phone yet).
- **Wanted**: asked for by the owner.
- **Suggested**: proposed, not yet accepted.
- **Open**: has a question that must be answered before it can be built.

## 1. The list

### Shared with the Plus

These are the same services planned for the Macintosh Plus (MacWeather,
MacNews, MacMail, MacThink). One fetcher on the Pi should feed both: it
collects the data once, and writes a WML deck for the phone and whatever
the Plus needs.

| Service | Status | What the phone shows | Texts | Notes |
|---|---|---|---|---|
| Weather | Built | Two places (home and town), a card each: today, tonight, tomorrow, then a 3-day outlook; rain chance, temperature, wind, sunrise and sunset | 1 + 4 | Prepared hourly. Sources researched, section 4 |
| News | Built (BBC); Guardian wanted, awaiting a key | Six to eight headlines; each links to a two-sentence summary in the same deck if it fits, otherwise a second fetch | 1 + 5 | Prepared every 15 to 30 minutes. Sources researched, section 4 |
| Mail | Wanted | Subjects of new messages; open one to read the start of its text. Any verification code in a new message is shown first, on its own line, so a code sent by email can be read when away from home | 1 + 3; a message 1 + 3 | Uses the mail gateway already on the Pi; to be agreed with that project. Replies go only to the owner's phone |
| Texts | Built | The latest ordinary texts received by the Pi's own SIM (network notices, verification codes) | 1 + 2 | Kept in an inbox file by `deploy/wapsms.py`; never answered |
| Ask | Wanted | Type a short question; get a summarised answer | 1 + 1, then 1 or 2 plain texts back | See section 3a |

### Personal

| Service | Status | What the phone does | Texts | Notes |
|---|---|---|---|---|
| Calories: add | Built | Enter a number of calories, optionally pick a meal; the reply confirms and shows today's total | 1 + 1 | Home side is MacTrack (Open, section 3) |
| Calories: view | Built (phone entries only) | Today's total and the last seven days, on the same deck as the entry field | 1 + 3 | Shows what was entered from the phone; MacTrack's figures are not included (Open). No target yet |
| Cash: add | Built | Enter a short description and an amount in pence (650 for 6.50, 6500 for 65.00); the reply confirms | 1 + 1 | A log of its own on the Pi. No categories. Not sent to MacMoney, which records only the total cash held |
| Cash: view | Built | The latest entries and the total spent since the log was last cleared; a "clear" action for when the cash figure in MacMoney has been brought up to date | 1 + 2 | Cash only. No balances or totals of worth |
| Bus times: timetable | Wanted | Next four departures for each of the saved journeys, both directions (three services of two operators; details in the private file) | 1 + 2 | Prepared daily from published timetables, so always instant |
| Bus times: live | Wanted | The same, with live predictions where available | 1 + 2 | Sources researched, section 4; needs an application to a data provider |

### Suggestions

| Service | What it would do | Texts | Why |
|---|---|---|---|
| **Today** (the home deck; built, weather lines only so far) | One screenful: date, weather in a line, next bus, unread mail count, calories so far; below it, the menu | 1 + 3 | Most of what is wanted, most days, in one fetch. Best value per text |
| Alerts by ordinary text | The Pi texts the phone unprompted: mail from chosen people, a frost or heavy-rain warning, a bus disruption, a fault on the Pi | 0 + 1 | The only way to push. No WAP involved |
| Trains | Live departures from one or two saved stations | 1 + 3 | A free official live feed exists for Great Britain |
| Lists | Shopping and to-do lists: add an item from the phone or the Plus, read and tick off on the phone | 1 + 2 | Two-way, small, and useful where the phone actually is |
| Pocket notes | Any short text file saved to a folder on the shared drive from the Plus becomes a card on the phone | 1 + 2–4 | Write at the desk, read when out. No new program on the Plus |
| Note to self | Type a line on the phone; it appears as a file on the Plus's shared drive | 1 + 1 | The reverse of pocket notes |
| Diary | Today's and tomorrow's appointments | 1 + 2 | A plain text file at first; MacCalendar later |
| Home status | Is the Pi healthy, is the Plus on the network, when did data last update | 1 + 1 | Also a quick test that the gateway is alive |
| Sport and TV | Results for chosen teams; tonight's programmes on chosen channels | 1 + 3 | Classic uses of the period |

## 2. Rules every service follows

1. **One deck per service**, within the budget: 4 texts back for things
   used daily, 8 at most for anything else.
2. **Prepared in advance.** Anything from the internet is fetched by a
   timed job and stored as a finished deck. Each deck shows the time of
   its data.
3. **Adding data is one short address**, for example `http://pi/c?k=450`,
   and the reply is a confirmation small enough for one text (under 97
   bytes compiled), showing the new running total.
4. **Entries go into a journal on the Pi**: one line per entry with date,
   time and source. The journal is the Pi's own; home programs read it.
5. **Guard against double entry.** If a reply is lost, the natural
   reaction is to send again. The confirmation shows the running total,
   and each "add" deck offers "Undo last".
6. **Amounts are whole numbers.** The phone's number editor has no
   decimal point, so money is entered in pence (450 for 4.50).
7. **Little that is sensitive on a page.** Messages have only the
   network's own protection: no passwords or account numbers. Mail and
   verification codes are shown at the owner's request; they are sent
   only to the owner's phone and only when asked for.

## 3. Open: the home side of calories

"Home side" means MacTrack on the Plus. The Pi cannot run it, so the link
is by files on the drive the Plus and the Pi share.

- **Phone to home:** the Pi's journal is a text file on the shared drive.
  MacTrack would need an "import from phone" step. That is new work in
  MacTrack, to be agreed in its own project. Until then the journal
  still collects entries and the phone can show them back.
- **Home to phone:** for the phone to show totals that include what was
  entered on the Plus, MacTrack would need to write a small summary file
  to the shared drive. Without it, the phone shows only what was entered
  from the phone.
- **Questions for the owner:** whether meals are worth a menu or a bare
  number is enough; the daily calorie target, if "remaining" is wanted.

Cash needs none of this: it is a log kept on the Pi alone.

## 3a. Ask: keeping answers short

- The question goes out as one WAP request; the reply page says only
  "Asked". The answer is produced in the background, because it takes
  longer than the 3 seconds the gateway allows.
- The answer comes back as **ordinary text messages**. The 7110 shows a
  long message as separate messages, so each must stand alone: at most
  160 characters, cut at a word, numbered "1/2", "2/2".
- **Limit: two messages (about 300 characters)** unless the question
  asks for more. The answering model is told the limit, and the Pi
  enforces it: anything longer is refused and re-summarised, never just
  cut off mid-sentence.
- Only the basic GSM character set is used. One character outside it
  (a curly quote, a long dash) halves a message's capacity to 70, so the
  Pi replaces such characters before sending.
- A longer answer, when wanted, is better as a WAP deck (about 1,000
  characters in one scrollable card): the text says "more at Ask" and
  the deck is fetched only if needed.
- Uses the API key already on the Pi for the Plus's chat service; to be
  agreed with that project.

## 4. Sources researched (14 November 2026)

Web research only. Nothing below has been signed up for or tested.

### Bus timetables

- **Bus Open Data Service** (Department for Transport). Operators in
  England publish their timetables there; anyone can register for a free
  account and an API key; the data is under the Open Government Licence.
  The Pi would download the timetable files for the wanted services and
  work out the next departures itself.
- To confirm on registering: that both operators' current timetables are
  there.

### Bus live times

| Source | What it gives | Terms | Verdict |
|---|---|---|---|
| Bus Open Data Service, location feed | Live positions of buses, by operator, service or map area. No predicted times at stops | Free, same account | Usable as a fallback: "the bus is at such a place" or an estimate worked out on the Pi |
| Traveline NextBuses API | Next departures at a named stop anywhere in Great Britain, live where the operator supplies it, scheduled otherwise | By application (allow two working days) and a licence agreement; reported free up to agreed limits, but current limits and any charge are not confirmed | **First choice.** It is exactly the question the phone asks. Apply and ask about terms for one private user |
| bustimes.org | A volunteer-run site with live tracking built on the open data; it has an API | No published terms found | Ask its author before using; do not rely on it |
| TransportAPI | Live and scheduled departures | Paid commercial service | Not for this |
| The operators' own apps | Live times | No public interface | Do not reverse-engineer |

Plan: build the timetable service first; apply to Traveline for live
times; if that fails, add positions from the open data.

### Weather

| Source | What it gives | Terms | Verdict |
|---|---|---|---|
| Open-Meteo | Hourly and daily forecasts for any point; includes the Met Office's 2 km UK model (must be selected by name; it covers two days, with the 10 km global model beyond) | Free for non-commercial use, no key or account, up to 10,000 calls a day; credit required | **First choice.** Nothing to sign up for |
| Met Office Weather DataHub | Official site-specific forecasts: hourly, three-hourly, daily | Free plan with an account and key; reported as 360 calls a day | Good alternative if the official source is preferred |
| BBC Weather | No supported interface found | Unclear | Not recommended |

Two places hourly is 48 calls a day, far inside either limit.

### News

| Source | What it gives | Terms | Verdict |
|---|---|---|---|
| The Guardian Open Platform | Headlines, summaries and full text through a documented interface | Free developer key for non-commercial use, issued at once; the daily limit is reported as 500 calls (older reports say 5,000) | **Cleanest terms.** Thirty-minute updates use 48 calls a day |
| BBC News RSS feeds | Headline and one-line summary per story; national and regional feeds | The current terms could not be confirmed. Older BBC guidance allowed feed use with the credit "BBC News"; a more recent second-hand quotation suggests limits on automated use | Technically the simplest, and reading a feed privately is what feeds are for, but the terms are **unverified**. Owner's decision |

Both could be offered as separate menu entries.

## 5. Suggested order of building

1. **Today + Weather**: proves the prepared-in-advance pipeline.
2. **Bus timetable** for the saved journeys.
3. **Calories and cash: add**, with the journal: proves two-way data.
4. **News**, then **Mail**.
5. **Alerts by text**.
6. **Ask**, then **live bus times** once a source is granted.
7. The remaining suggestions as wanted.

## 6. Ideas waiting

(Add new ideas here.)

## 7. Two ways the phone reaches the services

The same services can be delivered over two bearers.

**WAP (the decks).** The phone's own browser fetches WML decks through the
gateway. This is the richer interface (menus, forms, soft keys). It is
built and proven on the Pi end — a genuine 7110 request, captured in an
emulator and replayed through the gateway, returns the live Today deck —
but it cannot run over the current SIMs: the current network
refuses, at submission, any message carrying the 16-bit application-port
header that WAP needs in both directions (`LIMITS.md` §12). The decks
(`wapapp.py`, `wapfetch.py`, `wapserver.py`) are **kept** for a future
route — a SIM on a network that passes the header, or patched phone
firmware that uses the 8-bit header instead.

**Plain-SMS commands (live).** The phone texts a short command to the
Pi's SIM and gets one or two ordinary texts back. Ordinary texts travel
on the present SIMs in about five seconds each way, and they work abroad.
This shares its data with the decks: a calorie or cash entry made by text
is the same journal the WAP side reads. Built 14 November 2026 in
`deploy/smscmd.py`, handled inside `deploy/wapsms.py`, replies sent
through Kannel's `sendsms`.

| Command | Does | Reply |
|---|---|---|
| `w` | Weather for the home place | 1 text |
| `n` | Latest BBC headlines | up to 2 texts |
| `t` or blank | Today: time, weather, calories so far | 1 text |
| `c` | Calories today | 1 text |
| `c 250` | Add 250 kcal | 1 text |
| `c undo` | Remove the last entry made today | 1 text |
| `m` | Cash total and last entry | 1 text |
| `m 650 bus` | Add £6.50 described "bus" | 1 text |
| `m undo` | Remove the last cash entry | 1 text |
| `help` / `?` | The command list | 1 text |

Only the allowed phone's commands are answered; every other text (carrier
notices, verification codes, other numbers) still goes to the inbox
unanswered. Clearing the cash log is deliberately not a text command;
it stays on the WAP side where it asks for confirmation.

Still to add as plain-SMS commands:

- **Bus times** for the saved journeys.
- **Email reading** — new subjects, and a verification code out and about
  (the main reason the owner wants it). A text back with the subject and
  the start of the body, or the code.
- **Email sending** — e.g. `email to@addr Subject — body`. This does the
  job the 7110's dead "Email" message type once did (a flag the network's
  gateway acted on); here the Pi sends a genuine email instead, with the
  phone on message type Text. The phone's Fax/Email send types are
  obsolete network services and are not used.
- **Alerts** by text.
- **Ask** (short, summarised answers).

Email read and send depend on the Pi's mail gateway (a separate project):
to be done through an interface it offers, not by reading its files or
credentials, and agreed with that side first.
