"""Check every request from the load test reached Elasticsearch through Logstash, with its fields parsed.

  python scripts/check_logs.py [elasticsearch_url]
Waits up to 2 minutes for Logstash to catch up, then compares counts with results.json.
"""
import json
import sys
import time
import urllib.request

ES = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:9200"
TRAFFIC = {"terms": {"path.keyword": ["/orders", "/checkout"]}}


def es(path, body=None):
    req = urllib.request.Request(ES + path, data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json"}, method="POST" if body else "GET")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)


def count(query):
    es("/app-logs-*/_refresh", {})
    return es("/app-logs-*/_count", {"query": query})["count"]


def main():
    with open("results.json", encoding="utf-8") as f:
        expected = json.load(f)

    deadline = time.time() + 120
    found = 0
    while time.time() < deadline:
        try:
            found = count(TRAFFIC)
        except OSError:
            found = 0  # index not created yet
        if found >= expected["requests"]:
            break
        print(f"waiting for logs: {found}/{expected['requests']}")
        time.sleep(3)

    errors = count({"bool": {"filter": [TRAFFIC, {"term": {"level.keyword": "error"}}]}})
    mapping = es("/app-logs-*/_field_caps?fields=latency_ms,status")["fields"]
    numeric = all(t in ("long", "float", "double", "integer") for f in mapping.values() for t in f)

    checks = [
        (found == expected["requests"], f"{found}/{expected['requests']} requests indexed in Elasticsearch"),
        (errors == expected["errors"], f"{errors}/{expected['errors']} error logs indexed"),
        (numeric, "latency_ms and status are numbers, so Kibana can chart and filter them"),
    ]
    for ok, msg in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {msg}")
    sys.exit(0 if all(ok for ok, _ in checks) else 1)


if __name__ == "__main__":
    main()
