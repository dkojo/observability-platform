# Applied once from your machine. Sets up the alerting side of the platform:
#   - an IAM role GitHub Actions assumes with OIDC, allowed only to publish metrics and read alarm states
#   - CloudWatch alarms on error rate and p95 latency, alerting the ops-alerts SNS topic
#   - a Datadog monitor on the same error rate
# Your email and Datadog keys go in terraform.tfvars, which is never committed (see terraform.tfvars.example).

terraform {
  required_version = ">= 1.10"
  required_providers {
    aws     = { source = "hashicorp/aws", version = "~> 6.0" }
    datadog = { source = "DataDog/datadog", version = "~> 4.0" }
  }
  backend "s3" {
    bucket       = "danielkojomegbenu-tfstate"
    key          = "observability-platform/terraform.tfstate"
    region       = "us-east-1"
    use_lockfile = true
  }
}

provider "aws" {
  region = "us-east-1"
  default_tags {
    tags = { Project = "observability-platform" }
  }
}

provider "datadog" {
  api_key = var.datadog_api_key
  app_key = var.datadog_app_key
  api_url = "https://api.${var.datadog_site}/"
}

variable "alert_email" {
  description = "Where CloudWatch and Datadog alerts go"
  type        = string
}

variable "datadog_api_key" {
  type      = string
  sensitive = true
}

variable "datadog_app_key" {
  type      = string
  sensitive = true
}

variable "datadog_site" {
  type    = string
  default = "datadoghq.com"
}

# GitHub's OIDC subject for this repo, in its immutable form.
# Find yours with: gh api repos/OWNER/REPO/actions/oidc/customization/sub --jq .sub_claim_prefix
variable "github_sub_prefix" {
  type    = string
  default = "repo:dkojo@167027053/observability-platform@1466522781"
}

locals {
  namespace  = "ObservabilityPlatform"
  dimensions = { Service = "orders-api" }
  # The same objectives as scripts/slo_check.py
  max_error_rate_pct = 1
  max_p95_ms         = 300
}

# ---------- GitHub Actions role ----------

data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}

resource "aws_iam_role" "metrics" {
  name = "github-observability-metrics"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRoleWithWebIdentity"
      Principal = { Federated = data.aws_iam_openid_connect_provider.github.arn }
      Condition = {
        StringEquals = { "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com" }
        StringLike   = { "token.actions.githubusercontent.com:sub" = ["${var.github_sub_prefix}:ref:refs/heads/main", "${var.github_sub_prefix}:pull_request"] }
      }
    }]
  })
}

resource "aws_iam_role_policy" "metrics" {
  name = "publish-metrics-read-alarms"
  role = aws_iam_role.metrics.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Action    = "cloudwatch:PutMetricData"
        Resource  = "*"
        Condition = { StringEquals = { "cloudwatch:namespace" = local.namespace } }
      },
      { Effect = "Allow", Action = "cloudwatch:DescribeAlarms", Resource = "*" },
    ]
  })
}

# ---------- CloudWatch alarms ----------

resource "aws_sns_topic" "ops_alerts" {
  name = "ops-alerts"
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.ops_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_cloudwatch_metric_alarm" "error_rate" {
  alarm_name          = "orders-api-error-rate"
  alarm_description   = "More than ${local.max_error_rate_pct}% of orders-api requests failed"
  namespace           = local.namespace
  metric_name         = "ErrorRate"
  dimensions          = local.dimensions
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 1
  comparison_operator = "GreaterThanThreshold"
  threshold           = local.max_error_rate_pct
  treat_missing_data  = "notBreaching" # no load test running is not an outage
  alarm_actions       = [aws_sns_topic.ops_alerts.arn]
  ok_actions          = [aws_sns_topic.ops_alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "latency" {
  alarm_name          = "orders-api-p95-latency"
  alarm_description   = "orders-api p95 latency is over ${local.max_p95_ms} ms"
  namespace           = local.namespace
  metric_name         = "LatencyP95"
  dimensions          = local.dimensions
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 1
  comparison_operator = "GreaterThanThreshold"
  threshold           = local.max_p95_ms
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.ops_alerts.arn]
  ok_actions          = [aws_sns_topic.ops_alerts.arn]
}

# ---------- Datadog monitor ----------

resource "datadog_monitor" "error_rate" {
  name    = "orders-api error rate above ${local.max_error_rate_pct}%"
  type    = "metric alert"
  query   = "max(last_5m):max:orders_api.error_rate{service:orders-api} > ${local.max_error_rate_pct}"
  message = <<-EOT
    orders-api error rate is {{value}}%, above the ${local.max_error_rate_pct}% objective.
    Search the error logs in Kibana with the saved search "Errors: orders-api" and follow the trace_id.
    @${var.alert_email}
  EOT

  monitor_thresholds {
    critical = local.max_error_rate_pct
  }
  notify_no_data = false
  tags           = ["service:orders-api", "project:observability-platform"]
}

output "role_arn" { value = aws_iam_role.metrics.arn }
output "ops_alerts_topic" { value = aws_sns_topic.ops_alerts.arn }
