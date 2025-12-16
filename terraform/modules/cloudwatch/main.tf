# CloudWatch Alarms and Monitoring for DocProf

# SNS Topic for alarm notifications
resource "aws_sns_topic" "alarms" {
  name = "${var.project_name}-${var.environment}-alarms"
  
  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-alarms"
    Component   = "monitoring"
    Function    = "alarm-notifications"
  })
}

# SNS Topic Subscription (email - configure manually or via variable)
resource "aws_sns_topic_subscription" "alarms_email" {
  count     = var.alarm_email != null ? 1 : 0
  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

# CloudWatch Alarm: Bedrock Throttling (Daily Token Quota)
# This alarm triggers when we hit "Too many tokens per day" errors
resource "aws_cloudwatch_metric_alarm" "bedrock_daily_token_quota" {
  alarm_name          = "${var.project_name}-${var.environment}-bedrock-daily-token-quota"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "BedrockDailyTokenQuotaHits"
  namespace           = "DocProf/Custom"
  period              = 300  # 5 minutes
  statistic           = "Sum"
  threshold           = 0  # Alert on any quota hit
  alarm_description   = "Alerts when Bedrock daily token quota limit is hit. This indicates we need to request a quota increase."
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.alarms.arn]

  tags = merge(var.tags, {
    Name      = "${var.project_name}-${var.environment}-bedrock-daily-token-quota"
    Component = "monitoring"
    Function  = "bedrock-quota-alert"
  })
}

# CloudWatch Alarm: Bedrock Throttling Rate (Rate Limits)
# This alarm triggers when we're hitting rate limits frequently
resource "aws_cloudwatch_metric_alarm" "bedrock_throttling_rate" {
  alarm_name          = "${var.project_name}-${var.environment}-bedrock-throttling-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "BedrockThrottlingExceptions"
  namespace           = "DocProf/Custom"
  period              = 300  # 5 minutes
  statistic           = "Sum"
  threshold           = 10  # Alert if more than 10 throttling exceptions in 5 minutes
  alarm_description   = "Alerts when Bedrock rate throttling occurs frequently. May indicate need for quota increase or request rate optimization."
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.alarms.arn]

  tags = merge(var.tags, {
    Name      = "${var.project_name}-${var.environment}-bedrock-throttling-rate"
    Component = "monitoring"
    Function  = "bedrock-rate-alert"
  })
}

# CloudWatch Alarm: Lambda Errors (Bedrock-related Lambdas)
# This catches errors in Lambdas that use Bedrock
resource "aws_cloudwatch_metric_alarm" "bedrock_lambda_errors" {
  alarm_name          = "${var.project_name}-${var.environment}-bedrock-lambda-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300  # 5 minutes
  statistic           = "Sum"
  threshold           = 5  # Alert if more than 5 errors in 5 minutes
  alarm_description   = "Alerts when Lambda functions using Bedrock have errors. May indicate Bedrock quota or API issues."
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = "${var.project_name}-${var.environment}-chapter-summary-processor"
  }

  alarm_actions = [aws_sns_topic.alarms.arn]

  tags = merge(var.tags, {
    Name      = "${var.project_name}-${var.environment}-bedrock-lambda-errors"
    Component = "monitoring"
    Function  = "lambda-error-alert"
  })
}
