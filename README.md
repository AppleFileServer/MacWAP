# MacWAP

A private WAP gateway for a Nokia 7110, running on a Raspberry Pi 3 with a
SIM800C GSM HAT. The phone texts (or calls) the Pi from anywhere; the Pi
answers with WAP pages it stores or builds from the internet.

**Status (14 November 2026):** the WAP side is installed and running on
the Pi: Kannel fetches the home deck from the page server and compiles it
(718 bytes of WML become 317 bytes), checked with `tools/wapget.py`. The
text-message side is not enabled: the HAT is fitted and its modem answers
on the serial port, but its SIM has not arrived.
Whether the link will be text messages or a data call is to be decided by
test.

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
| `deploy/wapfetch.py`, `wapfetch.timer` | Prepares the decks (weather, news, Today) every 15 minutes |
| `deploy/services.conf.example` | Settings for the above: places, feeds |
| `docs/SERVICES.md` | The services planned and built |
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

- Test the allow-list: `enable-sms` restricts the gateway to one phone
  number (Kannel `white-list-sender-regex`); confirm a text from any other number
  is discarded.
- Test whether the network passes the binary messages.

## Licence

MIT. See `LICENSE`. wap-over-sms and Kannel carry their own licences.
