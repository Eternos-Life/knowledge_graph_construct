terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region  = var.aws_region
  profile = "development"
}

data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
}

# S3 Buckets
resource "aws_s3_bucket" "input_files" {
  bucket = "${var.project_name}-input-files-${var.environment}-${local.account_id}"
}

resource "aws_s3_bucket_versioning" "input_files" {
  bucket = aws_s3_bucket.input_files.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket" "processed_data" {
  bucket = "${var.project_name}-processed-data-${var.environment}-${local.account_id}"
}

resource "aws_s3_bucket" "q_tables" {
  bucket = "${var.project_name}-q-tables-${var.environment}-${local.account_id}"
}

# DynamoDB Tables
resource "aws_dynamodb_table" "agent_performance" {
  name           = "agent-performance-metrics"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "execution_id"
  range_key      = "agent_type"

  attribute {
    name = "execution_id"
    type = "S"
  }

  attribute {
    name = "agent_type"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  global_secondary_index {
    name            = "agent-type-timestamp-index"
    hash_key        = "agent_type"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Name        = "AgentPerformanceMetrics"
    Environment = var.environment
  }
}

resource "aws_dynamodb_table" "agent_experiences" {
  name           = "agent-experiences"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "experience_id"

  attribute {
    name = "experience_id"
    type = "S"
  }

  attribute {
    name = "agent_type"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  global_secondary_index {
    name            = "agent-type-timestamp-index"
    hash_key        = "agent_type"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Name        = "AgentExperiences"
    Environment = var.environment
  }
}

# IAM Roles for Lambda Functions
resource "aws_iam_role" "lambda_execution_role" {
  name = "${var.project_name}-lambda-execution-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_policy" {
  name = "${var.project_name}-lambda-policy-${var.environment}"
  role = aws_iam_role.lambda_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.input_files.arn,
          "${aws_s3_bucket.input_files.arn}/*",
          aws_s3_bucket.processed_data.arn,
          "${aws_s3_bucket.processed_data.arn}/*",
          aws_s3_bucket.q_tables.arn,
          "${aws_s3_bucket.q_tables.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem"
        ]
        Resource = [
          aws_dynamodb_table.agent_performance.arn,
          "${aws_dynamodb_table.agent_performance.arn}/index/*",
          aws_dynamodb_table.agent_experiences.arn,
          "${aws_dynamodb_table.agent_experiences.arn}/index/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel"
        ]
        Resource = "arn:aws:bedrock:*:*:model/meta.llama3-2-8b-instruct-v1:0"
      }
    ]
  })
}

# Step Functions State Machine Role
resource "aws_iam_role" "step_functions_role" {
  name = "${var.project_name}-step-functions-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "states.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "step_functions_policy" {
  name = "${var.project_name}-step-functions-policy-${var.environment}"
  role = aws_iam_role.step_functions_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = [
          "arn:aws:lambda:${var.aws_region}:${local.account_id}:function:agentic-*",
          "arn:aws:lambda:${var.aws_region}:${local.account_id}:function:graph-extraction-*",
          "arn:aws:lambda:${var.aws_region}:${local.account_id}:function:neptune-persistence-*",
          "arn:aws:lambda:${var.aws_region}:${local.account_id}:function:enhanced-hypergraph-*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:UpdateItem"
        ]
        Resource = [
          aws_dynamodb_table.agent_performance.arn,
          aws_dynamodb_table.agent_experiences.arn
        ]
      }
    ]
  })
}

# Customer Graph Storage S3 Bucket
resource "aws_s3_bucket" "customer_graphs" {
  bucket = "${var.project_name}-customer-graphs-${var.environment}-${local.account_id}"

  tags = {
    Name        = "Customer Graph Storage"
    Environment = var.environment
    Purpose     = "graph-persistence"
  }
}

resource "aws_s3_bucket_versioning" "customer_graphs" {
  bucket = aws_s3_bucket.customer_graphs.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "customer_graphs" {
  bucket = aws_s3_bucket.customer_graphs.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.customer_graphs.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "customer_graphs" {
  bucket = aws_s3_bucket.customer_graphs.id

  rule {
    id     = "customer_graph_lifecycle"
    status = "Enabled"

    filter {
      prefix = "customer-graphs/"
    }

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    transition {
      days          = 365
      storage_class = "DEEP_ARCHIVE"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "customer_graphs" {
  bucket = aws_s3_bucket.customer_graphs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# KMS Key for Customer Graph Encryption
resource "aws_kms_key" "customer_graphs" {
  description             = "KMS key for customer graph data encryption"
  deletion_window_in_days = 7

  tags = {
    Name        = "CustomerGraphsKMSKey"
    Environment = var.environment
  }
}

resource "aws_kms_alias" "customer_graphs" {
  name          = "alias/${var.project_name}-customer-graphs-${var.environment}"
  target_key_id = aws_kms_key.customer_graphs.key_id
}

# Neptune Subnet Group
resource "aws_neptune_subnet_group" "customer_graphs" {
  name       = "${var.project_name}-neptune-subnet-group-${var.environment}"
  subnet_ids = data.aws_subnets.default.ids

  tags = {
    Name        = "Customer Graphs Neptune Subnet Group"
    Environment = var.environment
  }
}

# Neptune Cluster Parameter Group
resource "aws_neptune_cluster_parameter_group" "customer_graphs" {
  family = "neptune1.4"
  name   = "${var.project_name}-neptune-cluster-params-${var.environment}"

  tags = {
    Name        = "Customer Graphs Neptune Cluster Parameters"
    Environment = var.environment
  }
}

# Neptune Cluster
resource "aws_neptune_cluster" "customer_graphs" {
  cluster_identifier                  = "${var.project_name}-neptune-${var.environment}"
  engine                             = "neptune"
  backup_retention_period            = 7
  preferred_backup_window            = "07:00-09:00"
  preferred_maintenance_window       = "sun:05:00-sun:06:00"
  skip_final_snapshot               = var.environment == "dev" ? true : false
  final_snapshot_identifier         = var.environment == "dev" ? null : "${var.project_name}-neptune-final-snapshot-${var.environment}"
  storage_encrypted                 = true
  neptune_subnet_group_name         = aws_neptune_subnet_group.customer_graphs.name
  neptune_cluster_parameter_group_name = aws_neptune_cluster_parameter_group.customer_graphs.name
  vpc_security_group_ids            = [aws_security_group.neptune.id]
  apply_immediately                 = var.environment == "dev" ? true : false
  deletion_protection               = var.environment == "prod" ? true : false

  tags = {
    Name        = "Customer Graphs Neptune Cluster"
    Environment = var.environment
  }
}

# Neptune Cluster Instance
resource "aws_neptune_cluster_instance" "customer_graphs" {
  count              = var.neptune_instance_count
  identifier         = "${var.project_name}-neptune-${var.environment}-${count.index}"
  cluster_identifier = aws_neptune_cluster.customer_graphs.id
  instance_class     = var.neptune_instance_class
  engine             = "neptune"

  tags = {
    Name        = "Customer Graphs Neptune Instance ${count.index}"
    Environment = var.environment
  }
}

# Security Group for Neptune
resource "aws_security_group" "neptune" {
  name_prefix = "${var.project_name}-neptune-${var.environment}-"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    from_port       = 8182
    to_port         = 8182
    protocol        = "tcp"
    security_groups = [aws_security_group.lambda_neptune_access.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "Neptune Security Group"
    Environment = var.environment
  }
}

# Security Group for Lambda to access Neptune
resource "aws_security_group" "lambda_neptune_access" {
  name_prefix = "${var.project_name}-lambda-neptune-${var.environment}-"
  vpc_id      = data.aws_vpc.default.id

  egress {
    from_port   = 8182
    to_port     = 8182
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.default.cidr_block]
  }

  egress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "Lambda Neptune Access Security Group"
    Environment = var.environment
  }
}

# IAM Role for Neptune Monitoring
resource "aws_iam_role" "neptune_monitoring" {
  name = "${var.project_name}-neptune-monitoring-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "neptune_monitoring" {
  role       = aws_iam_role.neptune_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

# IAM Role for Graph Extraction Lambda
resource "aws_iam_role" "graph_extraction_lambda" {
  name = "${var.project_name}-graph-extraction-lambda-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "graph_extraction_lambda" {
  name = "${var.project_name}-graph-extraction-lambda-policy-${var.environment}"
  role = aws_iam_role.graph_extraction_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${local.account_id}:log-group:/aws/lambda/graph-extraction-*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.customer_graphs.arn,
          "${aws_s3_bucket.customer_graphs.arn}/*",
          aws_s3_bucket.processed_data.arn,
          "${aws_s3_bucket.processed_data.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = aws_kms_key.customer_graphs.arn
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "cloudwatch:namespace" = ["CustomerGraphs/Extraction", "CustomerGraphPersistence"]
          }
        }
      }
    ]
  })
}

# IAM Role for Neptune Persistence Lambda
resource "aws_iam_role" "neptune_persistence_lambda" {
  name = "${var.project_name}-neptune-persistence-lambda-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "neptune_persistence_lambda" {
  name = "${var.project_name}-neptune-persistence-lambda-policy-${var.environment}"
  role = aws_iam_role.neptune_persistence_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${local.account_id}:log-group:/aws/lambda/neptune-persistence-*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.customer_graphs.arn,
          "${aws_s3_bucket.customer_graphs.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt"
        ]
        Resource = aws_kms_key.customer_graphs.arn
      },
      {
        Effect = "Allow"
        Action = [
          "neptune-db:*"
        ]
        Resource = aws_neptune_cluster.customer_graphs.arn
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DeleteNetworkInterface",
          "ec2:AttachNetworkInterface",
          "ec2:DetachNetworkInterface"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "cloudwatch:namespace" = "CustomerGraphs/Neptune"
          }
        }
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:UpdateItem",
          "dynamodb:PutItem"
        ]
        Resource = [
          aws_dynamodb_table.agent_performance.arn,
          aws_dynamodb_table.agent_experiences.arn
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "neptune_persistence_lambda_vpc" {
  role       = aws_iam_role.neptune_persistence_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

# Graph Extraction Lambda Function
resource "aws_lambda_function" "graph_extraction_agent" {
  filename         = "../lambda-functions/graph_extraction_agent.zip"
  function_name    = "graph-extraction-agent-${var.environment}"
  role            = aws_iam_role.graph_extraction_lambda.arn
  handler         = "graph_extraction_agent.lambda_handler"
  runtime         = "python3.9"
  timeout         = 300
  memory_size     = 512

  environment {
    variables = {
      CUSTOMER_GRAPHS_BUCKET = aws_s3_bucket.customer_graphs.bucket
      ENVIRONMENT           = var.environment
      LOG_LEVEL            = "INFO"
    }
  }

  depends_on = [
    aws_iam_role_policy.graph_extraction_lambda,
    aws_cloudwatch_log_group.graph_extraction_lambda
  ]

  tags = {
    Name        = "Graph Extraction Agent"
    Environment = var.environment
  }
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "graph_extraction_lambda" {
  name              = "/aws/lambda/graph-extraction-agent-${var.environment}"
  retention_in_days = var.log_retention_days

  tags = {
    Name        = "Graph Extraction Lambda Logs"
    Environment = var.environment
  }
}

resource "aws_cloudwatch_log_group" "neptune_persistence_lambda" {
  name              = "/aws/lambda/neptune-persistence-agent-${var.environment}"
  retention_in_days = var.log_retention_days

  tags = {
    Name        = "Neptune Persistence Lambda Logs"
    Environment = var.environment
  }
}

# CloudWatch Custom Metrics and Alarms
resource "aws_cloudwatch_metric_alarm" "graph_extraction_errors" {
  alarm_name          = "${var.project_name}-graph-extraction-errors-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "This metric monitors graph extraction lambda errors"
  alarm_actions       = var.environment == "prod" ? [aws_sns_topic.alerts[0].arn] : []

  dimensions = {
    FunctionName = "graph-extraction-agent-${var.environment}"
  }

  tags = {
    Name        = "Graph Extraction Errors Alarm"
    Environment = var.environment
  }
}

resource "aws_cloudwatch_metric_alarm" "neptune_persistence_errors" {
  alarm_name          = "${var.project_name}-neptune-persistence-errors-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "This metric monitors neptune persistence lambda errors"
  alarm_actions       = var.environment == "prod" ? [aws_sns_topic.alerts[0].arn] : []

  dimensions = {
    FunctionName = "neptune-persistence-agent-${var.environment}"
  }

  tags = {
    Name        = "Neptune Persistence Errors Alarm"
    Environment = var.environment
  }
}

resource "aws_cloudwatch_metric_alarm" "neptune_cpu_utilization" {
  alarm_name          = "${var.project_name}-neptune-cpu-utilization-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/Neptune"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors neptune CPU utilization"
  alarm_actions       = var.environment == "prod" ? [aws_sns_topic.alerts[0].arn] : []

  dimensions = {
    DBClusterIdentifier = aws_neptune_cluster.customer_graphs.cluster_identifier
  }

  tags = {
    Name        = "Neptune CPU Utilization Alarm"
    Environment = var.environment
  }
}

# SNS Topic for Alerts (only in production)
resource "aws_sns_topic" "alerts" {
  count = var.environment == "prod" ? 1 : 0
  name  = "${var.project_name}-alerts-${var.environment}"

  tags = {
    Name        = "Customer Graphs Alerts"
    Environment = var.environment
  }
}

# Data sources for VPC and Subnets
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# Step Functions State Machine
resource "aws_sfn_state_machine" "agentic_workflow" {
  name     = "${var.project_name}-processing-workflow-${var.environment}"
  role_arn = aws_iam_role.step_functions_role.arn

  definition = templatefile("${path.module}/../config/customer_aware_workflow.json", {
    account_id = local.account_id
    region     = var.aws_region
    environment = var.environment
  })

  depends_on = [
    aws_iam_role_policy.step_functions_policy
  ]

  tags = {
    Name        = "Agentic Processing Workflow"
    Environment = var.environment
  }
}
