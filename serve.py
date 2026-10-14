#!/usr/bin/env python3
"""Local web server for the browser version.   python3 serve.py [--port 8765] [--no-open]

Serves ./web (static files) and a tiny JSON endpoint:  POST /api  {"cmd": "...", "args": {...}}
The game state lives in this Python process; the browser keeps the save in localStorage and re-sends it
when the page loads, so restarting the server never loses progress. 127.0.0.1 only, no internet needed.
"""
import argparse
import json
import mimetypes
import os
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from slime_gacha.registry import load_plugins
from slime_gacha.webapi import Session

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
SESSION = Session()
LOCK = threading.Lock()
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("application/wasm", ".wasm")


class Handler(BaseHTTPRequestHandler):
    server_version = "SlimeGacha/0.7"

    def log_message(self, fmt, *args):      # keep the console quiet
        pass

    def _send(self, code: int, body: bytes, ctype: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/ping":
            return self._send(200, b'{"ok": true, "backend": "python-server"}')
        rel = "index.html" if path in ("", "/") else path.lstrip("/")
        full = os.path.normpath(os.path.join(ROOT, rel))
        if not full.startswith(ROOT) or not os.path.isfile(full):
            return self._send(404, b"not found", "text/plain")
        with open(full, "rb") as f:
            data = f.read()
        self._send(200, data, mimetypes.guess_type(full)[0] or "application/octet-stream")

    def do_POST(self):
        if self.path != "/api":
            return self._send(404, b"not found", "text/plain")
        try:
            n = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(n) or b"{}")
            with LOCK:
                res = SESSION.call(str(req.get("cmd", "")), req.get("args") or {})
            self._send(200, json.dumps(res).encode())
        except Exception as e:                       # never leave the browser hanging
            self._send(500, json.dumps(dict(ok=False, error=f"Server error: {e}", log=[], result={},
                                            state=None, save=None)).encode())


def main() -> None:
    ap = argparse.ArgumentParser(description="Slime Gacha - browser edition")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--no-open", action="store_true", help="don't open a browser tab")
    args = ap.parse_args()
    load_plugins()
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}/"
    print(f"Slime Gacha is running at {url}  (Ctrl+C to stop)")
    if not args.no_open:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nBye, Keeper.")


if __name__ == "__main__":
    main()
