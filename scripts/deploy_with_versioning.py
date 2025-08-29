#!/usr/bin/env python3
"""
Enhanced Digital Twin Agentic Framework - Advanced Deployment with Versioning
Comprehensive deployment script with version management, rollback capabilities, and monitoring
"""

import boto3
import json
import time
import sys
import os
import subprocess
import zipfile
from datetime import datetime
from typing import Dict, List, Any, Optional
import argparse

class LambdaVersionManager:
    def __init__(self, profile: str = 'development', region: str = 'us-west-1', environment: str = 'dev'):
        self.profile = profile
        self.region = region
        self.environment = environment
        
        # Initialize AWS clients
        self.session = boto3.Session(profile_name=profile, region_name=region)
        self.lambda_client = self.session.client('lambda')
        self.stepfunctions = self.session.client('stepfunctions')
        self.s3 = self.session.client('s3')
        
        # Load deployment configuration
        self.config = self.load_deployment_config()
        
        # Track deployment results
        self.deployment_results = {
            'functions': {},
            'versions': {},
            'aliases': {},
            'step_functions': {},
            'errors': []
        }

    def load_deployment_config(self) -> Dict[str, Any]:
        """Load deployment configuration from JSON file"""
        config_path = 'config/deployment_config.json'
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"❌ Configuration file not found: {config_path}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in configuration file: {e}")
            sys.exit(1)

    def print_status(self, message: str, status: str = 'INFO'):
        """Print formatted status message"""
        icons = {'SUCCESS': '✅', 'ERROR': '❌', 'WARNING': '⚠️', 'INFO': 'ℹ️'}
        icon = icons.get(status, 'ℹ️')
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"[{timestamp}] {icon} {message}")

    def get_git_commit_hash(self) -> str:
        """Get current git commit hash"""
        try:
            result = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], 
                                  capture_output=True, text=True)
            return result.stdout.strip() if result.returncode == 0 else 'unknown'
        except:
            return 'unknown'

    def create_deployment_package(self, source_file: str) -> str:
        """Create deployment package for Lambda function"""
        if not os.path.exists(f"lambda-functions/{source_file}"):
            raise FileNotFoundError(f"Source file not found: lambda-functions/{source_file}")
        
        zip_filename = f"{source_file.replace('.py', '')}.zip"
        zip_path = f"lambda-functions/{zip_filename}"
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(f"lambda-functions/{source_file}", source_file)
        
        return zip_path

    def update_function_code(self, function_name: str, zip_path: str) -> Dict[str, Any]:
        """Update Lambda function code"""
        try:
            with open(zip_path, 'rb') as f:
                zip_content = f.read()
            
            response = self.lambda_client.update_function_code(
                FunctionName=function_name,
                ZipFile=zip_content
            )
            
            # Wait for function to be updated
            self.lambda_client.get_waiter('function_updated').wait(
                FunctionName=function_name,
                WaiterConfig={'Delay': 2, 'MaxAttempts': 30}
            )
            
            return response
        except Exception as e:
            raise Exception(f"Failed to update function code: {str(e)}")

    def publish_version(self, function_name: str, description: str = None) -> Dict[str, Any]:
        """Publish a new version of the Lambda function"""
        if not description:
            commit_hash = self.get_git_commit_hash()
            description = f"Deployed on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Commit: {commit_hash}"
        
        try:
            response = self.lambda_client.publish_version(
                FunctionName=function_name,
                Description=description
            )
            return response
        except Exception as e:
            raise Exception(f"Failed to publish version: {str(e)}")

    def create_or_update_alias(self, function_name: str, alias_name: str, version: str, description: str = None) -> Dict[str, Any]:
        """Create or update a Lambda function alias"""
        if not description:
            description = f"Alias updated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        try:
            # Try to update existing alias
            response = self.lambda_client.update_alias(
                FunctionName=function_name,
                Name=alias_name,
                FunctionVersion=version,
                Description=description
            )
            return {'action': 'updated', 'response': response}
        except self.lambda_client.exceptions.ResourceNotFoundException:
            # Create new alias if it doesn't exist
            try:
                response = self.lambda_client.create_alias(
                    FunctionName=function_name,
                    Name=alias_name,
                    FunctionVersion=version,
                    Description=description
                )
                return {'action': 'created', 'response': response}
            except Exception as e:
                raise Exception(f"Failed to create alias: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to update alias: {str(e)}")

    def deploy_function(self, function_name: str, function_config: Dict[str, Any]) -> Dict[str, Any]:
        """Deploy a single Lambda function with versioning"""
        self.print_status(f"Deploying {function_name}...")
        
        try:
            # Create deployment package
            zip_path = self.create_deployment_package(function_config['source_file'])
            
            # Update function code
            update_response = self.update_function_code(function_name, zip_path)
            self.print_status(f"Code updated for {function_name}", 'SUCCESS')
            
            # Publish new version
            version_response = self.publish_version(function_name)
            version_number = version_response['Version']
            self.print_status(f"Published version {version_number} for {function_name}", 'SUCCESS')
            
            # Update aliases
            aliases_config = self.config['deployment_settings']['aliases']
            alias_results = {}
            
            for alias_key, alias_name in aliases_config.items():
                if alias_key == 'live':  # Always update LIVE alias to latest version
                    alias_result = self.create_or_update_alias(function_name, alias_name, version_number)
                    alias_results[alias_name] = alias_result
                    action = alias_result['action']
                    self.print_status(f"{action.capitalize()} alias {alias_name} → version {version_number}", 'SUCCESS')
            
            # Clean up deployment package
            os.remove(zip_path)
            
            return {
                'function_name': function_name,
                'version': version_number,
                'aliases': alias_results,
                'code_sha256': update_response['CodeSha256'],
                'last_modified': update_response['LastModified']
            }
            
        except Exception as e:
            error_msg = f"Failed to deploy {function_name}: {str(e)}"
            self.print_status(error_msg, 'ERROR')
            self.deployment_results['errors'].append(error_msg)
            return {'error': str(e)}

    def update_step_functions(self) -> Dict[str, Any]:
        """Update Step Functions state machine definition"""
        self.print_status("Updating Step Functions workflow...")
        
        try:
            sf_config = self.config['step_functions']
            state_machine_name = sf_config['state_machine_name']
            definition_file = sf_config['definition_file']
            
            # Load state machine definition
            with open(definition_file, 'r') as f:
                definition = f.read()
            
            # Find state machine ARN
            response = self.stepfunctions.list_state_machines()
            state_machine_arn = None
            
            for sm in response['stateMachines']:
                if sm['name'] == state_machine_name:
                    state_machine_arn = sm['stateMachineArn']
                    break
            
            if not state_machine_arn:
                raise Exception(f"State machine not found: {state_machine_name}")
            
            # Update state machine
            update_response = self.stepfunctions.update_state_machine(
                stateMachineArn=state_machine_arn,
                definition=definition
            )
            
            self.print_status("Step Functions workflow updated successfully", 'SUCCESS')
            return {
                'state_machine_arn': state_machine_arn,
                'update_date': update_response['updateDate']
            }
            
        except Exception as e:
            error_msg = f"Failed to update Step Functions: {str(e)}"
            self.print_status(error_msg, 'ERROR')
            self.deployment_results['errors'].append(error_msg)
            return {'error': str(e)}

    def cleanup_old_versions(self, function_name: str, keep_versions: int = 5) -> Dict[str, Any]:
        """Clean up old versions of a Lambda function"""
        try:
            # Get all versions
            response = self.lambda_client.list_versions_by_function(FunctionName=function_name)
            versions = [v for v in response['Versions'] if v['Version'] != '$LATEST']
            
            # Sort versions numerically
            versions.sort(key=lambda x: int(x['Version']))
            
            # Determine versions to delete
            if len(versions) <= keep_versions:
                return {'deleted_versions': [], 'kept_versions': len(versions)}
            
            versions_to_delete = versions[:-keep_versions]
            deleted_versions = []
            
            for version in versions_to_delete:
                try:
                    self.lambda_client.delete_function(
                        FunctionName=function_name,
                        Qualifier=version['Version']
                    )
                    deleted_versions.append(version['Version'])
                except Exception as e:
                    self.print_status(f"Could not delete version {version['Version']}: {str(e)}", 'WARNING')
            
            if deleted_versions:
                self.print_status(f"Cleaned up {len(deleted_versions)} old versions for {function_name}", 'SUCCESS')
            
            return {
                'deleted_versions': deleted_versions,
                'kept_versions': keep_versions
            }
            
        except Exception as e:
            self.print_status(f"Failed to cleanup versions for {function_name}: {str(e)}", 'WARNING')
            return {'error': str(e)}

    def deploy_all_functions(self) -> Dict[str, Any]:
        """Deploy all Lambda functions with versioning"""
        self.print_status("🚀 Starting deployment with versioning...")
        
        functions_config = self.config['functions']
        deployment_settings = self.config['deployment_settings']
        
        for function_name, function_config in functions_config.items():
            result = self.deploy_function(function_name, function_config)
            self.deployment_results['functions'][function_name] = result
            
            if 'error' not in result:
                self.deployment_results['versions'][function_name] = result['version']
                self.deployment_results['aliases'][function_name] = result['aliases']
                
                # Cleanup old versions if enabled
                if deployment_settings['versioning']['auto_cleanup']:
                    keep_versions = deployment_settings['versioning']['keep_versions']
                    cleanup_result = self.cleanup_old_versions(function_name, keep_versions)
                    result['cleanup'] = cleanup_result
        
        # Update Step Functions
        sf_result = self.update_step_functions()
        self.deployment_results['step_functions'] = sf_result
        
        return self.deployment_results

    def generate_deployment_report(self) -> str:
        """Generate a comprehensive deployment report"""
        report = []
        report.append("=" * 60)
        report.append("🚀 DEPLOYMENT REPORT")
        report.append("=" * 60)
        report.append(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Environment: {self.environment}")
        report.append(f"Region: {self.region}")
        report.append(f"Git Commit: {self.get_git_commit_hash()}")
        report.append("")
        
        # Function deployment results
        report.append("📦 LAMBDA FUNCTIONS")
        report.append("-" * 40)
        
        for function_name, result in self.deployment_results['functions'].items():
            if 'error' in result:
                report.append(f"❌ {function_name}: FAILED - {result['error']}")
            else:
                version = result['version']
                report.append(f"✅ {function_name}: Version {version}")
                
                # Show aliases
                for alias_name, alias_info in result['aliases'].items():
                    action = alias_info['action']
                    report.append(f"   └─ Alias {alias_name}: {action}")
                
                # Show cleanup results
                if 'cleanup' in result and 'deleted_versions' in result['cleanup']:
                    deleted = len(result['cleanup']['deleted_versions'])
                    if deleted > 0:
                        report.append(f"   └─ Cleaned up {deleted} old versions")
        
        report.append("")
        
        # Step Functions results
        report.append("🔄 STEP FUNCTIONS")
        report.append("-" * 40)
        
        sf_result = self.deployment_results['step_functions']
        if 'error' in sf_result:
            report.append(f"❌ Workflow update: FAILED - {sf_result['error']}")
        else:
            report.append("✅ Workflow updated successfully")
        
        report.append("")
        
        # Summary
        total_functions = len(self.deployment_results['functions'])
        successful_functions = len([r for r in self.deployment_results['functions'].values() if 'error' not in r])
        
        report.append("📊 SUMMARY")
        report.append("-" * 40)
        report.append(f"Functions deployed: {successful_functions}/{total_functions}")
        report.append(f"Step Functions: {'✅' if 'error' not in sf_result else '❌'}")
        
        if self.deployment_results['errors']:
            report.append(f"Errors: {len(self.deployment_results['errors'])}")
            report.append("")
            report.append("🚨 ERRORS")
            report.append("-" * 40)
            for error in self.deployment_results['errors']:
                report.append(f"❌ {error}")
        
        report.append("")
        report.append("🎉 Deployment completed!")
        report.append("=" * 60)
        
        return "\n".join(report)

    def save_deployment_manifest(self) -> str:
        """Save deployment manifest for rollback purposes"""
        manifest = {
            'deployment_id': f"deploy-{int(time.time())}",
            'timestamp': datetime.now().isoformat(),
            'environment': self.environment,
            'region': self.region,
            'git_commit': self.get_git_commit_hash(),
            'functions': {},
            'step_functions': self.deployment_results['step_functions']
        }
        
        for function_name, result in self.deployment_results['functions'].items():
            if 'error' not in result:
                manifest['functions'][function_name] = {
                    'version': result['version'],
                    'code_sha256': result['code_sha256'],
                    'last_modified': result['last_modified'],
                    'aliases': {name: info['response']['FunctionVersion'] 
                              for name, info in result['aliases'].items()}
                }
        
        # Save manifest
        manifest_file = f"deployments/manifest-{manifest['deployment_id']}.json"
        os.makedirs('deployments', exist_ok=True)
        
        with open(manifest_file, 'w') as f:
            json.dump(manifest, f, indent=2, default=str)
        
        self.print_status(f"Deployment manifest saved: {manifest_file}", 'SUCCESS')
        return manifest_file

def main():
    parser = argparse.ArgumentParser(description='Deploy Enhanced Digital Twin Agentic Framework with versioning')
    parser.add_argument('--profile', default='development', help='AWS profile to use')
    parser.add_argument('--region', default='us-west-1', help='AWS region')
    parser.add_argument('--environment', default='dev', help='Environment name')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be deployed without actually deploying')
    
    args = parser.parse_args()
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - No actual deployment will occur")
        print("-" * 50)
    
    # Initialize deployment manager
    manager = LambdaVersionManager(
        profile=args.profile,
        region=args.region,
        environment=args.environment
    )
    
    if args.dry_run:
        print("Configuration loaded successfully:")
        print(f"  Functions: {len(manager.config['functions'])}")
        print(f"  Versioning enabled: {manager.config['deployment_settings']['versioning']['enabled']}")
        print(f"  Auto cleanup: {manager.config['deployment_settings']['versioning']['auto_cleanup']}")
        return
    
    try:
        # Deploy all functions
        results = manager.deploy_all_functions()
        
        # Generate and display report
        report = manager.generate_deployment_report()
        print(report)
        
        # Save deployment manifest
        manifest_file = manager.save_deployment_manifest()
        
        # Exit with appropriate code
        if results['errors']:
            sys.exit(1)
        else:
            sys.exit(0)
            
    except KeyboardInterrupt:
        print("\n❌ Deployment cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Deployment failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()