"""Publish the load test results to CloudWatch as custom metrics, using the AWS CLI on the runner.

  python scripts/publish_cloudwatch.py
The CloudWatch alarms in infra/main.tf watch these metrics.
"""
import json
import subprocess

NAMESPACE = "ObservabilityPlatform"
DIMENSIONS = [{"Name": "Service", "Value": "orders-api"}]

with open("results.json", encoding="utf-8") as f:
    r = json.load(f)

metrics = [
    {"MetricName": "ErrorRate", "Value": r["error_rate_pct"], "Unit": "Percent", "Dimensions": DIMENSIONS},
    {"MetricName": "LatencyP95", "Value": r["p95_ms"], "Unit": "Milliseconds", "Dimensions": DIMENSIONS},
    {"MetricName": "Uptime", "Value": r["uptime_pct"], "Unit": "Percent", "Dimensions": DIMENSIONS},
]
subprocess.run(["aws", "cloudwatch", "put-metric-data", "--namespace", NAMESPACE, "--metric-data", json.dumps(metrics)], check=True)
for m in metrics:
    print(f"{NAMESPACE}/{m['MetricName']} = {m['Value']} {m['Unit']}")
