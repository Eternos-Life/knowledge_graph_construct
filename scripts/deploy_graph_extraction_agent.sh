#!/bin/bash

# Deploy Graph Extraction Agent Lambda Function
# This script packages and deploys the graph extraction agent

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LAMBDA_DIR="$PROJECT_ROOT/lambda-functions"
TERRAFORM_DIR="$PROJECT_ROOT/terraform"

# Configuration
REGION="us-west-1"
PROFILE="development"
ENVIRONMENT="dev"
FUNCTION_NAME="graph-extraction-agent-${ENVIRONMENT}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Deploying Graph Extraction Agent${NC}"
echo -e "${BLUE}=================================${NC}"

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

# Check if graph extraction agent exists
if [ ! -f "$LAMBDA_DIR/graph_extraction_agent.py" ]; then
    print_error "graph_extraction_agent.py not found in lambda-functions directory"
    exit 1
fi
print_status "Graph extraction agent source found"

echo ""

# Step 1: Package the Lambda function
echo -e "${BLUE}📦 Packaging Lambda Function${NC}"
echo "----------------------------------------"

cd "$LAMBDA_DIR"

# Create deployment package
ZIP_FILE="graph_extraction_agent.zip"
echo -e "${YELLOW}📦 Creating deployment package...${NC}"

# Remove existing zip if it exists
rm -f "$ZIP_FILE"

# Create zip with the Python file
zip -q "$ZIP_FILE" graph_extraction_agent.py

print_status "Deployment package created: $ZIP_FILE"

# Step 2: Check if function exists
echo ""
echo -e "${BLUE}🔍 Checking Function Status${NC}"
echo "----------------------------------------"

FUNCTION_EXISTS=false
if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" --profile "$PROFILE" &> /dev/null; then
    FUNCTION_EXISTS=true
    print_status "Function exists, will update code"
else
    print_warning "Function does not exist, will deploy infrastructure first"
fi

# Step 3: Deploy infrastructure if needed
if [ "$FUNCTION_EXISTS" = false ]; then
    echo ""
    echo -e "${BLUE}🏗️  Deploying Infrastructure${NC}"
    echo "----------------------------------------"
    
    cd "$TERRAFORM_DIR"
    
    echo -e "${YELLOW}📋 Initializing Terraform...${NC}"
    terraform init
    
    echo -e "${YELLOW}📋 Planning Terraform deployment...${NC}"
    terraform plan -target=aws_lambda_function.graph_extraction_agent -out=tfplan
    
    echo -e "${YELLOW}🚀 Applying Terraform configuration...${NC}"
    terraform apply tfplan
    
    # Clean up plan file
    rm -f tfplan
    
    print_status "Infrastructure deployed"
    
    cd "$LAMBDA_DIR"
fi

# Step 4: Update function code
echo ""
echo -e "${BLUE}🔄 Updating Function Code${NC}"
echo "----------------------------------------"

echo -e "${YELLOW}📦 Updating Lambda function code...${NC}"

if UPDATE_RESULT=$(aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --zip-file "fileb://$ZIP_FILE" \
    --region "$REGION" \
    --profile "$PROFILE" 2>&1); then
    
    print_status "Code updated for $FUNCTION_NAME"
    
    # Wait for function to be updated
    echo -e "${YELLOW}⏳ Waiting for function update to complete...${NC}"
    aws lambda wait function-updated \
        --function-name "$FUNCTION_NAME" \
        --region "$REGION" \
        --profile "$PROFILE"
    
    print_status "Function update completed"
    
else
    print_error "Failed to update function code: $UPDATE_RESULT"
    exit 1
fi

# Step 5: Create version and alias
echo ""
echo -e "${BLUE}🏷️  Creating Version and Alias${NC}"
echo "----------------------------------------"

echo -e "${YELLOW}🏷️  Creating new version...${NC}"
if VERSION_RESULT=$(aws lambda publish-version \
    --function-name "$FUNCTION_NAME" \
    --description "Deployed on $(date '+%Y-%m-%d %H:%M:%S') - Graph Extraction Agent" \
    --region "$REGION" \
    --profile "$PROFILE" 2>&1); then
    
    # Extract version number
    VERSION_NUMBER=$(echo "$VERSION_RESULT" | jq -r '.Version' 2>/dev/null || echo "unknown")
    print_status "Created version $VERSION_NUMBER for $FUNCTION_NAME"
    
    # Update alias to point to new version (create if doesn't exist)
    ALIAS_NAME="LIVE"
    echo -e "${YELLOW}🔗 Updating alias $ALIAS_NAME to version $VERSION_NUMBER...${NC}"
    
    # Try to update alias first
    if aws lambda update-alias \
        --function-name "$FUNCTION_NAME" \
        --name "$ALIAS_NAME" \
        --function-version "$VERSION_NUMBER" \
        --description "Live version updated on $(date '+%Y-%m-%d %H:%M:%S')" \
        --region "$REGION" \
        --profile "$PROFILE" > /dev/null 2>&1; then
        print_status "Updated alias $ALIAS_NAME to version $VERSION_NUMBER"
    else
        # If update fails, try to create alias
        if aws lambda create-alias \
            --function-name "$FUNCTION_NAME" \
            --name "$ALIAS_NAME" \
            --function-version "$VERSION_NUMBER" \
            --description "Live version created on $(date '+%Y-%m-%d %H:%M:%S')" \
            --region "$REGION" \
            --profile "$PROFILE" > /dev/null 2>&1; then
            print_status "Created alias $ALIAS_NAME pointing to version $VERSION_NUMBER"
        else
            print_warning "Failed to create/update alias for $FUNCTION_NAME"
        fi
    fi
    
else
    print_warning "Failed to create version for $FUNCTION_NAME: $VERSION_RESULT"
fi

# Step 6: Verify deployment
echo ""
echo -e "${BLUE}🔍 Verifying Deployment${NC}"
echo "----------------------------------------"

# Check function status
if FUNCTION_INFO=$(aws lambda get-function \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --profile "$PROFILE" 2>&1); then
    
    print_status "Function is active and accessible"
    
    # Extract function details
    FUNCTION_ARN=$(echo "$FUNCTION_INFO" | jq -r '.Configuration.FunctionArn' 2>/dev/null || echo "unknown")
    RUNTIME=$(echo "$FUNCTION_INFO" | jq -r '.Configuration.Runtime' 2>/dev/null || echo "unknown")
    MEMORY_SIZE=$(echo "$FUNCTION_INFO" | jq -r '.Configuration.MemorySize' 2>/dev/null || echo "unknown")
    TIMEOUT=$(echo "$FUNCTION_INFO" | jq -r '.Configuration.Timeout' 2>/dev/null || echo "unknown")
    
    echo "  📋 Function Details:"
    echo "     ARN: $FUNCTION_ARN"
    echo "     Runtime: $RUNTIME"
    echo "     Memory: ${MEMORY_SIZE}MB"
    echo "     Timeout: ${TIMEOUT}s"
    
else
    print_error "Function verification failed: $FUNCTION_INFO"
    exit 1
fi

# Check S3 bucket access
echo ""
echo -e "${YELLOW}🪣 Checking S3 bucket access...${NC}"
ACCOUNT_ID=$(aws sts get-caller-identity --profile "$PROFILE" --query Account --output text)
S3_BUCKET="agentic-framework-customer-graphs-${ENVIRONMENT}-${ACCOUNT_ID}"

if aws s3 ls "s3://$S3_BUCKET" --region "$REGION" --profile "$PROFILE" > /dev/null 2>&1; then
    print_status "S3 bucket is accessible: $S3_BUCKET"
else
    print_warning "S3 bucket not accessible: $S3_BUCKET (may need infrastructure deployment)"
fi

# Clean up
rm -f "$ZIP_FILE"

echo ""
echo -e "${BLUE}📋 Deployment Summary${NC}"
echo "========================================"
echo -e "${GREEN}✅ Graph Extraction Agent deployed successfully!${NC}"
echo ""
echo "Function Details:"
echo "  📦 Function Name: $FUNCTION_NAME"
echo "  🏷️  Version: $VERSION_NUMBER"
echo "  🔗 Alias: $ALIAS_NAME"
echo "  🪣 S3 Bucket: $S3_BUCKET"
echo ""
echo "Next steps:"
echo "1. Test the function: aws lambda invoke --function-name $FUNCTION_NAME --payload '{}' response.json --profile $PROFILE"
echo "2. Run integration tests: source endtfenv/bin/activate && python testing/integration/test_complete_framework.py"
echo "3. Monitor function logs: aws logs tail /aws/lambda/$FUNCTION_NAME --follow --profile $PROFILE"
echo ""
echo -e "${BLUE}🎉 Graph Extraction Agent is ready for use!${NC}"