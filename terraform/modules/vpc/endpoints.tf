# VPC Endpoints for AWS Services
# VPC endpoints allow private resources to access AWS services without going through the internet

# Security group for VPC endpoints (always created)
resource "aws_security_group" "vpc_endpoints" {
  name        = "${var.project_name}-${var.environment}-vpc-endpoints-sg"
  description = "Security group for VPC endpoints - allows HTTPS from Lambda"
  vpc_id      = aws_vpc.main.id

  # Allow inbound HTTPS from Lambda security group
  ingress {
    description     = "HTTPS from Lambda"
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [aws_security_group.lambda.id]
  }

  # Allow outbound (required for endpoint functionality)
  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-vpc-endpoints-sg"
    }
  )

  lifecycle {
    create_before_destroy = true
  }
}

# Data source for current AWS region
data "aws_region" "current" {}

# VPC Endpoint for Bedrock Runtime - CONDITIONAL (on-demand)
# count = 0 means resource doesn't exist, count = 1 means resource is created
resource "aws_vpc_endpoint" "bedrock_runtime" {
  count = var.enable_ai_endpoints ? 1 : 0

  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.bedrock-runtime"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true

  tags = merge(
    var.tags,
    {
      Name     = "${var.project_name}-${var.environment}-bedrock-runtime-endpoint"
      Service  = "bedrock-runtime"
      OnDemand = "true"
    }
  )
}

# VPC Endpoint for Polly - CONDITIONAL (on-demand)
resource "aws_vpc_endpoint" "polly" {
  count = var.enable_ai_endpoints ? 1 : 0

  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.polly"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true

  tags = merge(
    var.tags,
    {
      Name     = "${var.project_name}-${var.environment}-polly-endpoint"
      Service  = "polly"
      OnDemand = "true"
    }
  )
}

# S3 Gateway Endpoint - ALWAYS ON (FREE)
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${data.aws_region.current.name}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = concat([aws_route_table.public.id], [aws_route_table.private.id])

  tags = merge(
    var.tags,
    {
      Name    = "${var.project_name}-${var.environment}-s3-endpoint"
      Service = "s3"
    }
  )
}

# DynamoDB Gateway Endpoint - ALWAYS ON (FREE)
resource "aws_vpc_endpoint" "dynamodb" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${data.aws_region.current.name}.dynamodb"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = concat([aws_route_table.public.id], [aws_route_table.private.id])

  tags = merge(
    var.tags,
    {
      Name    = "${var.project_name}-${var.environment}-dynamodb-endpoint"
      Service = "dynamodb"
    }
  )
}

# Secrets Manager Interface Endpoint - ALWAYS ON (Required for Lambda to access DB password)
resource "aws_vpc_endpoint" "secretsmanager" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.secretsmanager"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true

  tags = merge(
    var.tags,
    {
      Name    = "${var.project_name}-${var.environment}-secretsmanager-endpoint"
      Service = "secretsmanager"
      Required = "true"
    }
  )
}
