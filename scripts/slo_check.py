"""Fail the pipeline if the service misses its service level objectives (SLOs).

  python scripts/slo_check.py
The same thresholds drive the CloudWatch alarms and the Datadog monitor in infra/main.tf.
"""
import json
import sys

SLO = {"uptime_pct": 99.9, "error_rate_pct": 1.0, "p95_ms": 300}

with open("results.json", encoding="utf-8") as f:
    r = json.load(f)

checks = [
    (r["uptime_pct"] >= SLO["uptime_pct"], f"Uptime {r['uptime_pct']}% (objective {SLO['uptime_pct']}% or more)"),
    (r["error_rate_pct"] <= SLO["error_rate_pct"], f"Error rate {r['error_rate_pct']}% (objective {SLO['error_rate_pct']}% or less)"),
    (r["p95_ms"] <= SLO["p95_ms"], f"p95 latency {r['p95_ms']} ms (objective {SLO['p95_ms']} ms or less)"),
]
for ok, msg in checks:
    print(f"{'PASS' if ok else 'FAIL'}  {msg}")
sys.exit(0 if all(ok for ok, _ in checks) else 1)
