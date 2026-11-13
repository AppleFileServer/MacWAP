#!/usr/bin/env python3
"""Tiny page server for the WAP gateway.

Serves the files in /srv/wap to Kannel's wapbox on this machine only
(127.0.0.1:8088), with the content types WAP needs. Kannel compiles the
WML to binary before it goes to the phone.
"""
import http.server
import os
import sys

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

    def do_GET(self):
        if self.path in ("", "/"):
            self.path = "/index.wml"
        super().do_GET()

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
