#!/usr/bin/env python3
"""
Enhanced Digital Twin Agentic Framework - Comprehensive S3 Files Test
Tests all files in the S3 high_customers folder through the complete framework
"""

import boto3
import json
import time
import sys
import argparse
from datetime import datetime
from typing import Dict, List, Any
import uuid
import re

class ComprehensiveS3Tester:
    def __init__(self, profile: str = 'development', region: str = 'us-west-1', environment: str = 'dev'):
        self.profile = profile
        self.region = region
        self.environment = environment
        
        # Initialize AWS clients
        self.session = boto3.Session(profile_name=profile, region_name=region)
        self.stepfunctions = self.session.client('stepfunctions')
        self.dynamodb = self.session.resource('dynamodb')
        self.s3 = self.session.client('s3')
        
        # Configuration
        self.account_id = self.session.client('sts').get_caller_identity()['Account']
        self.bucket_name = f"agentic-framework-input-files-{environment}-{self.account_id}"
        self.state_machine_name = f"agentic-framework-processing-workflow-{environment}"
        self.performance_table = self.dynamodb.Table('agent-performance-metrics')
        
        # Test results
        self.test_results = {
            'tests': [],
            'summary': {},
            'errors': []
        }

    def print_status(self, message: str, status: str = 'INFO'):
        """Print formatted status message"""
        icons = {'SUCCESS': '✅', 'ERROR': '❌', 'WARNING': '⚠️', 'INFO': 'ℹ️', 'RUNNING': '🔄'}
        icon = icons.get(status, 'ℹ️')
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"[{timestamp}] {icon} {message}")

    def get_all_s3_files(self) -> List[Dict[str, str]]:
        """Get all files from S3 high_customers folder"""
        try:
            response = self.s3.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix='high_customers/'
            )
            
            files = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    key = obj['Key']
                    if key.endswith('.txt') and not key.endswith('/'):
                        # Extract customer info from path
                        path_parts = key.split('/')
                        if len(path_parts) >= 3:
                            customer_folder = path_parts[1]
                            filename = path_parts[-1]
                            
                            # Extract customer name and ID
                            customer_match = re.match(r'(\d+)_(.+)', customer_folder)
                            if customer_match:
                                customer_id = customer_match.group(1)
                                customer_name = customer_match.group(2).replace('_', ' ').title()
                            else:
                                customer_id = "unknown"
                                customer_name = customer_folder.replace('_', ' ').title()
                            
                            files.append({
                                'key': key,
                                'customer_id': customer_id,
                                'customer_name': customer_name,
                                'filename': filename,
                                'size': obj['Size']
                            })
            
            # Sort by customer ID and filename
            files.sort(key=lambda x: (x['customer_id'], x['filename']))
            return files
            
        except Exception as e:
            self.print_status(f"Error listing S3 files: {str(e)}", 'ERROR')
            return []

    def get_state_machine_arn(self) -> str:
        """Get the Step Functions state machine ARN"""
        try:
            response = self.stepfunctions.list_state_machines()
            for state_machine in response['stateMachines']:
                if state_machine['name'] == self.state_machine_name:
                    return state_machine['stateMachineArn']
            return None
        except Exception as e:
            self.print_status(f"Error getting state machine ARN: {str(e)}", 'ERROR')
            return None

    def start_execution(self, file_info: Dict[str, str]) -> str:
        """Start a Step Functions execution for a file"""
        try:
            state_machine_arn = self.get_state_machine_arn()
            if not state_machine_arn:
                raise Exception("State machine not found")
            
            execution_name = f"s3-test-{file_info['customer_id']}-{int(time.time())}-{uuid.uuid4().hex[:8]}"
            
            input_data = {
                "file_path": file_info['key'],
                "customer_folder": f"{file_info['customer_id']}_{file_info['customer_name'].lower().replace(' ', '_')}",
                "customer_name": file_info['customer_name'],
                "processing_config": {
                    "enable_detailed_analysis": True,
                    "confidence_threshold": 0.7,
                    "test_execution": True
                }
            }
            
            response = self.stepfunctions.start_execution(
                stateMachineArn=state_machine_arn,
                name=execution_name,
                input=json.dumps(input_data)
            )
            
            return execution_name
            
        except Exception as e:
            self.print_status(f"Error starting execution: {str(e)}", 'ERROR')
            return None

    def monitor_execution(self, execution_name: str, timeout: int = 300) -> Dict[str, Any]:
        """Monitor execution until completion"""
        try:
            state_machine_arn = self.get_state_machine_arn()
            execution_arn = f"{state_machine_arn.replace(':stateMachine:', ':execution:')}:{execution_name}"
            
            start_time = time.time()
            last_status_time = start_time
            
            while time.time() - start_time < timeout:
                response = self.stepfunctions.describe_execution(
                    executionArn=execution_arn
                )
                
                status = response['status']
                
                # Print status updates every 10 seconds
                if time.time() - last_status_time >= 10:
                    elapsed = time.time() - start_time
                    self.print_status(f"Execution running... ({elapsed:.1f}s)", 'RUNNING')
                    last_status_time = time.time()
                
                if status in ['SUCCEEDED', 'FAILED', 'TIMED_OUT', 'ABORTED']:
                    elapsed_time = time.time() - start_time
                    
                    result = {
                        'status': status,
                        'execution_time': elapsed_time,
                        'execution_arn': execution_arn
                    }
                    
                    if status == 'SUCCEEDED':
                        result['output'] = json.loads(response.get('output', '{}'))
                    elif status == 'FAILED':
                        result['error'] = response.get('error', 'Unknown error')
                        result['cause'] = response.get('cause', 'Unknown cause')
                    
                    return result
                
                time.sleep(2)
            
            # Timeout
            return {
                'status': 'TIMEOUT',
                'execution_time': timeout,
                'execution_arn': execution_arn,
                'error': f'Execution timed out after {timeout} seconds'
            }
            
        except Exception as e:
            return {
                'status': 'ERROR',
                'execution_time': 0,
                'error': str(e)
            }

    def verify_results_in_dynamodb(self, execution_name: str) -> bool:
        """Verify that results were stored in DynamoDB"""
        try:
            response = self.performance_table.get_item(
                Key={'execution_id': execution_name}
            )
            return 'Item' in response
        except Exception as e:
            self.print_status(f"Error checking DynamoDB: {str(e)}", 'WARNING')
            return False

    def test_single_file(self, file_info: Dict[str, str], test_number: int, total_tests: int) -> Dict[str, Any]:
        """Test a single file through the complete framework"""
        
        self.print_status(f"📋 Test {test_number}/{total_tests}: {file_info['customer_name']}")
        self.print_status("----------------------------------------")
        self.print_status(f"Testing: {file_info['customer_name']} ({file_info['customer_id']})")
        self.print_status(f"File: {file_info['key']}")
        self.print_status(f"Size: {file_info['size']:,} bytes")
        
        test_result = {
            'customer_name': file_info['customer_name'],
            'customer_id': file_info['customer_id'],
            'filename': file_info['filename'],
            'file_key': file_info['key'],
            'file_size': file_info['size'],
            'status': 'UNKNOWN',
            'execution_time': 0,
            'execution_name': None,
            'error': None,
            'steps': {
                'file_verification': False,
                'execution_start': False,
                'execution_monitoring': False,
                'results_storage': False
            }
        }
        
        try:
            # Step 1: Verify file exists in S3
            try:
                self.s3.head_object(Bucket=self.bucket_name, Key=file_info['key'])
                test_result['steps']['file_verification'] = True
                self.print_status("File verified in S3", 'SUCCESS')
            except Exception as e:
                test_result['error'] = f"File not found in S3: {str(e)}"
                self.print_status(f"File not found in S3: {str(e)}", 'ERROR')
                return test_result
            
            # Step 2: Start execution
            execution_name = self.start_execution(file_info)
            if execution_name:
                test_result['execution_name'] = execution_name
                test_result['steps']['execution_start'] = True
                self.print_status(f"Starting execution: {execution_name}", 'RUNNING')
            else:
                test_result['error'] = "Failed to start execution"
                self.print_status("Failed to start execution", 'ERROR')
                return test_result
            
            # Step 3: Monitor execution
            execution_result = self.monitor_execution(execution_name)
            test_result['execution_time'] = execution_result['execution_time']
            
            if execution_result['status'] == 'SUCCEEDED':
                test_result['steps']['execution_monitoring'] = True
                self.print_status("Execution completed successfully", 'SUCCESS')
                test_result['status'] = 'SUCCESS'
                
                # Step 4: Verify results in DynamoDB
                if self.verify_results_in_dynamodb(execution_name):
                    test_result['steps']['results_storage'] = True
                    self.print_status("Results verified in DynamoDB", 'SUCCESS')
                else:
                    self.print_status("Results not found in DynamoDB", 'WARNING')
                
                self.print_status(f"Test completed: SUCCESS ({execution_result['execution_time']:.1f}s)", 'SUCCESS')
                
            else:
                test_result['status'] = 'FAILED'
                test_result['error'] = execution_result.get('error', 'Execution failed')
                self.print_status("Execution failed", 'ERROR')
                if 'error' in execution_result:
                    self.print_status(f"Error: {execution_result['error']}", 'ERROR')
        
        except Exception as e:
            test_result['status'] = 'ERROR'
            test_result['error'] = str(e)
            self.print_status(f"Test error: {str(e)}", 'ERROR')
        
        return test_result

    def run_comprehensive_s3_test(self, max_files: int = None, customer_filter: str = None) -> Dict[str, Any]:
        """Run comprehensive test on all S3 files"""
        
        self.print_status("🚀 Starting Comprehensive S3 Files Test")
        self.print_status("=" * 60)
        
        # Get all files
        all_files = self.get_all_s3_files()
        
        if not all_files:
            self.print_status("No files found in S3", 'ERROR')
            return {'summary': {'success_rate': 0, 'total_tests': 0}}
        
        # Apply filters
        if customer_filter:
            all_files = [f for f in all_files if customer_filter.lower() in f['customer_name'].lower()]
        
        if max_files:
            all_files = all_files[:max_files]
        
        self.print_status(f"Found {len(all_files)} files to test")
        
        # Run tests
        successful_tests = 0
        failed_tests = 0
        total_execution_time = 0
        
        for i, file_info in enumerate(all_files, 1):
            test_result = self.test_single_file(file_info, i, len(all_files))
            self.test_results['tests'].append(test_result)
            
            if test_result['status'] == 'SUCCESS':
                successful_tests += 1
            else:
                failed_tests += 1
            
            total_execution_time += test_result['execution_time']
            
            # Wait between tests to avoid overwhelming the system
            if i < len(all_files):
                self.print_status("Waiting 10 seconds before next test...")
                time.sleep(10)
        
        # Calculate summary
        success_rate = (successful_tests / len(all_files)) * 100 if all_files else 0
        avg_execution_time = total_execution_time / len(all_files) if all_files else 0
        
        self.test_results['summary'] = {
            'total_tests': len(all_files),
            'successful': successful_tests,
            'failed': failed_tests,
            'success_rate': success_rate,
            'average_execution_time': avg_execution_time,
            'total_execution_time': total_execution_time,
            'test_timestamp': datetime.now().isoformat()
        }
        
        return self.test_results

    def print_detailed_report(self):
        """Print detailed test report"""
        print("\n" + "=" * 80)
        print("🎯 COMPREHENSIVE S3 FILES TEST REPORT")
        print("=" * 80)
        
        summary = self.test_results['summary']
        
        print(f"📊 Test Summary:")
        print(f"   Total Tests: {summary['total_tests']}")
        print(f"   Successful: {summary['successful']} ✅")
        print(f"   Failed: {summary['failed']} ❌")
        print(f"   Success Rate: {summary['success_rate']:.1f}%")
        print(f"   Average Execution Time: {summary['average_execution_time']:.1f}s")
        print(f"   Total Execution Time: {summary['total_execution_time']:.1f}s")
        print(f"   Test Timestamp: {summary['test_timestamp']}")
        
        print(f"\n📋 Detailed Results:")
        print("-" * 80)
        
        for i, test in enumerate(self.test_results['tests'], 1):
            status_icon = "✅" if test['status'] == 'SUCCESS' else "❌"
            print(f"\n{i}. {test['customer_name']} ({test['customer_id']}) {status_icon}")
            print(f"   File: {test['filename']}")
            print(f"   Size: {test['file_size']:,} bytes")
            print(f"   Status: {test['status']}")
            print(f"   Execution Time: {test['execution_time']:.1f}s")
            if test['execution_name']:
                print(f"   Execution Name: {test['execution_name']}")
            
            # Print step details
            steps = test['steps']
            print(f"     └─ File Verification: {'✅' if steps['file_verification'] else '❌'}")
            print(f"     └─ Execution Start: {'✅' if steps['execution_start'] else '❌'}")
            print(f"     └─ Execution Monitoring: {'✅' if steps['execution_monitoring'] else '❌'}")
            print(f"     └─ Results Storage: {'✅' if steps['results_storage'] else '❌'}")
            
            if test['error']:
                print(f"   ❌ Error: {test['error']}")
        
        print("\n" + "=" * 80)
        
        # Overall assessment
        if summary['success_rate'] >= 90:
            print("🎉 EXCELLENT: Nearly all tests passed successfully!")
        elif summary['success_rate'] >= 70:
            print("👍 GOOD: Most tests passed, minor issues to investigate")
        elif summary['success_rate'] >= 50:
            print("⚠️  FAIR: Mixed results, investigation needed")
        else:
            print("❌ POOR: Multiple test failures, investigation required")
        
        print("=" * 80)

def main():
    parser = argparse.ArgumentParser(description='Test all S3 files through Enhanced Digital Twin Framework')
    parser.add_argument('--profile', default='development', help='AWS profile to use')
    parser.add_argument('--region', default='us-west-1', help='AWS region')
    parser.add_argument('--environment', default='dev', help='Environment name')
    parser.add_argument('--max-files', type=int, help='Maximum number of files to test')
    parser.add_argument('--customer', help='Filter by customer name (partial match)')
    
    args = parser.parse_args()
    
    try:
        # Initialize tester
        tester = ComprehensiveS3Tester(
            profile=args.profile,
            region=args.region,
            environment=args.environment
        )
        
        # Run comprehensive test
        results = tester.run_comprehensive_s3_test(
            max_files=args.max_files,
            customer_filter=args.customer
        )
        
        # Print detailed report
        tester.print_detailed_report()
        
        # Exit with appropriate code
        summary = results['summary']
        if summary['success_rate'] >= 80:
            sys.exit(0)  # Success
        else:
            sys.exit(1)  # Failure
            
    except KeyboardInterrupt:
        print("\n❌ Test cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Test failed with error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()