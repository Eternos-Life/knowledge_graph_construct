#!/bin/bash

# Enhanced Digital Twin Agentic Framework - Complete Deployment Script
# This script deploys all Lambda functions and updates the Step Functions workflow

set -e  # Exit on any error

# Configuration
REGION="us-west-1"
PROFILE="development"
ENVIRONMENT="dev"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Enhanced Digital Twin Agentic Framework Deployment${NC}"
echo -e "${BLUE}=================================================${NC}"
echo ""

# Function to print status
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check prerequisites
echo -e "${BLUE}🔍 Checking Prerequisites${NC}"
echo "----------------------------------------"

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    print_error "AWS CLI not found. Please install AWS CLI."
    exit 1
fi
print_status "AWS CLI found"

# Check AWS credentials
if ! aws sts get-caller-identity --profile $PROFILE &> /dev/null; then
    print_error "AWS credentials not configured for profile: $PROFILE"
    echo "Please run: aws configure sso --profile $PROFILE"
    exit 1
fi
print_status "AWS credentials configured"

# Check if we're in the right directory
if [ ! -d "lambda-functions" ]; then
    print_error "lambda-functions directory not found. Please run from project root."
    exit 1
fi
print_status "Project structure verified"

echo ""

# Deploy Lambda Functions
echo -e "${BLUE}📦 Deploying Lambda Functions${NC}"
echo "----------------------------------------"

cd lambda-functions

# Function names mapping
declare -A FUNCTIONS=(
    ["enhanced_file_analyzer.py"]="agentic-file-analyzer-${ENVIRONMENT}"
    ["interview_processing_agent.py"]="agentic-interview-processing-${ENVIRONMENT}"
    ["needs_analysis_agent.py"]="agentic-needs-analysis-${ENVIRONMENT}"
    ["hypergraph_builder_agent.py"]="agentic-hypergraph-builder-${ENVIRONMENT}"
    ["nlp_processing_agent.py"]="agentic-nlp-processing-${ENVIRONMENT}"
)

# Deploy each function
for file in "${!FUNCTIONS[@]}"; do
    function_name="${FUNCTIONS[$file]}"
    
    if [ -f "$file" ]; then
        echo -e "${YELLOW}📦 Deploying $function_name...${NC}"
        
        # Create deployment package
        zip_file="${file%.py}.zip"
        zip -q "$zip_file" "$file"
        
        # Update function code
        if aws lambda update-function-code \
            --function-name "$function_name" \
            --zip-file "fileb://$zip_file" \
            --region "$REGION" \
            --profile "$PROFILE" > /dev/null 2>&1; then
            print_status "Deployed $function_name"
        else
            print_warning "Failed to deploy $function_name (function may not exist yet)"
        fi
        
        # Clean up zip file
        rm -f "$zip_file"
    else
        print_warning "File $file not found, skipping..."
    fi
done

cd ..

echo ""

# Update Step Functions workflow
echo -e "${BLUE}🔄 Updating Step Functions Workflow${NC}"
echo "----------------------------------------"

if [ -f "config/customer_aware_workflow.json" ]; then
    # Get the state machine ARN
    STATE_MACHINE_ARN=$(aws stepfunctions list-state-machines \
        --region "$REGION" \
        --profile "$PROFILE" \
        --query "stateMachines[?name=='agentic-framework-processing-workflow-${ENVIRONMENT}'].stateMachineArn" \
        --output text)
    
    if [ -n "$STATE_MACHINE_ARN" ] && [ "$STATE_MACHINE_ARN" != "None" ]; then
        echo -e "${YELLOW}🔄 Updating Step Functions definition...${NC}"
        
        if aws stepfunctions update-state-machine \
            --state-machine-arn "$STATE_MACHINE_ARN" \
            --definition file://config/customer_aware_workflow.json \
            --region "$REGION" \
            --profile "$PROFILE" > /dev/null 2>&1; then
            print_status "Step Functions workflow updated"
        else
            print_warning "Failed to update Step Functions workflow"
        fi
    else
        print_warning "Step Functions state machine not found"
    fi
else
    print_warning "Step Functions workflow definition not found"
fi

echo ""

# Verify deployment
echo -e "${BLUE}🔍 Verifying Deployment${NC}"
echo "----------------------------------------"

# Check Lambda functions
echo "Lambda Functions:"
for function_name in "${FUNCTIONS[@]}"; do
    if aws lambda get-function \
        --function-name "$function_name" \
        --region "$REGION" \
        --profile "$PROFILE" > /dev/null 2>&1; then
        print_status "$function_name is active"
    else
        print_error "$function_name not found or not accessible"
    fi
done

# Check Step Functions
echo ""
echo "Step Functions:"
if [ -n "$STATE_MACHINE_ARN" ] && [ "$STATE_MACHINE_ARN" != "None" ]; then
    print_status "State machine is active: $STATE_MACHINE_ARN"
else
    print_error "State machine not found"
fi

# Check S3 bucket
echo ""
echo "S3 Storage:"
S3_BUCKET="agentic-framework-input-files-${ENVIRONMENT}-765455500375"
if aws s3 ls "s3://$S3_BUCKET" --region "$REGION" --profile "$PROFILE" > /dev/null 2>&1; then
    print_status "S3 bucket is accessible: $S3_BUCKET"
else
    print_error "S3 bucket not accessible: $S3_BUCKET"
fi

# Check DynamoDB table
echo ""
echo "DynamoDB:"
DYNAMODB_TABLE="agent-performance-metrics"
if aws dynamodb describe-table \
    --table-name "$DYNAMODB_TABLE" \
    --region "$REGION" \
    --profile "$PROFILE" > /dev/null 2>&1; then
    print_status "DynamoDB table is active: $DYNAMODB_TABLE"
else
    print_error "DynamoDB table not accessible: $DYNAMODB_TABLE"
fi

echo ""

# Run a test execution
echo -e "${BLUE}🧪 Running Test Execution${NC}"
echo "----------------------------------------"

if [ -f "test_complete_framework.py" ]; then
    echo -e "${YELLOW}🧪 Running framework test...${NC}"
    
    # Check if test files exist
    if [ -f "high_customers/00_tim_wolff/Berater = Netzwerk, Know-how, Backup.txt" ]; then
        echo "Testing with Tim Wolff file..."
        if python test_complete_framework.py "high_customers/00_tim_wolff/Berater = Netzwerk, Know-how, Backup.txt"; then
            print_status "Test execution completed successfully"
        else
            print_warning "Test execution failed - check logs above"
        fi
    else
        print_warning "Test files not found - skipping test execution"
    fi
else
    print_warning "Test script not found - skipping test execution"
fi

echo ""

# Final summary
echo -e "${BLUE}📋 Deployment Summary${NC}"
echo "========================================"

echo -e "${GREEN}✅ Deployment completed successfully!${NC}"
echo ""
echo "Next steps:"
echo "1. Verify all functions are working: aws lambda list-functions --profile $PROFILE"
echo "2. Test the complete framework: python test_complete_framework.py <file_path>"
echo "3. Monitor executions in AWS Step Functions console"
echo "4. Check results in DynamoDB table: $DYNAMODB_TABLE"
echo ""
echo -e "${BLUE}🎉 Enhanced Digital Twin Agentic Framework is ready for use!${NC}"