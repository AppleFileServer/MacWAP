# MacWAP

A private WAP gateway for a Nokia 7110, running on a Raspberry Pi 3 with a
SIM800C GSM HAT. The phone texts (or calls) the Pi from anywhere; the Pi
answers with WAP pages it stores or builds from the internet.

**Status (14 November 2026):** the WAP side is built and verified on the
Pi — Kannel compiles the decks, and a genuine 7110 request (captured in
an emulator) replayed through the gateway returns the live Today deck —
but it cannot run over the current SIMs: the current network
refuses, when sent, any message carrying the 16-bit port header that WAP
over text messages depends on. The WAP decks are kept for a future route.
In its place a **plain-SMS command service** is live: the phone texts a
short command (`w`, `n`, `t`, `c`, `m`, …) and gets ordinary texts back,
sharing its data with the decks. See `docs/SERVICES.md`, section 7, for
the commands and `docs/LIMITS.md`, section 12, for the bearer tests. Data
calls are not possible with this HAT.

## How it works

    Nokia 7110 --texts--> SIM800C HAT -> Kannel -> wap-over-sms -> Kannel wapbox
                                                                       |
                                              pages on the Pi  <- wapserver.py

- **Kannel** is the open-source WAP gateway. It compiles WML pages to the
  binary form the phone needs.
- **wap-over-sms** (github.com/bevelgacom/wap-over-sms) carries WAP inside
  text messages, which is the bearer the 7110 supports besides data calls.
- **wapserver.py** serves the pages in `/srv/wap` to Kannel on the Pi only.

## Contents

| Path | What it is |
|---|---|
| `deploy/install.sh` | Run on the Pi as root: `base`, later `enable-sms HAT-NUMBER PHONE-NUMBER` |
| `deploy/kannel.conf` | Kannel core and WAP settings |
| `deploy/sms.conf.hat` | Modem and text-message settings (untested) |
| `deploy/wapserver.py`, `*.service` | Page server and systemd units |
| `deploy/wapsms.py` | Sorts incoming texts: WAP requests relayed, commands from the allowed phone answered, everything else to an inbox |
| `deploy/smscmd.py` | The plain-SMS command service (`w`, `n`, `t`, `c`, `m`, …); shares data with the decks |
| `deploy/wapapp.py` | Decks built at request time: Today, Calories, Cash |
| `deploy/wapfetch.py`, `wapfetch.timer` | Prepares the decks (weather, news, Today) every 15 minutes |
| `deploy/services.conf.example` | Settings for the above: places, feeds |
| `docs/SERVICES.md` | The services planned and built |
| `docs/MACTRACK-FEED.md` | The calorie-log file format MacTrack imports |
| `deploy/www/` | A fallback home deck for a Pi with no settings yet |
| `build-wap-over-sms.sh` | Builds wap-over-sms for the Pi into `deploy/` |
| `docs/LIMITS.md` | What the phone and the link can carry, and how to design for it |
| `tools/wapget.py` | Fetches a page through the gateway as a phone would (run on the Pi) |

`vendor/` and the built `deploy/wap-over-sms` are not tracked.

## Limits set by the phone

- WML 1.1 only; one fetch at most about 1,400 bytes once compiled.
- Addresses at most about 100 bytes over text messages.
- Use connection type "Temporary", connection security off.

## Still to do

- Extend the plain-SMS service (`deploy/smscmd.py`): bus times, mail
  subjects, alerts, Ask.
- For the kept WAP route: a SIM on a network that carries the 16-bit
  header, or phone firmware that uses the 8-bit header (the analysis is
  in the private notes).
- Test the allow-list in `wapsms.py` with a WAP request from another
  number, once WAP requests can arrive at all.

## Licence

MIT. See `LICENSE`. wap-over-sms and Kannel carry their own licences.
