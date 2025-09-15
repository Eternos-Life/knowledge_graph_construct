# Neptune Query Proxy Lambda Function
resource "aws_lambda_function" "neptune_query_proxy" {
  filename         = "../lambda-functions/neptune_query_proxy.zip"
  function_name    = "neptune-query-proxy-${var.environment}"
  role            = aws_iam_role.neptune_query_proxy_lambda.arn
  handler         = "neptune_query_proxy.lambda_handler"
  runtime         = "python3.9"
  timeout         = 300  # 5 minutes for complex queries
  memory_size     = 1024

  vpc_config {
    subnet_ids         = data.aws_subnets.default.ids
    security_group_ids = [aws_security_group.lambda_neptune_access.id]
  }

  environment {
    variables = {
      NEPTUNE_ENDPOINT = aws_neptune_cluster.customer_graphs.endpoint
      ENVIRONMENT     = var.environment
      LOG_LEVEL       = "INFO"
    }
  }

  depends_on = [
    aws_iam_role_policy.neptune_query_proxy_lambda,
    aws_cloudwatch_log_group.neptune_query_proxy_lambda,
    aws_neptune_cluster.customer_graphs
  ]

  tags = {
    Name        = "Neptune Query Proxy"
    Environment = var.environment
  }
}

# IAM Role for Neptune Query Proxy Lambda
resource "aws_iam_role" "neptune_query_proxy_lambda" {
  name = "agentic-framework-neptune-query-proxy-lambda-${var.environment}"

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
    Name        = "Neptune Query Proxy Lambda Role"
    Environment = var.environment
  }
}

# IAM Policy for Neptune Query Proxy Lambda
resource "aws_iam_role_policy" "neptune_query_proxy_lambda" {
  name = "neptune-query-proxy-lambda-policy"
  role = aws_iam_role.neptune_query_proxy_lambda.id

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
          "neptune-db:*"
        ]
        Resource = aws_neptune_cluster.customer_graphs.arn
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "cloudwatch:namespace" = "NeptuneQueryProxy"
          }
        }
      }
    ]
  })
}

# Attach VPC execution policy
resource "aws_iam_role_policy_attachment" "neptune_query_proxy_lambda_vpc" {
  role       = aws_iam_role.neptune_query_proxy_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "neptune_query_proxy_lambda" {
  name              = "/aws/lambda/neptune-query-proxy-${var.environment}"
  retention_in_days = var.log_retention_days
  tags = {
    Name        = "Neptune Query Proxy Lambda Logs"
    Environment = var.environment
  }
}

# API Gateway for Neptune Query Proxy
resource "aws_api_gateway_rest_api" "neptune_query_api" {
  name        = "neptune-query-api-${var.environment}"
  description = "API Gateway for Neptune Query Proxy"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = {
    Name        = "Neptune Query API"
    Environment = var.environment
  }
}

# API Gateway Resource
resource "aws_api_gateway_resource" "neptune_query_resource" {
  rest_api_id = aws_api_gateway_rest_api.neptune_query_api.id
  parent_id   = aws_api_gateway_rest_api.neptune_query_api.root_resource_id
  path_part   = "query"
}

# API Gateway Method
resource "aws_api_gateway_method" "neptune_query_method" {
  rest_api_id   = aws_api_gateway_rest_api.neptune_query_api.id
  resource_id   = aws_api_gateway_resource.neptune_query_resource.id
  http_method   = "POST"
  authorization = "NONE"

  request_models = {
    "application/json" = aws_api_gateway_model.neptune_query_model.name
  }
}

# API Gateway Model
resource "aws_api_gateway_model" "neptune_query_model" {
  rest_api_id  = aws_api_gateway_rest_api.neptune_query_api.id
  name         = "NeptuneQueryModel"
  content_type = "application/json"

  schema = jsonencode({
    "$schema" = "http://json-schema.org/draft-04/schema#"
    title     = "Neptune Query Request"
    type      = "object"
    properties = {
      customer_id = {
        type = "string"
      }
      query_type = {
        type = "string"
        enum = ["nodes", "edges", "summary"]
      }
      limit = {
        type    = "integer"
        minimum = 1
        maximum = 1000
      }
    }
    required = ["customer_id"]
  })
}

# API Gateway Integration
resource "aws_api_gateway_integration" "neptune_query_integration" {
  rest_api_id = aws_api_gateway_rest_api.neptune_query_api.id
  resource_id = aws_api_gateway_resource.neptune_query_resource.id
  http_method = aws_api_gateway_method.neptune_query_method.http_method

  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = aws_lambda_function.neptune_query_proxy.invoke_arn
}

# Lambda Permission for API Gateway
resource "aws_lambda_permission" "neptune_query_api_lambda" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.neptune_query_proxy.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.neptune_query_api.execution_arn}/*/*"
}

# API Gateway Deployment
resource "aws_api_gateway_deployment" "neptune_query_deployment" {
  depends_on = [
    aws_api_gateway_method.neptune_query_method,
    aws_api_gateway_integration.neptune_query_integration,
  ]

  rest_api_id = aws_api_gateway_rest_api.neptune_query_api.id
  stage_name  = var.environment

  lifecycle {
    create_before_destroy = true
  }
}

# CORS Support
resource "aws_api_gateway_method" "neptune_query_options" {
  rest_api_id   = aws_api_gateway_rest_api.neptune_query_api.id
  resource_id   = aws_api_gateway_resource.neptune_query_resource.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "neptune_query_options_integration" {
  rest_api_id = aws_api_gateway_rest_api.neptune_query_api.id
  resource_id = aws_api_gateway_resource.neptune_query_resource.id
  http_method = aws_api_gateway_method.neptune_query_options.http_method

  type = "MOCK"
  request_templates = {
    "application/json" = jsonencode({
      statusCode = 200
    })
  }
}

resource "aws_api_gateway_method_response" "neptune_query_options_response" {
  rest_api_id = aws_api_gateway_rest_api.neptune_query_api.id
  resource_id = aws_api_gateway_resource.neptune_query_resource.id
  http_method = aws_api_gateway_method.neptune_query_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "neptune_query_options_integration_response" {
  rest_api_id = aws_api_gateway_rest_api.neptune_query_api.id
  resource_id = aws_api_gateway_resource.neptune_query_resource.id
  http_method = aws_api_gateway_method.neptune_query_options.http_method
  status_code = aws_api_gateway_method_response.neptune_query_options_response.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS,POST,PUT'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# Output API Gateway URL
output "neptune_query_api_url" {
  description = "URL of the Neptune Query API"
  value       = "${aws_api_gateway_deployment.neptune_query_deployment.invoke_url}/query"
}

output "neptune_query_lambda_function_name" {
  description = "Name of the Neptune Query Proxy Lambda function"
  value       = aws_lambda_function.neptune_query_proxy.function_name
}