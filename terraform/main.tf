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
        Resource = "arn:aws:lambda:${var.aws_region}:${local.account_id}:function:agentic-*"
      }
    ]
  })
}

# Step Functions State Machine
resource "aws_sfn_state_machine" "agentic_workflow" {
  name     = "${var.project_name}-processing-workflow-${var.environment}"
  role_arn = aws_iam_role.step_functions_role.arn

  definition = templatefile("${path.module}/../config/step_functions_workflow.json", {
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
