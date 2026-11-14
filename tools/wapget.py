#!/usr/bin/env python3
"""Fetch a page through the WAP gateway the way a phone does.

Sends a connectionless WSP "Get" over UDP (port 9200) and reports the
status and the size of the compiled page that comes back.

    tools/wapget.py GATEWAY URL
"""
import socket
import sys


def uintvar(n):
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.insert(0, 0x80 | (n & 0x7F))
        n >>= 7
    return bytes(out)


def read_uintvar(data, pos):
    value = 0
    while True:
        b = data[pos]
        pos += 1
        value = (value << 7) | (b & 0x7F)
        if not b & 0x80:
            return value, pos


def wap_get(gateway, url, timeout=15):
    uri = url.encode("ascii")
    # What a WAP 1.1 phone says it accepts: compiled WML (not WML text, so the gateway must compile it), WBMP
    # images, and the UTF-8 character set.
    accept = bytes([0x80, 0x94, 0x80, 0xA1, 0x81, 0xEA])
    pdu = bytes([0x01, 0x40]) + uintvar(len(uri)) + uri + accept
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(timeout)
        s.sendto(pdu, (gateway, 9200))
        data, _ = s.recvfrom(65535)
    if len(data) < 4 or data[1] != 0x04:
        raise RuntimeError(f"unexpected reply: {data[:16].hex()}")
    status = data[2]
    hlen, pos = read_uintvar(data, 3)
    return status, data[pos:pos + hlen], data[pos + hlen:]


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    status, headers, body = wap_get(sys.argv[1], sys.argv[2])
    # WSP status 0x20 is HTTP 200.
    print(f"status 0x{status:02x}  headers {headers.hex()}  body {len(body)} bytes")
    # The whole reply datagram, and the text messages it needs at the
    # 110 bytes per message that wap-over-sms uses.
    total = 4 + len(headers) + len(body)
    print(f"reply {total} bytes = {1 if total <= 110 else -(-total // 110)} text(s)")
    print(body[:48].hex())
