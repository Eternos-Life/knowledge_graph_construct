# Lambda Function Versioning Guide

## Overview

The Enhanced Digital Twin Agentic Framework now includes comprehensive Lambda function versioning and alias management for better deployment control, rollback capabilities, and production safety.

## 🎯 Key Features

### ✅ Automatic Versioning
- **Version Creation**: Every deployment creates a new immutable version
- **Git Integration**: Version descriptions include git commit hashes
- **Timestamp Tracking**: Deployment timestamps for audit trails

### ✅ Alias Management
- **LIVE Alias**: Always points to the latest deployed version
- **ROLLBACK Alias**: Can be set to any previous version for quick rollbacks
- **STAGING Alias**: Available for testing before promoting to LIVE

### ✅ Automated Cleanup
- **Version Retention**: Configurable number of versions to keep (default: 5)
- **Automatic Cleanup**: Old versions are automatically removed
- **Safety Checks**: Versions in use by aliases are protected

### ✅ Deployment Tracking
- **Manifest Files**: Complete deployment history with version mappings
- **Rollback Support**: Easy rollback to any previous deployment
- **Audit Trail**: Full deployment history with git commits

## 🚀 Deployment Methods

### Method 1: Advanced Deployment with Versioning (Recommended)

```bash
# Deploy with full versioning support
python scripts/deploy_with_versioning.py

# Dry run to see what would be deployed
python scripts/deploy_with_versioning.py --dry-run

# Deploy to different environment
python scripts/deploy_with_versioning.py --environment prod --profile production
```

**Features:**
- ✅ Automatic version creation
- ✅ Alias management (LIVE, ROLLBACK, STAGING)
- ✅ Deployment manifests for rollback
- ✅ Automatic cleanup of old versions
- ✅ Comprehensive deployment reports
- ✅ Git commit tracking

### Method 2: Enhanced Shell Script (Legacy with Versioning)

```bash
# Deploy using the enhanced shell script
./scripts/deploy_all_functions.sh
```

**Features:**
- ✅ Version creation
- ✅ LIVE alias management
- ✅ Basic version tracking
- ✅ Compatible with existing workflows

## 🔧 Version Management

### List All Versions and Aliases

```bash
# Show versions for all functions
./scripts/manage_versions.sh list

# Show versions for specific function
aws lambda list-versions-by-function \
  --function-name agentic-file-analyzer-dev \
  --profile development
```

### Rollback to Previous Version

```bash
# Rollback specific function to version 3
./scripts/manage_versions.sh rollback agentic-file-analyzer-dev 3

# Create rollback alias pointing to version 2
./scripts/manage_versions.sh create-rollback agentic-file-analyzer-dev 2
```

### Clean Up Old Versions

```bash
# Clean up old versions (keep last 5)
./scripts/manage_versions.sh cleanup

# Keep only last 3 versions
./scripts/manage_versions.sh cleanup 3
```

### Compare Versions

```bash
# Compare two versions of a function
./scripts/manage_versions.sh compare agentic-file-analyzer-dev 2 3
```

## 📊 Step Functions Integration

The Step Functions workflow now uses Lambda aliases instead of direct function names:

```json
{
  "FunctionName": "agentic-file-analyzer-dev:LIVE"
}
```

This ensures that Step Functions always uses the current LIVE version, and rollbacks are seamless.

## 🔄 Rollback Procedures

### Quick Rollback (Recommended)

1. **Identify target version:**
   ```bash
   ./scripts/manage_versions.sh list
   ```

2. **Rollback to previous version:**
   ```bash
   ./scripts/manage_versions.sh rollback agentic-file-analyzer-dev 2
   ```

3. **Verify rollback:**
   ```bash
   aws lambda get-alias \
     --function-name agentic-file-analyzer-dev \
     --name LIVE \
     --profile development
   ```

### Full Deployment Rollback

1. **Find deployment manifest:**
   ```bash
   ls -la deployments/
   ```

2. **Review manifest:**
   ```bash
   cat deployments/manifest-deploy-{timestamp}.json
   ```

3. **Rollback each function:**
   ```bash
   # Extract versions from manifest and rollback
   ./scripts/manage_versions.sh rollback function-name version
   ```

## 📋 Configuration

### Deployment Configuration (`config/deployment_config.json`)

```json
{
  "deployment_settings": {
    "versioning": {
      "enabled": true,
      "create_aliases": true,
      "keep_versions": 5,
      "auto_cleanup": true
    },
    "aliases": {
      "live": "LIVE",
      "rollback": "ROLLBACK",
      "staging": "STAGING"
    }
  }
}
```

### Environment Variables

```bash
export AWS_PROFILE=development
export AWS_REGION=us-west-1
export ENVIRONMENT=dev
```

## 🔍 Monitoring and Troubleshooting

### Check Function Status

```bash
# Check function configuration
aws lambda get-function \
  --function-name agentic-file-analyzer-dev:LIVE \
  --profile development

# Check alias configuration
aws lambda list-aliases \
  --function-name agentic-file-analyzer-dev \
  --profile development
```

### View Deployment History

```bash
# List all deployment manifests
ls -la deployments/

# View specific deployment
cat deployments/manifest-deploy-{timestamp}.json | jq '.'
```

### Debug Version Issues

```bash
# Check if version exists
aws lambda get-function \
  --function-name agentic-file-analyzer-dev \
  --qualifier 3 \
  --profile development

# List all versions
aws lambda list-versions-by-function \
  --function-name agentic-file-analyzer-dev \
  --profile development
```

## 🚨 Best Practices

### 1. Always Use Aliases in Production
- ✅ Use `function-name:LIVE` in Step Functions
- ✅ Never reference `$LATEST` in production
- ✅ Use specific versions only for testing

### 2. Test Before Promoting
```bash
# Deploy to staging alias first
aws lambda update-alias \
  --function-name agentic-file-analyzer-dev \
  --name STAGING \
  --function-version 4

# Test with staging
# Then promote to LIVE
aws lambda update-alias \
  --function-name agentic-file-analyzer-dev \
  --name LIVE \
  --function-version 4
```

### 3. Keep Deployment Manifests
- ✅ Store manifests in version control
- ✅ Include in backup procedures
- ✅ Use for audit and compliance

### 4. Regular Cleanup
```bash
# Schedule regular cleanup
./scripts/manage_versions.sh cleanup 5
```

### 5. Monitor Version Usage
```bash
# Check which versions are in use
aws lambda list-aliases \
  --function-name agentic-file-analyzer-dev \
  --profile development
```

## 🔐 Security Considerations

### IAM Permissions Required

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "lambda:PublishVersion",
        "lambda:CreateAlias",
        "lambda:UpdateAlias",
        "lambda:DeleteAlias",
        "lambda:ListVersionsByFunction",
        "lambda:ListAliases",
        "lambda:GetFunction",
        "lambda:DeleteFunction"
      ],
      "Resource": "arn:aws:lambda:*:*:function:agentic-*"
    }
  ]
}
```

### Version Protection

- Versions are **immutable** once created
- Aliases can be updated but require proper permissions
- Old versions are only deleted if not referenced by aliases

## 📈 Performance Impact

### Version Creation
- **Time**: ~2-3 seconds per function
- **Storage**: Each version stores complete function code
- **Cost**: Minimal additional cost for version metadata

### Alias Usage
- **Performance**: No performance impact
- **Latency**: Same as direct function invocation
- **Scaling**: Aliases scale with function

## 🎉 Migration from Legacy Deployment

### For Existing Functions

1. **Current deployment** creates Version 1 automatically
2. **LIVE alias** is created pointing to Version 1
3. **Step Functions** updated to use aliases
4. **No downtime** during migration

### Backward Compatibility

- Old deployment scripts still work
- Functions without aliases continue to work
- Gradual migration is supported

## 📞 Support and Troubleshooting

### Common Issues

1. **"Alias not found" error**
   ```bash
   # Create missing alias
   ./scripts/manage_versions.sh create-rollback function-name version
   ```

2. **"Version in use" during cleanup**
   - Check which aliases reference the version
   - Update aliases before deleting versions

3. **Step Functions using old versions**
   - Update workflow definition to use aliases
   - Redeploy Step Functions workflow

### Getting Help

```bash
# Show help for version management
./scripts/manage_versions.sh help

# Show help for deployment
python scripts/deploy_with_versioning.py --help
```

This versioning system provides enterprise-grade deployment capabilities with safety, auditability, and easy rollback procedures for the Enhanced Digital Twin Agentic Framework.