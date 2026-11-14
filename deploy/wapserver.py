#!/usr/bin/env python3
"""Tiny page server for the WAP gateway.

Serves the files in /srv/wap to Kannel's wapbox on this machine only
(127.0.0.1:8088), with the content types WAP needs. Kannel compiles the
WML to binary before it goes to the phone.
"""
import http.server
import os
import sys
import urllib.parse

import wapapp

ROOT = os.environ.get("WAP_ROOT", "/srv/wap")
HOST = os.environ.get("WAP_HOST", "127.0.0.1")
PORT = int(os.environ.get("WAP_PORT", "8088"))


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        ".wml": "text/vnd.wap.wml",
        ".wbmp": "image/vnd.wap.wbmp",
        ".wmls": "text/vnd.wap.wmlscript",
        "": "application/octet-stream",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def app(self, query=None):
        """Answer from wapapp (Today, Calories, Cash) if the address is
        one of its routes. Returns True if it did."""
        parts = urllib.parse.urlsplit(self.path)
        try:
            text = wapapp.handle(parts.path.strip("/"),
                                 parts.query if query is None else query)
        except Exception as e:           # never leave the phone waiting
            print(f"wapserver: {parts.path}: {e!r}", file=sys.stderr)
            text = wapapp.wf.deck([("e", "Error", "Sorry, that failed.")])
        if text is None:
            return False
        data = text.encode("ascii")
        self.send_response(200)
        self.send_header("Content-type", "text/vnd.wap.wml")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
        return True

    def do_POST(self):
        # Forms may post their fields; the phone never caches a post.
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(min(length, 2000)).decode("ascii", "replace")
        if not self.app(body):
            self.send_error(404, "No such page")

    def do_GET(self):
        if self.app():
            return
        if self.path in ("", "/"):
            self.path = "/index.wml"
        elif "." not in self.path.rsplit("/", 1)[-1] and "?" not in self.path:
            # Short addresses: /w is /w.wml. Every byte of an address
            # travels in the request.
            self.path += ".wml"
        super().do_GET()

    # Every reply header Kannel sees is passed on to the phone, and over
    # text messages each byte counts. Leave out Server and Date (about 36
    # bytes) and Last-Modified (6 bytes); the phone needs none of them.
    def send_response(self, code, message=None):
        self.log_request(code)
        self.send_response_only(code, message)

    def send_header(self, keyword, value):
        if keyword.lower() == "last-modified":
            return
        super().send_header(keyword, value)

    def end_headers(self):
        # The 7110 caches aggressively; ask it not to.
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def list_directory(self, path):
        self.send_error(404, "No such page")
        return None


if __name__ == "__main__":
    server = http.server.ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"wapserver: serving {ROOT} on {HOST}:{PORT}", file=sys.stderr)
    server.serve_forever()
