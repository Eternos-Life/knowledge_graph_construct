#!/usr/bin/env python3
"""
Validation script for Customer Graph Infrastructure
Verifies that all required AWS resources are properly configured
"""

import boto3
import json
import sys
from botocore.exceptions import ClientError, NoCredentialsError

def check_aws_credentials():
    """Check if AWS credentials are configured"""
    try:
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        print(f"✅ AWS credentials configured for account: {identity['Account']}")
        return identity['Account']
    except NoCredentialsError:
        print("❌ AWS credentials not configured")
        return None
    except Exception as e:
        print(f"❌ Error checking AWS credentials: {e}")
        return None

def validate_s3_bucket(bucket_name):
    """Validate S3 bucket configuration"""
    try:
        s3 = boto3.client('s3')
        
        # Check if bucket exists
        s3.head_bucket(Bucket=bucket_name)
        print(f"✅ S3 bucket '{bucket_name}' exists")
        
        # Check versioning
        versioning = s3.get_bucket_versioning(Bucket=bucket_name)
        if versioning.get('Status') == 'Enabled':
            print(f"✅ S3 bucket versioning enabled")
        else:
            print(f"⚠️  S3 bucket versioning not enabled")
        
        # Check encryption
        try:
            encryption = s3.get_bucket_encryption(Bucket=bucket_name)
            if encryption['ServerSideEncryptionConfiguration']:
                print(f"✅ S3 bucket encryption configured")
        except ClientError as e:
            if e.response['Error']['Code'] == 'ServerSideEncryptionConfigurationNotFoundError':
                print(f"⚠️  S3 bucket encryption not configured")
        
        # Check public access block
        try:
            public_access = s3.get_public_access_block(Bucket=bucket_name)
            config = public_access['PublicAccessBlockConfiguration']
            if all([config['BlockPublicAcls'], config['BlockPublicPolicy'], 
                   config['IgnorePublicAcls'], config['RestrictPublicBuckets']]):
                print(f"✅ S3 bucket public access properly blocked")
            else:
                print(f"⚠️  S3 bucket public access not fully blocked")
        except ClientError:
            print(f"⚠️  Could not check S3 bucket public access configuration")
            
        return True
        
    except ClientError as e:
        print(f"❌ S3 bucket validation failed: {e}")
        return False

def validate_neptune_cluster(cluster_id):
    """Validate Neptune cluster configuration"""
    try:
        neptune = boto3.client('neptune')
        
        # Check cluster status
        response = neptune.describe_db_clusters(DBClusterIdentifier=cluster_id)
        cluster = response['DBClusters'][0]
        
        print(f"✅ Neptune cluster '{cluster_id}' exists")
        print(f"   Status: {cluster['Status']}")
        print(f"   Engine: {cluster['Engine']}")
        print(f"   Encrypted: {cluster['StorageEncrypted']}")
        
        if cluster['Status'] == 'available':
            print(f"✅ Neptune cluster is available")
        else:
            print(f"⚠️  Neptune cluster status: {cluster['Status']}")
        
        if cluster['StorageEncrypted']:
            print(f"✅ Neptune cluster encryption enabled")
        else:
            print(f"⚠️  Neptune cluster encryption not enabled")
        
        # Check instances
        instances = neptune.describe_db_instances(
            Filters=[{'Name': 'db-cluster-id', 'Values': [cluster_id]}]
        )
        
        instance_count = len(instances['DBInstances'])
        print(f"✅ Neptune cluster has {instance_count} instance(s)")
        
        for instance in instances['DBInstances']:
            print(f"   Instance: {instance['DBInstanceIdentifier']} - {instance['DBInstanceStatus']}")
        
        return True
        
    except ClientError as e:
        print(f"❌ Neptune cluster validation failed: {e}")
        return False

def validate_iam_roles(role_names):
    """Validate IAM roles exist and have proper policies"""
    try:
        iam = boto3.client('iam')
        
        for role_name in role_names:
            try:
                role = iam.get_role(RoleName=role_name)
                print(f"✅ IAM role '{role_name}' exists")
                
                # Check attached policies
                policies = iam.list_attached_role_policies(RoleName=role_name)
                inline_policies = iam.list_role_policies(RoleName=role_name)
                
                total_policies = len(policies['AttachedPolicies']) + len(inline_policies['PolicyNames'])
                print(f"   Policies attached: {total_policies}")
                
            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchEntity':
                    print(f"❌ IAM role '{role_name}' not found")
                    return False
                else:
                    raise
        
        return True
        
    except ClientError as e:
        print(f"❌ IAM role validation failed: {e}")
        return False

def validate_cloudwatch_log_groups(log_group_names):
    """Validate CloudWatch log groups exist"""
    try:
        logs = boto3.client('logs')
        
        for log_group_name in log_group_names:
            try:
                response = logs.describe_log_groups(logGroupNamePrefix=log_group_name)
                
                found = False
                for log_group in response['logGroups']:
                    if log_group['logGroupName'] == log_group_name:
                        print(f"✅ CloudWatch log group '{log_group_name}' exists")
                        print(f"   Retention: {log_group.get('retentionInDays', 'Never expire')} days")
                        found = True
                        break
                
                if not found:
                    print(f"❌ CloudWatch log group '{log_group_name}' not found")
                    return False
                    
            except ClientError as e:
                print(f"❌ Error checking log group '{log_group_name}': {e}")
                return False
        
        return True
        
    except ClientError as e:
        print(f"❌ CloudWatch log group validation failed: {e}")
        return False

def validate_kms_key(key_id):
    """Validate KMS key exists and is enabled"""
    try:
        kms = boto3.client('kms')
        
        key = kms.describe_key(KeyId=key_id)
        key_metadata = key['KeyMetadata']
        
        print(f"✅ KMS key '{key_id}' exists")
        print(f"   State: {key_metadata['KeyState']}")
        print(f"   Usage: {key_metadata['KeyUsage']}")
        
        if key_metadata['KeyState'] == 'Enabled':
            print(f"✅ KMS key is enabled")
        else:
            print(f"⚠️  KMS key state: {key_metadata['KeyState']}")
        
        return True
        
    except ClientError as e:
        print(f"❌ KMS key validation failed: {e}")
        return False

def main():
    """Main validation function"""
    print("🔍 Validating Customer Graph Infrastructure...")
    print("=" * 50)
    
    # Check AWS credentials
    account_id = check_aws_credentials()
    if not account_id:
        sys.exit(1)
    
    # Get environment from Terraform outputs or use default
    environment = "dev"  # Default environment
    
    # Construct resource names based on naming convention
    project_name = "agentic-framework"
    
    bucket_name = f"{project_name}-customer-graphs-{environment}-{account_id}"
    cluster_id = f"{project_name}-neptune-{environment}"
    
    role_names = [
        f"{project_name}-graph-extraction-lambda-{environment}",
        f"{project_name}-neptune-persistence-lambda-{environment}",
        f"{project_name}-neptune-monitoring-{environment}"
    ]
    
    log_group_names = [
        f"/aws/lambda/graph-extraction-agent-{environment}",
        f"/aws/lambda/neptune-persistence-agent-{environment}"
    ]
    
    validation_results = []
    
    print("\n📦 Validating S3 Bucket...")
    validation_results.append(validate_s3_bucket(bucket_name))
    
    print("\n🗄️  Validating Neptune Cluster...")
    validation_results.append(validate_neptune_cluster(cluster_id))
    
    print("\n🔐 Validating IAM Roles...")
    validation_results.append(validate_iam_roles(role_names))
    
    print("\n📊 Validating CloudWatch Log Groups...")
    validation_results.append(validate_cloudwatch_log_groups(log_group_names))
    
    # Try to get KMS key from Terraform output or skip if not available
    try:
        import subprocess
        result = subprocess.run(['terraform', 'output', '-json'], 
                              cwd='terraform', capture_output=True, text=True)
        if result.returncode == 0:
            outputs = json.loads(result.stdout)
            if 'customer_graphs_kms_key_id' in outputs:
                key_id = outputs['customer_graphs_kms_key_id']['value']
                print(f"\n🔑 Validating KMS Key...")
                validation_results.append(validate_kms_key(key_id))
    except Exception as e:
        print(f"\n⚠️  Could not validate KMS key: {e}")
    
    # Summary
    print("\n" + "=" * 50)
    print("📋 Validation Summary")
    print("=" * 50)
    
    if all(validation_results):
        print("✅ All infrastructure components validated successfully!")
        print("\n🎉 Customer Graph Infrastructure is ready for Lambda deployment!")
        sys.exit(0)
    else:
        print("❌ Some infrastructure components failed validation")
        print("\n🔧 Please check the errors above and re-run Terraform deployment if needed")
        sys.exit(1)

if __name__ == "__main__":
    main()