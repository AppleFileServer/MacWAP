# MacWAP

A private WAP gateway for a Nokia 7110, running on a Raspberry Pi 3 with a
SIM800C GSM HAT. The phone texts (or calls) the Pi from anywhere; the Pi
answers with WAP pages it stores or builds from the internet.

**Status (13 November 2026):** files prepared, nothing installed on the Pi
yet. The HAT and its SIM are on order. Whether the link will be text
messages or a data call is to be decided by test.

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
| `deploy/install.sh` | Run on the Pi as root: `base`, later `enable-sms +44...` |
| `deploy/kannel.conf` | Kannel core and WAP settings |
| `deploy/sms.conf.hat` | Modem and text-message settings (untested) |
| `deploy/wapserver.py`, `*.service` | Page server and systemd units |
| `deploy/www/` | The WML decks |
| `build-wap-over-sms.sh` | Builds wap-over-sms for the Pi into `deploy/` |

`vendor/` and the built `deploy/wap-over-sms` are not tracked.

## Limits set by the phone

- WML 1.1 only; one fetch at most about 1,400 bytes once compiled.
- Addresses at most about 100 bytes over text messages.
- Use connection type "Temporary", connection security off.

## Still to do

- Restrict the gateway to the owner's phone number before enabling texts.
- Install on the Pi and test Kannel's configuration.
- Test whether the network passes the binary messages.

## Licence

MIT. See `LICENSE`. wap-over-sms and Kannel carry their own licences.
