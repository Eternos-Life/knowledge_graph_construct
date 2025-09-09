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

# Function files to deploy
FUNCTION_FILES=(
    "enhanced_file_analyzer.py"
    "interview_processing_agent.py"
    "needs_analysis_agent.py"
    "enhanced_hypergraph_builder_agent_v2.py"
)

# Function to get Lambda function name from file name
get_function_name() {
    local file=$1
    case $file in
        "enhanced_file_analyzer.py")
            echo "agentic-file-analyzer-${ENVIRONMENT}"
            ;;
        "interview_processing_agent.py")
            echo "agentic-interview-processing-${ENVIRONMENT}"
            ;;
        "needs_analysis_agent.py")
            echo "agentic-needs-analysis-${ENVIRONMENT}"
            ;;
        "enhanced_hypergraph_builder_agent_v2.py")
            echo "agentic-hypergraph-builder-${ENVIRONMENT}"
            ;;
        *)
            echo "unknown-function"
            ;;
    esac
}

# Deploy each function with versioning
for file in "${FUNCTION_FILES[@]}"; do
    function_name=$(get_function_name "$file")
    
    if [ -f "$file" ]; then
        echo -e "${YELLOW}📦 Deploying $function_name...${NC}"
        
        # Create deployment package
        zip_file="${file%.py}.zip"
        zip -q "$zip_file" "$file"
        
        # Update function code
        if UPDATE_RESULT=$(aws lambda update-function-code \
            --function-name "$function_name" \
            --zip-file "fileb://$zip_file" \
            --region "$REGION" \
            --profile "$PROFILE" 2>&1); then
            
            print_status "Code updated for $function_name"
            
            # Wait for function to be updated (avoid InvalidParameterValueException)
            echo -e "${YELLOW}⏳ Waiting for function update to complete...${NC}"
            aws lambda wait function-updated \
                --function-name "$function_name" \
                --region "$REGION" \
                --profile "$PROFILE"
            
            # Create a new version
            echo -e "${YELLOW}🏷️  Creating new version for $function_name...${NC}"
            if VERSION_RESULT=$(aws lambda publish-version \
                --function-name "$function_name" \
                --description "Deployed on $(date '+%Y-%m-%d %H:%M:%S') - Commit: $(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')" \
                --region "$REGION" \
                --profile "$PROFILE" 2>&1); then
                
                # Extract version number
                VERSION_NUMBER=$(echo "$VERSION_RESULT" | jq -r '.Version' 2>/dev/null || echo "unknown")
                print_status "Created version $VERSION_NUMBER for $function_name"
                
                # Update alias to point to new version (create if doesn't exist)
                ALIAS_NAME="LIVE"
                echo -e "${YELLOW}🔗 Updating alias $ALIAS_NAME to version $VERSION_NUMBER...${NC}"
                
                # Try to update alias first
                if aws lambda update-alias \
                    --function-name "$function_name" \
                    --name "$ALIAS_NAME" \
                    --function-version "$VERSION_NUMBER" \
                    --description "Live version updated on $(date '+%Y-%m-%d %H:%M:%S')" \
                    --region "$REGION" \
                    --profile "$PROFILE" > /dev/null 2>&1; then
                    print_status "Updated alias $ALIAS_NAME to version $VERSION_NUMBER"
                else
                    # If update fails, try to create alias
                    if aws lambda create-alias \
                        --function-name "$function_name" \
                        --name "$ALIAS_NAME" \
                        --function-version "$VERSION_NUMBER" \
                        --description "Live version created on $(date '+%Y-%m-%d %H:%M:%S')" \
                        --region "$REGION" \
                        --profile "$PROFILE" > /dev/null 2>&1; then
                        print_status "Created alias $ALIAS_NAME pointing to version $VERSION_NUMBER"
                    else
                        print_warning "Failed to create/update alias for $function_name"
                    fi
                fi
                
                # Store version info for later use
                echo "$function_name:$VERSION_NUMBER" >> "/tmp/deployed_versions.txt"
                
            else
                print_warning "Failed to create version for $function_name: $VERSION_RESULT"
            fi
            
        else
            print_warning "Failed to deploy $function_name: $UPDATE_RESULT"
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
for file in "${FUNCTION_FILES[@]}"; do
    function_name=$(get_function_name "$file")
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

# Version Summary
echo ""
echo -e "${BLUE}📋 Version Summary${NC}"
echo "========================================"

if [ -f "/tmp/deployed_versions.txt" ]; then
    echo "Deployed versions:"
    while IFS=':' read -r function_name version_number; do
        echo "  📦 $function_name → Version $version_number"
    done < "/tmp/deployed_versions.txt"
    
    # Clean up temp file
    rm -f "/tmp/deployed_versions.txt"
else
    echo "No version information available"
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
echo "5. View function versions: aws lambda list-versions-by-function --function-name <function-name> --profile $PROFILE"
echo ""
echo -e "${BLUE}🎉 Enhanced Digital Twin Agentic Framework is ready for use!${NC}"