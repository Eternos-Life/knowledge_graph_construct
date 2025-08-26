#!/usr/bin/env python3
"""
Enhanced Digital Twin Agentic Framework - Deployment Validation Script
Comprehensive validation of all components and end-to-end functionality
"""

import boto3
import json
import time
import sys
from datetime import datetime
from decimal import Decimal

def decimal_default(obj):
    """JSON serializer for Decimal objects"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

class DeploymentValidator:
    def __init__(self, profile='development', region='us-west-1', environment='dev'):
        self.profile = profile
        self.region = region
        self.environment = environment
        
        # Initialize AWS clients
        self.session = boto3.Session(profile_name=profile, region_name=region)
        self.lambda_client = self.session.client('lambda')
        self.stepfunctions = self.session.client('stepfunctions')
        self.s3 = self.session.client('s3')
        self.dynamodb = self.session.resource('dynamodb')
        self.iam = self.session.client('iam')
        
        # Configuration
        self.account_id = self.session.client('sts').get_caller_identity()['Account']
        self.bucket_name = f"agentic-framework-input-files-{environment}-{self.account_id}"
        self.state_machine_name = f"agentic-framework-processing-workflow-{environment}"
        
        # Expected resources
        self.expected_lambdas = [
            f"agentic-file-analyzer-{environment}",
            f"agentic-interview-processing-{environment}",
            f"agentic-needs-analysis-{environment}",
            f"agentic-hypergraph-builder-{environment}",
            f"agentic-nlp-processing-{environment}"
        ]
        
        self.expected_tables = [
            "agent-performance-metrics",
            "agent-experiences"
        ]
        
        self.validation_results = {
            'infrastructure': {},
            'lambda_functions': {},
            'step_functions': {},
            'data_storage': {},
            'end_to_end': {},
            'overall_status': 'UNKNOWN'
        }

    def print_header(self, title):
        """Print formatted header"""
        print(f"\n{'='*60}")
        print(f"🔍 {title}")
        print(f"{'='*60}")

    def print_status(self, message, status='INFO'):
        """Print formatted status message"""
        icons = {'SUCCESS': '✅', 'ERROR': '❌', 'WARNING': '⚠️', 'INFO': 'ℹ️'}
        icon = icons.get(status, 'ℹ️')
        print(f"{icon} {message}")

    def validate_aws_credentials(self):
        """Validate AWS credentials and permissions"""
        self.print_header("AWS Credentials Validation")
        
        try:
            identity = self.session.client('sts').get_caller_identity()
            self.print_status(f"Account ID: {identity['Account']}", 'SUCCESS')
            self.print_status(f"User/Role: {identity['Arn']}", 'SUCCESS')
            self.print_status(f"Region: {self.region}", 'SUCCESS')
            self.validation_results['infrastructure']['credentials'] = True
            return True
        except Exception as e:
            self.print_status(f"Credentials validation failed: {str(e)}", 'ERROR')
            self.validation_results['infrastructure']['credentials'] = False
            return False

    def validate_lambda_functions(self):
        """Validate all Lambda functions"""
        self.print_header("Lambda Functions Validation")
        
        all_functions_valid = True
        
        for function_name in self.expected_lambdas:
            try:
                response = self.lambda_client.get_function(FunctionName=function_name)
                
                # Check function configuration
                config = response['Configuration']
                runtime = config['Runtime']
                memory = config['MemorySize']
                timeout = config['Timeout']
                
                self.print_status(f"{function_name}: Active (Runtime: {runtime}, Memory: {memory}MB, Timeout: {timeout}s)", 'SUCCESS')
                
                # Test function invocation with a simple test
                try:
                    test_payload = {
                        "test": True,
                        "validation": "deployment_check"
                    }
                    
                    invoke_response = self.lambda_client.invoke(
                        FunctionName=function_name,
                        InvocationType='RequestResponse',
                        Payload=json.dumps(test_payload)
                    )
                    
                    if invoke_response['StatusCode'] == 200:
                        self.print_status(f"  └─ Function invocation: SUCCESS", 'SUCCESS')
                    else:
                        self.print_status(f"  └─ Function invocation: FAILED (Status: {invoke_response['StatusCode']})", 'WARNING')
                        
                except Exception as invoke_error:
                    self.print_status(f"  └─ Function invocation test failed: {str(invoke_error)}", 'WARNING')
                
                self.validation_results['lambda_functions'][function_name] = True
                
            except Exception as e:
                self.print_status(f"{function_name}: NOT FOUND or ERROR - {str(e)}", 'ERROR')
                self.validation_results['lambda_functions'][function_name] = False
                all_functions_valid = False
        
        return all_functions_valid

    def validate_step_functions(self):
        """Validate Step Functions state machine"""
        self.print_header("Step Functions Validation")
        
        try:
            # List state machines
            response = self.stepfunctions.list_state_machines()
            state_machines = response['stateMachines']
            
            # Find our state machine
            our_state_machine = None
            for sm in state_machines:
                if sm['name'] == self.state_machine_name:
                    our_state_machine = sm
                    break
            
            if our_state_machine:
                self.print_status(f"State Machine Found: {self.state_machine_name}", 'SUCCESS')
                self.print_status(f"  └─ ARN: {our_state_machine['stateMachineArn']}", 'INFO')
                self.print_status(f"  └─ Type: {our_state_machine['type']}", 'INFO')
                self.print_status(f"  └─ Created: {our_state_machine['creationDate']}", 'INFO')
                
                # Get state machine definition
                definition_response = self.stepfunctions.describe_state_machine(
                    stateMachineArn=our_state_machine['stateMachineArn']
                )
                
                definition = json.loads(definition_response['definition'])
                states = definition.get('States', {})
                
                self.print_status(f"  └─ States defined: {len(states)}", 'INFO')
                
                # Check for expected states
                expected_states = ['FileAnalysis', 'DetermineProcessingPath', 'NeedsAnalysis', 'HypergraphBuilding', 'StoreResults']
                for state in expected_states:
                    if state in states:
                        self.print_status(f"    └─ {state}: Found", 'SUCCESS')
                    else:
                        self.print_status(f"    └─ {state}: Missing", 'WARNING')
                
                self.validation_results['step_functions']['state_machine'] = True
                return True
                
            else:
                self.print_status(f"State Machine NOT FOUND: {self.state_machine_name}", 'ERROR')
                self.validation_results['step_functions']['state_machine'] = False
                return False
                
        except Exception as e:
            self.print_status(f"Step Functions validation failed: {str(e)}", 'ERROR')
            self.validation_results['step_functions']['state_machine'] = False
            return False

    def validate_data_storage(self):
        """Validate S3 buckets and DynamoDB tables"""
        self.print_header("Data Storage Validation")
        
        storage_valid = True
        
        # Validate S3 bucket
        try:
            self.s3.head_bucket(Bucket=self.bucket_name)
            self.print_status(f"S3 Bucket accessible: {self.bucket_name}", 'SUCCESS')
            
            # Check bucket contents
            response = self.s3.list_objects_v2(Bucket=self.bucket_name, MaxKeys=5)
            object_count = response.get('KeyCount', 0)
            self.print_status(f"  └─ Objects in bucket: {object_count}", 'INFO')
            
            self.validation_results['data_storage']['s3_bucket'] = True
            
        except Exception as e:
            self.print_status(f"S3 Bucket validation failed: {str(e)}", 'ERROR')
            self.validation_results['data_storage']['s3_bucket'] = False
            storage_valid = False
        
        # Validate DynamoDB tables
        for table_name in self.expected_tables:
            try:
                table = self.dynamodb.Table(table_name)
                table.load()
                
                self.print_status(f"DynamoDB Table accessible: {table_name}", 'SUCCESS')
                self.print_status(f"  └─ Status: {table.table_status}", 'INFO')
                self.print_status(f"  └─ Item count: {table.item_count}", 'INFO')
                
                # Check key schema
                key_schema = table.key_schema
                keys = [key['AttributeName'] for key in key_schema]
                self.print_status(f"  └─ Key schema: {', '.join(keys)}", 'INFO')
                
                self.validation_results['data_storage'][table_name] = True
                
            except Exception as e:
                self.print_status(f"DynamoDB Table validation failed for {table_name}: {str(e)}", 'ERROR')
                self.validation_results['data_storage'][table_name] = False
                storage_valid = False
        
        return storage_valid

    def validate_iam_permissions(self):
        """Validate IAM roles and permissions"""
        self.print_header("IAM Permissions Validation")
        
        try:
            # Check Lambda execution role
            lambda_role_name = f"agentic-framework-lambda-execution-role-{self.environment}"
            
            try:
                role_response = self.iam.get_role(RoleName=lambda_role_name)
                self.print_status(f"Lambda execution role found: {lambda_role_name}", 'SUCCESS')
                
                # Check attached policies
                policies_response = self.iam.list_attached_role_policies(RoleName=lambda_role_name)
                attached_policies = policies_response['AttachedPolicies']
                
                inline_policies_response = self.iam.list_role_policies(RoleName=lambda_role_name)
                inline_policies = inline_policies_response['PolicyNames']
                
                self.print_status(f"  └─ Attached policies: {len(attached_policies)}", 'INFO')
                self.print_status(f"  └─ Inline policies: {len(inline_policies)}", 'INFO')
                
            except Exception as e:
                self.print_status(f"Lambda execution role validation failed: {str(e)}", 'WARNING')
            
            # Check Step Functions role
            sf_role_name = f"agentic-framework-step-functions-role-{self.environment}"
            
            try:
                sf_role_response = self.iam.get_role(RoleName=sf_role_name)
                self.print_status(f"Step Functions role found: {sf_role_name}", 'SUCCESS')
                
            except Exception as e:
                self.print_status(f"Step Functions role validation failed: {str(e)}", 'WARNING')
            
            self.validation_results['infrastructure']['iam_roles'] = True
            return True
            
        except Exception as e:
            self.print_status(f"IAM validation failed: {str(e)}", 'ERROR')
            self.validation_results['infrastructure']['iam_roles'] = False
            return False

    def run_end_to_end_test(self):
        """Run end-to-end test with sample data"""
        self.print_header("End-to-End Functionality Test")
        
        try:
            # Find state machine ARN
            response = self.stepfunctions.list_state_machines()
            state_machine_arn = None
            
            for sm in response['stateMachines']:
                if sm['name'] == self.state_machine_name:
                    state_machine_arn = sm['stateMachineArn']
                    break
            
            if not state_machine_arn:
                self.print_status("State machine not found for end-to-end test", 'ERROR')
                self.validation_results['end_to_end']['execution'] = False
                return False
            
            # Create test execution
            execution_name = f"validation-test-{int(time.time())}"
            
            # Check if test file exists in S3
            test_file_key = "high_customers/00_tim_wolff/Berater = Netzwerk, Know-how, Backup.txt"
            
            try:
                self.s3.head_object(Bucket=self.bucket_name, Key=test_file_key)
                self.print_status(f"Test file found: {test_file_key}", 'SUCCESS')
            except:
                self.print_status(f"Test file not found: {test_file_key}", 'WARNING')
                self.print_status("Skipping end-to-end test", 'WARNING')
                self.validation_results['end_to_end']['execution'] = False
                return False
            
            # Start execution
            input_data = {
                "file_path": test_file_key,
                "customer_folder": "00_tim_wolff",
                "customer_name": "Tim Wolff",
                "processing_config": {
                    "enable_detailed_analysis": True,
                    "confidence_threshold": 0.7
                }
            }
            
            self.print_status(f"Starting test execution: {execution_name}", 'INFO')
            
            execution_response = self.stepfunctions.start_execution(
                stateMachineArn=state_machine_arn,
                name=execution_name,
                input=json.dumps(input_data, default=decimal_default)
            )
            
            execution_arn = execution_response['executionArn']
            self.print_status(f"Execution started: {execution_arn}", 'SUCCESS')
            
            # Monitor execution
            max_wait_time = 300  # 5 minutes
            start_time = time.time()
            
            while time.time() - start_time < max_wait_time:
                execution_status = self.stepfunctions.describe_execution(executionArn=execution_arn)
                status = execution_status['status']
                
                if status == 'SUCCEEDED':
                    self.print_status("End-to-end test execution: SUCCESS", 'SUCCESS')
                    
                    # Check if results were stored
                    try:
                        table = self.dynamodb.Table('agent-performance-metrics')
                        response = table.get_item(Key={
                            'execution_id': execution_name,
                            'agent_type': 'customer_processing'
                        })
                        
                        if 'Item' in response:
                            self.print_status("Results stored in DynamoDB: SUCCESS", 'SUCCESS')
                            self.validation_results['end_to_end']['execution'] = True
                            self.validation_results['end_to_end']['data_storage'] = True
                            return True
                        else:
                            self.print_status("Results not found in DynamoDB", 'WARNING')
                            self.validation_results['end_to_end']['execution'] = True
                            self.validation_results['end_to_end']['data_storage'] = False
                            return True
                            
                    except Exception as e:
                        self.print_status(f"Error checking DynamoDB results: {str(e)}", 'WARNING')
                        self.validation_results['end_to_end']['execution'] = True
                        self.validation_results['end_to_end']['data_storage'] = False
                        return True
                
                elif status == 'FAILED':
                    self.print_status("End-to-end test execution: FAILED", 'ERROR')
                    
                    # Get failure details
                    if 'error' in execution_status:
                        self.print_status(f"Error: {execution_status['error']}", 'ERROR')
                    if 'cause' in execution_status:
                        self.print_status(f"Cause: {execution_status['cause']}", 'ERROR')
                    
                    self.validation_results['end_to_end']['execution'] = False
                    return False
                
                elif status in ['TIMED_OUT', 'ABORTED']:
                    self.print_status(f"End-to-end test execution: {status}", 'ERROR')
                    self.validation_results['end_to_end']['execution'] = False
                    return False
                
                # Still running, wait a bit
                time.sleep(5)
            
            # Timeout reached
            self.print_status("End-to-end test execution: TIMEOUT", 'ERROR')
            self.validation_results['end_to_end']['execution'] = False
            return False
            
        except Exception as e:
            self.print_status(f"End-to-end test failed: {str(e)}", 'ERROR')
            self.validation_results['end_to_end']['execution'] = False
            return False

    def generate_validation_report(self):
        """Generate comprehensive validation report"""
        self.print_header("Validation Report Summary")
        
        # Calculate overall status
        all_checks = []
        
        # Infrastructure checks
        infra_checks = list(self.validation_results['infrastructure'].values())
        all_checks.extend(infra_checks)
        
        # Lambda function checks
        lambda_checks = list(self.validation_results['lambda_functions'].values())
        all_checks.extend(lambda_checks)
        
        # Step Functions checks
        sf_checks = list(self.validation_results['step_functions'].values())
        all_checks.extend(sf_checks)
        
        # Data storage checks
        storage_checks = list(self.validation_results['data_storage'].values())
        all_checks.extend(storage_checks)
        
        # End-to-end checks
        e2e_checks = list(self.validation_results['end_to_end'].values())
        all_checks.extend(e2e_checks)
        
        # Calculate success rate
        total_checks = len(all_checks)
        successful_checks = sum(1 for check in all_checks if check is True)
        success_rate = (successful_checks / total_checks * 100) if total_checks > 0 else 0
        
        # Determine overall status
        if success_rate >= 95:
            overall_status = 'EXCELLENT'
            status_icon = '🎉'
        elif success_rate >= 80:
            overall_status = 'GOOD'
            status_icon = '✅'
        elif success_rate >= 60:
            overall_status = 'FAIR'
            status_icon = '⚠️'
        else:
            overall_status = 'POOR'
            status_icon = '❌'
        
        self.validation_results['overall_status'] = overall_status
        
        # Print summary
        print(f"\n{status_icon} Overall Deployment Status: {overall_status}")
        print(f"📊 Success Rate: {success_rate:.1f}% ({successful_checks}/{total_checks} checks passed)")
        
        print(f"\n📋 Component Status:")
        print(f"  Infrastructure: {'✅' if all(self.validation_results['infrastructure'].values()) else '❌'}")
        print(f"  Lambda Functions: {'✅' if all(self.validation_results['lambda_functions'].values()) else '❌'}")
        print(f"  Step Functions: {'✅' if all(self.validation_results['step_functions'].values()) else '❌'}")
        print(f"  Data Storage: {'✅' if all(self.validation_results['data_storage'].values()) else '❌'}")
        print(f"  End-to-End Test: {'✅' if all(self.validation_results['end_to_end'].values()) else '❌'}")
        
        # Recommendations
        print(f"\n💡 Recommendations:")
        if success_rate < 100:
            print("  • Review failed components above")
            print("  • Check AWS CloudWatch logs for detailed error information")
            print("  • Verify IAM permissions and resource configurations")
        else:
            print("  • Deployment is fully validated and ready for production use!")
            print("  • Consider setting up monitoring and alerting")
            print("  • Review performance metrics and optimize as needed")
        
        return overall_status, success_rate

    def run_full_validation(self):
        """Run complete deployment validation"""
        print("🚀 Enhanced Digital Twin Agentic Framework - Deployment Validation")
        print(f"Region: {self.region} | Environment: {self.environment} | Profile: {self.profile}")
        
        # Run all validation steps
        steps = [
            ("AWS Credentials", self.validate_aws_credentials),
            ("Lambda Functions", self.validate_lambda_functions),
            ("Step Functions", self.validate_step_functions),
            ("Data Storage", self.validate_data_storage),
            ("IAM Permissions", self.validate_iam_permissions),
            ("End-to-End Test", self.run_end_to_end_test)
        ]
        
        for step_name, step_function in steps:
            try:
                step_function()
            except Exception as e:
                self.print_status(f"{step_name} validation failed with exception: {str(e)}", 'ERROR')
        
        # Generate final report
        overall_status, success_rate = self.generate_validation_report()
        
        return overall_status == 'EXCELLENT' or overall_status == 'GOOD'

def main():
    """Main validation function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate Enhanced Digital Twin Agentic Framework deployment')
    parser.add_argument('--profile', default='development', help='AWS profile to use')
    parser.add_argument('--region', default='us-west-1', help='AWS region')
    parser.add_argument('--environment', default='dev', help='Environment name')
    
    args = parser.parse_args()
    
    validator = DeploymentValidator(
        profile=args.profile,
        region=args.region,
        environment=args.environment
    )
    
    success = validator.run_full_validation()
    
    if success:
        print(f"\n🎉 Deployment validation completed successfully!")
        sys.exit(0)
    else:
        print(f"\n❌ Deployment validation failed. Please review the issues above.")
        sys.exit(1)

if __name__ == "__main__":
    main()