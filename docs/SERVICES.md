# MacWAP: services

The list of services planned for the phone. A living document: add to it
freely. Started 14 November 2026.

**Built so far (14 November 2026):** Today, Weather and News (BBC),
prepared every 15 minutes by `deploy/wapfetch.py` and measured through
the gateway: Today 140 bytes (2 texts back), Weather 393 (4), News
headlines 447 (5), News summaries 741 (7). Not yet seen on the phone.

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
| Mail | Wanted | Subjects of new messages only (with the sender's name if it fits) | 1 + 3 | Uses the mail gateway already on the Pi; to be agreed with that project. Never bodies |
| Ask | Wanted | Type a short question; get a summarised answer | 1 + 1, then 1 or 2 plain texts back | See section 3a |

### Personal

| Service | Status | What the phone does | Texts | Notes |
|---|---|---|---|---|
| Calories: add | Wanted | Enter a number of calories, optionally pick a meal; the reply confirms and shows today's total | 1 + 1 | Home side is MacTrack (Open, section 3) |
| Calories: view | Wanted | Today's total and what is left of the target; the last seven days | 1 + 2 | Needs MacTrack's figures to reach the Pi (Open) |
| Cash: add | Wanted | Enter a short description and an amount in pence (650 for 6.50, 6500 for 65.00); the reply confirms | 1 + 1 | A log of its own on the Pi. No categories. Not sent to MacMoney, which records only the total cash held |
| Cash: view | Wanted | The latest entries and the total spent since the log was last cleared; a "clear" action for when the cash figure in MacMoney has been brought up to date | 1 + 2 | Cash only. No balances or totals of worth |
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
7. **Nothing sensitive on a page.** Messages have only the network's own
   protection: no passwords, account numbers or message bodies.

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
