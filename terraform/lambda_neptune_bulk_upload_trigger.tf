# Neptune Bulk Upload Trigger Lambda Function
resource "aws_lambda_function" "neptune_bulk_upload_trigger" {
  filename         = "../lambda-functions/neptune_bulk_upload_trigger.zip"
  function_name    = "neptune-bulk-upload-trigger-${var.environment}"
  role            = aws_iam_role.neptune_bulk_upload_trigger_lambda.arn
  handler         = "neptune_bulk_upload_trigger.lambda_handler"
  runtime         = "python3.9"
  timeout         = 900  # 15 minutes for bulk operations
  memory_size     = 1024

  environment {
    variables = {
      ENVIRONMENT = var.environment
      LOG_LEVEL   = "INFO"
      CUSTOMER_GRAPHS_BUCKET = aws_s3_bucket.customer_graphs.bucket
    }
  }

  depends_on = [
    aws_iam_role_policy.neptune_bulk_upload_trigger_lambda,
    aws_iam_role_policy_attachment.neptune_bulk_upload_trigger_lambda_policy,
    aws_cloudwatch_log_group.neptune_bulk_upload_trigger_lambda,
  ]

  tags = {
    Name        = "Neptune Bulk Upload Trigger"
    Environment = var.environment
  }
}

# IAM Role for Neptune Bulk Upload Trigger Lambda
resource "aws_iam_role" "neptune_bulk_upload_trigger_lambda" {
  name = "agentic-framework-neptune-bulk-upload-trigger-lambda-${var.environment}"

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

  tags = {
    Name        = "Neptune Bulk Upload Trigger Lambda Role"
    Environment = var.environment
  }
}

# IAM Policy for Neptune Bulk Upload Trigger Lambda
resource "aws_iam_role_policy" "neptune_bulk_upload_trigger_lambda" {
  name = "neptune-bulk-upload-trigger-lambda-policy"
  role = aws_iam_role.neptune_bulk_upload_trigger_lambda.id

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
        Resource = "arn:aws:logs:${var.aws_region}:${local.account_id}:*"
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
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
      }
    ]
  })
}

# Attach basic Lambda execution policy
resource "aws_iam_role_policy_attachment" "neptune_bulk_upload_trigger_lambda_policy" {
  role       = aws_iam_role.neptune_bulk_upload_trigger_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "neptune_bulk_upload_trigger_lambda" {
  name              = "/aws/lambda/neptune-bulk-upload-trigger-${var.environment}"
  retention_in_days = 14
  tags = {
    Name        = "Neptune Bulk Upload Trigger Lambda Logs"
    Environment = var.environment
  }
}
