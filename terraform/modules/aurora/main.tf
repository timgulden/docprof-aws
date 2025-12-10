# Aurora Serverless v2 PostgreSQL Cluster
# Supports pgvector extension for vector similarity search

# DB Parameter Group (pgvector is enabled as extension, not via shared_preload_libraries)
resource "aws_db_parameter_group" "aurora_postgres" {
  name   = "${var.project_name}-${var.environment}-aurora-postgres"
  family = "aurora-postgresql16"

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-aurora-postgres"
    }
  )
}

# DB Cluster Parameter Group
resource "aws_rds_cluster_parameter_group" "aurora_postgres" {
  name   = "${var.project_name}-${var.environment}-aurora-postgres-cluster"
  family = "aurora-postgresql16"

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-aurora-postgres-cluster"
    }
  )
}

# Aurora Serverless v2 Cluster
resource "aws_rds_cluster" "aurora" {
  cluster_identifier      = "${var.project_name}-${var.environment}-aurora"
  engine                  = "aurora-postgresql"
  engine_version          = "16.6"
  engine_mode             = "provisioned"
  database_name           = var.database_name
  master_username         = var.master_username
  master_password         = random_password.master_password.result
  backup_retention_period = var.backup_retention_period
  preferred_backup_window = "03:00-04:00"
  preferred_maintenance_window = "sun:04:00-sun:05:00"
  
  # Serverless v2 configuration
  # Auto-pause enabled when min_capacity = 0
  serverlessv2_scaling_configuration {
    min_capacity             = var.min_capacity
    max_capacity             = var.max_capacity
    seconds_until_auto_pause = var.min_capacity == 0 ? var.seconds_until_auto_pause : null
  }

  # Network configuration
  db_subnet_group_name   = aws_db_subnet_group.aurora.name
  vpc_security_group_ids = [var.security_group_id]
  
  # Parameter groups
  db_cluster_parameter_group_name = aws_rds_cluster_parameter_group.aurora_postgres.name
  
  # Monitoring
  enabled_cloudwatch_logs_exports = ["postgresql"]
  # Note: monitoring_interval is set at cluster level, not instance level for Serverless v2
  monitoring_interval              = 60
  monitoring_role_arn              = var.monitoring_role_arn
  
  # Backup configuration
  skip_final_snapshot       = var.environment == "dev" ? true : false
  final_snapshot_identifier = var.environment == "dev" ? null : "${var.project_name}-${var.environment}-final-snapshot-${formatdate("YYYY-MM-DD-hhmm", timestamp())}"
  
  # Enable deletion protection only in prod
  deletion_protection = var.environment == "prod" ? true : false

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-aurora-cluster"
    }
  )
}

# DB Subnet Group
resource "aws_db_subnet_group" "aurora" {
  name       = "${var.project_name}-${var.environment}-aurora-subnet-group"
  subnet_ids = var.private_subnet_ids

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-aurora-subnet-group"
    }
  )
}

# Aurora Serverless v2 Instance
resource "aws_rds_cluster_instance" "aurora" {
  identifier         = "${var.project_name}-${var.environment}-aurora-instance-1"
  cluster_identifier = aws_rds_cluster.aurora.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.aurora.engine
  engine_version     = aws_rds_cluster.aurora.engine_version
  
  # Parameter group
  db_parameter_group_name = aws_db_parameter_group.aurora_postgres.name

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-aurora-instance-1"
    }
  )
}

# Random password for master user
# RDS password requirements: Only printable ASCII characters besides '/', '@', '"', ' '
resource "random_password" "master_password" {
  length  = 32
  special = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

# Store master password in AWS Secrets Manager
resource "aws_secretsmanager_secret" "aurora_master_password" {
  name        = "${var.project_name}-${var.environment}-aurora-master-password"
  description = "Master password for Aurora PostgreSQL cluster"

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-aurora-master-password"
    }
  )
}

resource "aws_secretsmanager_secret_version" "aurora_master_password" {
  secret_id     = aws_secretsmanager_secret.aurora_master_password.id
  secret_string = random_password.master_password.result
}

