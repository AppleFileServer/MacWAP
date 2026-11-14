#!/usr/bin/env python3
"""Sorts incoming text messages for the WAP gateway.

Kannel's smsbox posts every incoming message here (127.0.0.1:8090).

- A WAP request (a binary message carrying port numbers) from the one
  allowed phone is passed on to wap-over-sms, which turns it into a
  request to Kannel's wapbox and sends the reply back as messages.
- A WAP request from any other number is dropped and noted.
- An ordinary text from anyone (the network's own notices, verification
  codes, and so on) is kept in an inbox file. It is never answered.

Replies only ever go to the allowed phone, so a forged sender number
gains nothing: the answer still travels to the real phone.

Environment (from /etc/wapgateway/sms.env):
    TOKEN     shared secret in the address Kannel posts to
    ALLOWED   regular expression matching the allowed phone's number
"""
import datetime
import http.server
import os
import re
import sys
import urllib.parse
import urllib.request

import smscmd

HOST, PORT = "127.0.0.1", 8090
RELAY = "http://127.0.0.1:8089/kannel"           # wap-over-sms
STATE = os.environ.get("STATE_DIRECTORY", "/var/lib/wapgateway")
INBOX = os.path.join(STATE, "sms-inbox.tsv")
TOKEN = os.environ.get("TOKEN", "")
ALLOWED = re.compile(os.environ.get("ALLOWED") or r"^\b$")   # default: nobody

# Replies are sent back through Kannel's smsbox (the sendsms HTTP API).
SENDSMS = os.environ.get("SENDSMS_URL", "http://127.0.0.1:13014/cgi-bin/sendsms")
SENDSMS_USER = os.environ.get("SENDSMS_USER", "wapsms")
SENDSMS_PASS = os.environ.get("SENDSMS_PASSWORD", "")
# Kannel's sendsms needs a sender address; the SIM's own number serves (the
# network uses the SIM's real number regardless).
SENDER = os.environ.get("SENDSMS_FROM") or os.environ.get("MODEM_NUMBER", "")


def send_sms(to, text):
    """Send one plain text through smsbox. Never logs the number, the text
    or the URL (it carries the password)."""
    fields = {"username": SENDSMS_USER, "password": SENDSMS_PASS, "to": to, "text": text}
    if SENDER:
        fields["from"] = SENDER
    query = urllib.parse.urlencode(fields)
    try:
        with urllib.request.urlopen(SENDSMS + "?" + query, timeout=15) as r:
            r.read()
    except Exception as e:
        print("wapsms: sendsms failed:", type(e).__name__, file=sys.stderr)


def is_wap(udh):
    """True if the user-data header carries port addressing (element 05
    or 04), which is how WAP data is marked."""
    i = 1
    while i + 1 < len(udh):
        ident, length = udh[i], udh[i + 1]
        if ident in (0x04, 0x05):
            return True
        i += 2 + length
    return False


def keep(sender, text):
    text = " ".join(text.split())
    now = datetime.datetime.now().replace(microsecond=0).isoformat(sep=" ")
    with open(INBOX, "a", encoding="utf-8") as f:
        f.write(f"{now}\t{sender}\t{text}\n")


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass                      # never log message contents or numbers

    def reply(self, code):
        self.send_response_only(code)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        parts = urllib.parse.urlsplit(self.path)
        token = urllib.parse.parse_qs(parts.query).get("token", [""])[0]
        if parts.path != "/in" or not TOKEN or token != TOKEN:
            return self.reply(403)
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        sender = self.headers.get("X-Kannel-From", "")
        udh = urllib.parse.unquote_to_bytes(self.headers.get("X-Kannel-UDH", ""))

        if udh and is_wap(udh):
            if not ALLOWED.search(sender):
                keep(sender, "[WAP request from a number not allowed; dropped]")
                return self.reply(200)
            headers = {k: v for k, v in self.headers.items()
                       if k.lower().startswith("x-kannel-") or k.lower() == "content-type"}
            req = urllib.request.Request(
                RELAY + "?token=" + urllib.parse.quote(TOKEN),
                data=body, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=10) as r:
                    r.read()
            except Exception as e:
                print(f"wapsms: relay failed: {e!r}", file=sys.stderr)
            return self.reply(200)

        charset = self.headers.get_content_charset() or "utf-8"
        try:
            text = body.decode(charset, "replace")
        except LookupError:
            text = body.decode("latin-1")

        # An ordinary text from the allowed phone is a command: answer it
        # and do not file it. Everything else (carrier notices, verification
        # codes, texts from other numbers) goes to the inbox, unanswered.
        if not udh and ALLOWED.search(sender):
            try:
                replies = smscmd.handle(text)
            except Exception as e:
                print("wapsms: command failed:", type(e).__name__, file=sys.stderr)
                replies = ["Sorry, that failed."]
            for msg in replies:
                send_sms(sender, msg)
            return self.reply(200)

        keep(sender, text if not udh else "[binary message, not WAP]")
        self.reply(200)           # empty body: Kannel sends no answer


if __name__ == "__main__":
    os.makedirs(STATE, exist_ok=True)
    print(f"wapsms: listening on {HOST}:{PORT}", file=sys.stderr)
    http.server.ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
