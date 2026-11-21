"""orders-api: a tiny web service that writes one structured JSON log line per request.

Only the Python standard library, so there is nothing to install.
  GET /health    always 200
  GET /orders    a list of orders
  GET /checkout  simulates a payment; every FAIL_EVERY-th checkout fails with a 500
"""
import json
import os
import random
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SERVICE = "orders-api"
FAIL_EVERY = 200  # 1 failed checkout in 200, a 0.5% error rate on checkout
ORDERS = [
    {"id": 1, "item": "keyboard", "total": 49.99},
    {"id": 2, "item": "monitor", "total": 189.00},
    {"id": 3, "item": "headset", "total": 79.50},
]

_checkouts = 0
_lock = threading.Lock()
_log_file = None


def handle(path, checkout_no=0):
    """Pure request logic: returns (status, body, level, message). Easy to unit test."""
    if path == "/health":
        return 200, {"status": "ok"}, "info", "health check"
    if path == "/orders":
        return 200, ORDERS, "info", "listed orders"
    if path == "/checkout":
        if checkout_no % FAIL_EVERY == 0:
            return 500, {"error": "payment provider timeout"}, "error", "checkout failed: payment provider timeout"
        return 200, {"status": "paid"}, "info", "checkout paid"
    return 404, {"error": "not found"}, "warn", "unknown path"


def log_line(method, path, status, latency_ms, level, message):
    """One JSON object per line: Logstash parses it into fields without any regex."""
    return json.dumps({
        "time": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "service": SERVICE,
        "level": level,
        "method": method,
        "path": path,
        "status": status,
        "latency_ms": round(latency_ms, 1),
        "trace_id": uuid.uuid4().hex[:16],
        "message": message,
    })


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        global _checkouts
        start = time.perf_counter()
        path = self.path.split("?")[0]
        number = 0
        if path == "/checkout":
            with _lock:
                _checkouts += 1
                number = _checkouts
            time.sleep(random.uniform(0.02, 0.08))  # pretend to call a payment provider
        status, body, level, message = handle(path, number)
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
        line = log_line("GET", path, status, (time.perf_counter() - start) * 1000, level, message)
        print(line, flush=True)
        if _log_file:
            _log_file.write(line + "\n")
            _log_file.flush()

    def log_message(self, *args):  # the JSON line above replaces the default access log
        pass


def main():
    global _log_file
    path = os.environ.get("LOG_FILE")
    if path:
        _log_file = open(path, "a", encoding="utf-8")
    port = int(os.environ.get("PORT", "8080"))
    print(json.dumps({"service": SERVICE, "level": "info", "message": f"listening on :{port}"}), file=sys.stderr, flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
