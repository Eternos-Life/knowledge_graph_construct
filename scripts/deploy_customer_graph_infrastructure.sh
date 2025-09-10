#!/bin/bash

# Deploy Customer Graph Infrastructure
# This script deploys the AWS infrastructure needed for customer graph persistence

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TERRAFORM_DIR="$PROJECT_ROOT/terraform"

echo "🚀 Deploying Customer Graph Infrastructure..."

# Check if Terraform is installed
if ! command -v terraform &> /dev/null; then
    echo "❌ Terraform is not installed. Please install Terraform first."
    exit 1
fi

# Check if AWS CLI is configured
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS CLI is not configured. Please configure AWS CLI first."
    exit 1
fi

# Navigate to Terraform directory
cd "$TERRAFORM_DIR"

echo "📋 Initializing Terraform..."
terraform init

echo "📋 Planning Terraform deployment..."
terraform plan -out=tfplan

echo "🔍 Reviewing plan..."
echo "The following resources will be created:"
echo "- S3 bucket for customer graph storage with encryption"
echo "- Neptune cluster with customer isolation"
echo "- IAM roles for Lambda functions with minimal permissions"
echo "- CloudWatch log groups and custom metrics"
echo "- Security groups for Neptune access"
echo "- KMS key for encryption"

read -p "Do you want to proceed with the deployment? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Deployment cancelled."
    rm -f tfplan
    exit 1
fi

echo "🚀 Applying Terraform configuration..."
terraform apply tfplan

echo "✅ Infrastructure deployment completed!"

# Clean up plan file
rm -f tfplan

# Display important outputs
echo ""
echo "📊 Important Infrastructure Details:"
echo "=================================="
terraform output -json | jq -r '
  "S3 Customer Graphs Bucket: " + .s3_customer_graphs_bucket.value,
  "Neptune Cluster Endpoint: " + .neptune_cluster_endpoint.value,
  "Neptune Cluster ID: " + .neptune_cluster_id.value,
  "Graph Extraction Lambda Role: " + .graph_extraction_lambda_role_arn.value,
  "Neptune Persistence Lambda Role: " + .neptune_persistence_lambda_role_arn.value,
  "KMS Key ID: " + .customer_graphs_kms_key_id.value
'

echo ""
echo "🎉 Customer Graph Infrastructure is ready!"
echo "Next steps:"
echo "1. Deploy the Lambda functions (task 2)"
echo "2. Update the Step Functions workflow (task 4)"
echo "3. Test the complete pipeline"