# Deployment Guide

## Enhanced Digital Twin Agentic Framework

This guide provides step-by-step instructions for deploying the Enhanced Digital Twin Agentic Framework to AWS.

## 📋 Prerequisites

### Required Tools
- **AWS CLI** v2.0 or later
- **Terraform** v1.0 or later
- **Python** 3.9 or later
- **Git** for version control
- **Zip** utility for Lambda packaging

### AWS Account Requirements
- AWS account with administrative access
- AWS CLI configured with appropriate profile
- Sufficient service limits for:
  - Lambda functions (5+ functions)
  - Step Functions (1 state machine)
  - DynamoDB tables (2 tables)
  - S3 buckets (3 buckets)

### Permissions Required
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "lambda:*",
        "states:*",
        "s3:*",
        "dynamodb:*",
        "iam:*",
        "bedrock:*",
        "logs:*"
      ],
      "Resource": "*"
    }
  ]
}
```

## 🚀 Quick Deployment

### Option 1: Automated Deployment (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/Eternos-Life/knowledge_graph_construct.git
cd knowledge_graph_construct

# 2. Set up environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Configure AWS
aws configure sso --profile development

# 4. Deploy infrastructure
cd terraform
terraform init
terraform plan
terraform apply

# 5. Deploy Lambda functions
cd ..
./scripts/deploy_all_functions.sh

# 6. Test deployment
python test_complete_framework.py "examples/test_file.txt"
```

### Option 2: Manual Step-by-Step Deployment

## 📦 Step 1: Infrastructure Deployment

### 1.1 Initialize Terraform

```bash
cd terraform
terraform init
```

### 1.2 Review and Customize Variables

Edit `terraform/variables.tf`:

```hcl
variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-west-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "agentic-framework"
}
```

### 1.3 Plan and Apply Infrastructure

```bash
# Review planned changes
terraform plan

# Apply infrastructure
terraform apply
```

**Expected Resources Created:**
- 3 S3 buckets (input, processed, q-tables)
- 2 DynamoDB tables (performance metrics, experiences)
- IAM roles and policies
- Step Functions state machine

## 🔧 Step 2: Lambda Function Deployment

### 2.1 Manual Lambda Deployment

```bash
cd lambda-functions

# Deploy File Analyzer
zip enhanced_file_analyzer.zip enhanced_file_analyzer.py
aws lambda create-function \
  --function-name agentic-file-analyzer-dev \
  --runtime python3.9 \
  --role arn:aws:iam::ACCOUNT_ID:role/agentic-framework-lambda-execution-role-dev \
  --handler enhanced_file_analyzer.lambda_handler \
  --zip-file fileb://enhanced_file_analyzer.zip \
  --timeout 300 \
  --memory-size 512

# Deploy Interview Processing Agent
zip interview_processing_agent.zip interview_processing_agent.py
aws lambda create-function \
  --function-name agentic-interview-processing-dev \
  --runtime python3.9 \
  --role arn:aws:iam::ACCOUNT_ID:role/agentic-framework-lambda-execution-role-dev \
  --handler interview_processing_agent.lambda_handler \
  --zip-file fileb://interview_processing_agent.zip \
  --timeout 900 \
  --memory-size 1024

# Deploy Needs Analysis Agent
zip needs_analysis_agent.zip needs_analysis_agent.py
aws lambda create-function \
  --function-name agentic-needs-analysis-dev \
  --runtime python3.9 \
  --role arn:aws:iam::ACCOUNT_ID:role/agentic-framework-lambda-execution-role-dev \
  --handler needs_analysis_agent.lambda_handler \
  --zip-file fileb://needs_analysis_agent.zip \
  --timeout 900 \
  --memory-size 1024

# Deploy Hypergraph Builder Agent
zip hypergraph_builder_agent.zip hypergraph_builder_agent.py
aws lambda create-function \
  --function-name agentic-hypergraph-builder-dev \
  --runtime python3.9 \
  --role arn:aws:iam::ACCOUNT_ID:role/agentic-framework-lambda-execution-role-dev \
  --handler hypergraph_builder_agent.lambda_handler \
  --zip-file fileb://hypergraph_builder_agent.zip \
  --timeout 900 \
  --memory-size 1024

# Deploy NLP Processing Agent
zip nlp_processing_agent.zip nlp_processing_agent.py
aws lambda create-function \
  --function-name agentic-nlp-processing-dev \
  --runtime python3.9 \
  --role arn:aws:iam::ACCOUNT_ID:role/agentic-framework-lambda-execution-role-dev \
  --handler nlp_processing_agent.lambda_handler \
  --zip-file fileb://nlp_processing_agent.zip \
  --timeout 900 \
  --memory-size 512
```

### 2.2 Automated Lambda Deployment

```bash
./scripts/deploy_all_functions.sh
```

## 🔄 Step 3: Step Functions Configuration

### 3.1 Update State Machine Definition

The Step Functions state machine is automatically created by Terraform, but you may need to update it:

```bash
# Get state machine ARN
STATE_MACHINE_ARN=$(aws stepfunctions list-state-machines \
  --query "stateMachines[?name=='agentic-framework-processing-workflow-dev'].stateMachineArn" \
  --output text)

# Update state machine
aws stepfunctions update-state-machine \
  --state-machine-arn $STATE_MACHINE_ARN \
  --definition file://config/customer_aware_workflow.json
```

## 📊 Step 4: Data Setup

### 4.1 Upload Test Data

```bash
# Upload customer files to S3
aws s3 cp examples/high_customers/ s3://agentic-framework-input-files-dev-ACCOUNT_ID/high_customers/ --recursive

# Verify upload
aws s3 ls s3://agentic-framework-input-files-dev-ACCOUNT_ID/high_customers/ --recursive
```

### 4.2 Initialize DynamoDB Tables

The tables are created by Terraform, but you can verify:

```bash
# Check agent performance metrics table
aws dynamodb describe-table --table-name agent-performance-metrics

# Check agent experiences table
aws dynamodb describe-table --table-name agent-experiences
```

## 🧪 Step 5: Testing and Validation

### 5.1 Run Integration Tests

```bash
# Test with Tim Wolff file (Financial Processing)
python test_complete_framework.py "high_customers/00_tim_wolff/sample_file.txt"

# Test with Jon Fortt file (Interview Processing)
python test_complete_framework.py "high_customers/01_jon_fortt/sample_file.txt"

# Test with generic content
python test_complete_framework.py "examples/generic_content.txt"
```

### 5.2 Verify Results

```bash
# Check DynamoDB for results
aws dynamodb scan --table-name agent-performance-metrics --max-items 5

# Check Step Functions executions
aws stepfunctions list-executions \
  --state-machine-arn $STATE_MACHINE_ARN \
  --max-items 5
```

## 🔍 Step 6: Monitoring Setup

### 6.1 CloudWatch Dashboards

Create custom dashboards for monitoring:

```bash
# Create dashboard JSON
cat > dashboard.json << EOF
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/Lambda", "Duration", "FunctionName", "agentic-file-analyzer-dev"],
          ["AWS/Lambda", "Errors", "FunctionName", "agentic-file-analyzer-dev"]
        ],
        "period": 300,
        "stat": "Average",
        "region": "us-west-1",
        "title": "Lambda Performance"
      }
    }
  ]
}
EOF

# Create dashboard
aws cloudwatch put-dashboard \
  --dashboard-name "AgenticFramework" \
  --dashboard-body file://dashboard.json
```

### 6.2 CloudWatch Alarms

```bash
# Create alarm for Lambda errors
aws cloudwatch put-metric-alarm \
  --alarm-name "AgenticFramework-LambdaErrors" \
  --alarm-description "Alert on Lambda function errors" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --dimensions Name=FunctionName,Value=agentic-file-analyzer-dev \
  --evaluation-periods 1
```

## 🔧 Configuration Management

### Environment Variables

Set these environment variables for your Lambda functions:

```bash
# For all Lambda functions
export AWS_REGION=us-west-1
export S3_INPUT_BUCKET=agentic-framework-input-files-dev-ACCOUNT_ID
export S3_PROCESSED_BUCKET=agentic-framework-processed-data-dev-ACCOUNT_ID
export DYNAMODB_PERFORMANCE_TABLE=agent-performance-metrics
export DYNAMODB_EXPERIENCES_TABLE=agent-experiences

# Update Lambda function environment variables
aws lambda update-function-configuration \
  --function-name agentic-file-analyzer-dev \
  --environment Variables="{AWS_REGION=us-west-1,S3_INPUT_BUCKET=agentic-framework-input-files-dev-ACCOUNT_ID}"
```

## 🚨 Troubleshooting

### Common Issues

#### 1. Lambda Function Timeout
```bash
# Increase timeout
aws lambda update-function-configuration \
  --function-name FUNCTION_NAME \
  --timeout 900
```

#### 2. Insufficient Memory
```bash
# Increase memory
aws lambda update-function-configuration \
  --function-name FUNCTION_NAME \
  --memory-size 1024
```

#### 3. Permission Issues
```bash
# Check IAM role permissions
aws iam get-role-policy \
  --role-name agentic-framework-lambda-execution-role-dev \
  --policy-name agentic-framework-lambda-policy-dev
```

#### 4. Step Functions Execution Failures
```bash
# Get execution details
aws stepfunctions describe-execution \
  --execution-arn EXECUTION_ARN
```

### Debugging Commands

```bash
# Check Lambda logs
aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/agentic"

# Get recent log events
aws logs filter-log-events \
  --log-group-name "/aws/lambda/agentic-file-analyzer-dev" \
  --start-time $(date -d '1 hour ago' +%s)000

# Check Step Functions execution history
aws stepfunctions get-execution-history \
  --execution-arn EXECUTION_ARN
```

## 🔄 Updates and Maintenance

### Updating Lambda Functions

```bash
# Update function code
cd lambda-functions
zip updated_function.zip updated_function.py
aws lambda update-function-code \
  --function-name FUNCTION_NAME \
  --zip-file fileb://updated_function.zip
```

### Updating Step Functions

```bash
# Update state machine definition
aws stepfunctions update-state-machine \
  --state-machine-arn $STATE_MACHINE_ARN \
  --definition file://config/updated_workflow.json
```

### Infrastructure Updates

```bash
# Update infrastructure
cd terraform
terraform plan
terraform apply
```

## 📈 Performance Optimization

### Lambda Optimization
- **Memory**: Start with 512MB, increase if needed
- **Timeout**: Set based on actual execution time + buffer
- **Provisioned Concurrency**: For frequently used functions

### DynamoDB Optimization
- **On-Demand**: Good for variable workloads
- **Provisioned**: Better for predictable workloads
- **Global Secondary Indexes**: For query patterns

### Step Functions Optimization
- **Parallel Execution**: Use parallel states where possible
- **Error Handling**: Implement proper retry and catch logic
- **State Optimization**: Minimize state transitions

## 🔒 Security Best Practices

### IAM Policies
- Use least privilege principle
- Regular policy reviews
- Separate roles for different components

### Data Encryption
- Enable S3 bucket encryption
- Use DynamoDB encryption at rest
- Encrypt sensitive environment variables

### Network Security
- Use VPC endpoints where applicable
- Implement proper security groups
- Monitor network traffic

## 📊 Cost Optimization

### Lambda Costs
- Right-size memory allocation
- Optimize execution time
- Use provisioned concurrency judiciously

### Storage Costs
- Implement S3 lifecycle policies
- Use appropriate storage classes
- Regular cleanup of old data

### DynamoDB Costs
- Choose appropriate billing mode
- Optimize query patterns
- Use TTL for temporary data

This deployment guide provides comprehensive instructions for setting up the Enhanced Digital Twin Agentic Framework in production. Follow the steps carefully and refer to the troubleshooting section if you encounter any issues.