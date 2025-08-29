#!/bin/bash

# Enhanced Digital Twin Agentic Framework - Version Management Script
# This script helps manage Lambda function versions and aliases

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

# Function names
FUNCTIONS=(
    "agentic-file-analyzer-${ENVIRONMENT}"
    "agentic-interview-processing-${ENVIRONMENT}"
    "agentic-needs-analysis-${ENVIRONMENT}"
    "agentic-hypergraph-builder-${ENVIRONMENT}"
)

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

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Function to list all versions for a function
list_versions() {
    local function_name=$1
    echo -e "${BLUE}📋 Versions for $function_name${NC}"
    echo "----------------------------------------"
    
    aws lambda list-versions-by-function \
        --function-name "$function_name" \
        --region "$REGION" \
        --profile "$PROFILE" \
        --query "Versions[*].[Version,Description,LastModified]" \
        --output table
    
    echo ""
    
    # List aliases
    echo -e "${BLUE}🔗 Aliases for $function_name${NC}"
    echo "----------------------------------------"
    
    aws lambda list-aliases \
        --function-name "$function_name" \
        --region "$REGION" \
        --profile "$PROFILE" \
        --query "Aliases[*].[Name,FunctionVersion,Description]" \
        --output table
    
    echo ""
}

# Function to create a rollback alias
create_rollback_alias() {
    local function_name=$1
    local version=$2
    local alias_name="ROLLBACK"
    
    echo -e "${YELLOW}🔄 Creating rollback alias for $function_name version $version${NC}"
    
    # Try to update alias first
    if aws lambda update-alias \
        --function-name "$function_name" \
        --name "$alias_name" \
        --function-version "$version" \
        --description "Rollback version created on $(date '+%Y-%m-%d %H:%M:%S')" \
        --region "$REGION" \
        --profile "$PROFILE" > /dev/null 2>&1; then
        print_status "Updated rollback alias to version $version"
    else
        # If update fails, try to create alias
        if aws lambda create-alias \
            --function-name "$function_name" \
            --name "$alias_name" \
            --function-version "$version" \
            --description "Rollback version created on $(date '+%Y-%m-%d %H:%M:%S')" \
            --region "$REGION" \
            --profile "$PROFILE" > /dev/null 2>&1; then
            print_status "Created rollback alias pointing to version $version"
        else
            print_error "Failed to create rollback alias"
        fi
    fi
}

# Function to rollback to a specific version
rollback_function() {
    local function_name=$1
    local version=$2
    
    echo -e "${YELLOW}🔄 Rolling back $function_name to version $version${NC}"
    
    # Update LIVE alias to point to the specified version
    if aws lambda update-alias \
        --function-name "$function_name" \
        --name "LIVE" \
        --function-version "$version" \
        --description "Rolled back to version $version on $(date '+%Y-%m-%d %H:%M:%S')" \
        --region "$REGION" \
        --profile "$PROFILE" > /dev/null 2>&1; then
        print_status "Successfully rolled back $function_name to version $version"
    else
        print_error "Failed to rollback $function_name"
    fi
}

# Function to delete old versions (keep last N versions)
cleanup_old_versions() {
    local function_name=$1
    local keep_versions=${2:-5}  # Default keep 5 versions
    
    echo -e "${YELLOW}🧹 Cleaning up old versions for $function_name (keeping last $keep_versions)${NC}"
    
    # Get all versions except $LATEST
    versions=$(aws lambda list-versions-by-function \
        --function-name "$function_name" \
        --region "$REGION" \
        --profile "$PROFILE" \
        --query "Versions[?Version != '\$LATEST'].Version" \
        --output text)
    
    # Convert to array and sort numerically
    version_array=($versions)
    IFS=$'\n' sorted_versions=($(sort -n <<<"${version_array[*]}"))
    unset IFS
    
    # Calculate how many to delete
    total_versions=${#sorted_versions[@]}
    versions_to_delete=$((total_versions - keep_versions))
    
    if [ $versions_to_delete -gt 0 ]; then
        echo "Found $total_versions versions, will delete $versions_to_delete old versions"
        
        for ((i=0; i<versions_to_delete; i++)); do
            version_to_delete=${sorted_versions[$i]}
            echo -e "${YELLOW}Deleting version $version_to_delete...${NC}"
            
            if aws lambda delete-function \
                --function-name "$function_name" \
                --qualifier "$version_to_delete" \
                --region "$REGION" \
                --profile "$PROFILE" > /dev/null 2>&1; then
                print_status "Deleted version $version_to_delete"
            else
                print_warning "Failed to delete version $version_to_delete (may be in use by alias)"
            fi
        done
    else
        print_info "No old versions to clean up"
    fi
}

# Function to show version comparison
compare_versions() {
    local function_name=$1
    local version1=$2
    local version2=$3
    
    echo -e "${BLUE}🔍 Comparing versions $version1 and $version2 for $function_name${NC}"
    echo "----------------------------------------"
    
    # Get version details
    version1_info=$(aws lambda get-function \
        --function-name "$function_name" \
        --qualifier "$version1" \
        --region "$REGION" \
        --profile "$PROFILE" \
        --query "Configuration.[LastModified,Description,CodeSize]" \
        --output text)
    
    version2_info=$(aws lambda get-function \
        --function-name "$function_name" \
        --qualifier "$version2" \
        --region "$REGION" \
        --profile "$PROFILE" \
        --query "Configuration.[LastModified,Description,CodeSize]" \
        --output text)
    
    echo "Version $version1: $version1_info"
    echo "Version $version2: $version2_info"
    echo ""
}

# Main script logic
case "${1:-help}" in
    "list")
        echo -e "${BLUE}📋 Lambda Function Versions${NC}"
        echo "========================================"
        
        for function_name in "${FUNCTIONS[@]}"; do
            list_versions "$function_name"
        done
        ;;
        
    "rollback")
        if [ -z "$2" ] || [ -z "$3" ]; then
            print_error "Usage: $0 rollback <function_name> <version>"
            print_info "Available functions: ${FUNCTIONS[*]}"
            exit 1
        fi
        
        function_name=$2
        version=$3
        
        # Validate function exists
        if [[ ! " ${FUNCTIONS[@]} " =~ " ${function_name} " ]]; then
            print_error "Function $function_name not found"
            print_info "Available functions: ${FUNCTIONS[*]}"
            exit 1
        fi
        
        rollback_function "$function_name" "$version"
        ;;
        
    "cleanup")
        keep_versions=${2:-5}
        
        echo -e "${BLUE}🧹 Cleaning up old versions (keeping last $keep_versions)${NC}"
        echo "========================================"
        
        for function_name in "${FUNCTIONS[@]}"; do
            cleanup_old_versions "$function_name" "$keep_versions"
        done
        ;;
        
    "compare")
        if [ -z "$2" ] || [ -z "$3" ] || [ -z "$4" ]; then
            print_error "Usage: $0 compare <function_name> <version1> <version2>"
            exit 1
        fi
        
        compare_versions "$2" "$3" "$4"
        ;;
        
    "create-rollback")
        if [ -z "$2" ] || [ -z "$3" ]; then
            print_error "Usage: $0 create-rollback <function_name> <version>"
            exit 1
        fi
        
        create_rollback_alias "$2" "$3"
        ;;
        
    "help"|*)
        echo -e "${BLUE}🔧 Lambda Version Management Tool${NC}"
        echo "========================================"
        echo ""
        echo "Usage: $0 <command> [options]"
        echo ""
        echo "Commands:"
        echo "  list                           - List all versions and aliases for all functions"
        echo "  rollback <function> <version>  - Rollback function to specific version"
        echo "  cleanup [keep_count]           - Delete old versions (default: keep 5)"
        echo "  compare <function> <v1> <v2>   - Compare two versions"
        echo "  create-rollback <function> <v> - Create rollback alias for version"
        echo "  help                           - Show this help message"
        echo ""
        echo "Examples:"
        echo "  $0 list"
        echo "  $0 rollback agentic-file-analyzer-dev 3"
        echo "  $0 cleanup 3"
        echo "  $0 compare agentic-file-analyzer-dev 2 3"
        echo ""
        echo "Available functions:"
        for function_name in "${FUNCTIONS[@]}"; do
            echo "  - $function_name"
        done
        ;;
esac