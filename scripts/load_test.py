"""Send traffic to orders-api, probe /health throughout, and save the results to results.json.

  python scripts/load_test.py [base_url] [requests]
"""
import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
TOTAL = int(sys.argv[2]) if len(sys.argv) > 2 else 400


def call(path):
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(BASE + path, timeout=5) as r:
            status = r.status
    except urllib.error.HTTPError as e:
        status = e.code
    except OSError:
        status = 0  # connection failed: the service was down
    return path, status, (time.perf_counter() - start) * 1000


def main():
    paths = ["/orders" if i % 2 else "/checkout" for i in range(TOTAL)]  # half reads, half checkouts
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(call, paths))
        health = list(pool.map(call, ["/health"] * 50))

    latencies = sorted(ms for _, _, ms in results)
    errors = sum(1 for _, status, _ in results if status >= 500 or status == 0)
    up = sum(1 for _, status, _ in health if status == 200)
    # The same numbers per block of 20 requests, in the order they were sent, for sparklines
    blocks = [results[i:i + 20] for i in range(0, TOTAL, 20)]
    series = {
        "error_rate_pct": [round(sum(1 for _, st, _ in blk if st >= 500 or st == 0) / len(blk) * 100, 1) for blk in blocks],
        "p95_ms": [round(sorted(ms for _, _, ms in blk)[int(len(blk) * 0.95) - 1], 1) for blk in blocks],
    }
    summary = {
        "requests": TOTAL,
        "errors": errors,
        "error_rate_pct": round(errors / TOTAL * 100, 2),
        "p95_ms": round(latencies[int(len(latencies) * 0.95) - 1], 1),
        "uptime_pct": round(up / len(health) * 100, 2),
        "series": series,
    }
    with open("results.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps({k: v for k, v in summary.items() if k != "series"}, indent=2))
    print("error rate per 20 requests:", " ".join(map(str, series["error_rate_pct"])))
    print("p95 ms per 20 requests:    ", " ".join(map(str, series["p95_ms"])))


if __name__ == "__main__":
    main()
