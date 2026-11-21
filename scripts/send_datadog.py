"""Send the load test results to Datadog as metrics, plus one event describing the run.

  DD_API_KEY=... DD_SITE=datadoghq.com python scripts/send_datadog.py
The Datadog monitor in infra/main.tf alerts on orders_api.error_rate.
"""
import json
import os
import sys
import time
import urllib.request

SITE = os.environ.get("DD_SITE") or "datadoghq.com"
KEY = os.environ["DD_API_KEY"]
TAGS = ["service:orders-api", "env:ci"]


def post(path, body):
    req = urllib.request.Request(f"https://api.{SITE}{path}", data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "DD-API-KEY": KEY})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.status


with open("results.json", encoding="utf-8") as f:
    r = json.load(f)

now = int(time.time())
series = [
    {"metric": name, "type": 3, "points": [{"timestamp": now, "value": value}], "tags": TAGS}  # type 3 = gauge
    for name, value in [("orders_api.error_rate", r["error_rate_pct"]), ("orders_api.latency.p95", r["p95_ms"]),
                        ("orders_api.uptime", r["uptime_pct"])]
]
status = post("/api/v2/series", {"series": series})
print(f"metrics: orders_api.error_rate, .latency.p95, .uptime -> HTTP {status}")

run = os.environ.get("GITHUB_RUN_NUMBER", "local")
event = {
    "title": f"orders-api load test, run #{run}",
    "text": f"{r['requests']} requests, {r['errors']} errors ({r['error_rate_pct']}%), p95 {r['p95_ms']} ms, uptime {r['uptime_pct']}%",
    "alert_type": "error" if r["error_rate_pct"] > 1 else "success",
    "tags": TAGS,
}
status_ev = post("/api/v1/events", event)
print(f"event: {event['title']} -> HTTP {status_ev}")
sys.exit(0 if status in (200, 202) and status_ev in (200, 202) else 1)
