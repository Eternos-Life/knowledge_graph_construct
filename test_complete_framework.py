#!/usr/bin/env python3
"""
Enhanced Digital Twin Agentic Framework - Complete End-to-End Test
Tests the entire framework with customer example files
"""

import boto3
import json
import time
import sys
import argparse
from datetime import datetime
from typing import Dict, List, Any
import uuid

class FrameworkTester:
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

    def get_state_machine_arn(self) -> str:
        """Get the Step Functions state machine ARN"""
        try:
            response = self.stepfunctions.list_state_machines()
            for sm in response['stateMachines']:
                if sm['name'] == self.state_machine_name:
                    return sm['stateMachineArn']
            raise Exception(f"State machine not found: {self.state_machine_name}")
        except Exception as e:
            raise Exception(f"Failed to get state machine ARN: {str(e)}")

    def verify_file_exists(self, file_path: str) -> bool:
        """Verify that the test file exists in S3"""
        try:
            self.s3.head_object(Bucket=self.bucket_name, Key=file_path)
            return True
        except:
            return False

    def start_execution(self, file_path: str, customer_folder: str, customer_name: str) -> Dict[str, Any]:
        """Start a Step Functions execution"""
        try:
            state_machine_arn = self.get_state_machine_arn()
            
            # Generate unique execution name
            execution_name = f"test-{customer_folder}-{int(time.time())}-{str(uuid.uuid4())[:8]}"
            
            # Prepare input data
            input_data = {
                "file_path": file_path,
                "customer_folder": customer_folder,
                "customer_name": customer_name,
                "processing_config": {
                    "enable_detailed_analysis": True,
                    "confidence_threshold": 0.7,
                    "test_execution": True
                }
            }
            
            self.print_status(f"Starting execution: {execution_name}", 'RUNNING')
            
            # Start execution
            response = self.stepfunctions.start_execution(
                stateMachineArn=state_machine_arn,
                name=execution_name,
                input=json.dumps(input_data, default=str)
            )
            
            return {
                'execution_arn': response['executionArn'],
                'execution_name': execution_name,
                'start_time': time.time(),
                'input_data': input_data
            }
            
        except Exception as e:
            raise Exception(f"Failed to start execution: {str(e)}")

    def monitor_execution(self, execution_arn: str, timeout: int = 300) -> Dict[str, Any]:
        """Monitor Step Functions execution until completion"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                response = self.stepfunctions.describe_execution(executionArn=execution_arn)
                status = response['status']
                
                if status == 'SUCCEEDED':
                    self.print_status("Execution completed successfully", 'SUCCESS')
                    return {
                        'status': 'SUCCEEDED',
                        'execution_time': time.time() - start_time,
                        'output': response.get('output'),
                        'response': response
                    }
                elif status == 'FAILED':
                    self.print_status("Execution failed", 'ERROR')
                    return {
                        'status': 'FAILED',
                        'execution_time': time.time() - start_time,
                        'error': response.get('error', 'Unknown error'),
                        'cause': response.get('cause', 'Unknown cause'),
                        'response': response
                    }
                elif status in ['TIMED_OUT', 'ABORTED']:
                    self.print_status(f"Execution {status.lower()}", 'ERROR')
                    return {
                        'status': status,
                        'execution_time': time.time() - start_time,
                        'response': response
                    }
                
                # Still running
                elapsed = time.time() - start_time
                self.print_status(f"Execution running... ({elapsed:.1f}s)", 'RUNNING')
                time.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                return {
                    'status': 'ERROR',
                    'execution_time': time.time() - start_time,
                    'error': str(e)
                }
        
        # Timeout reached
        return {
            'status': 'TIMEOUT',
            'execution_time': timeout,
            'error': f'Execution timed out after {timeout} seconds'
        }

    def verify_results_stored(self, execution_name: str) -> Dict[str, Any]:
        """Verify that results were stored in DynamoDB"""
        try:
            # Check for results in performance metrics table
            response = self.performance_table.get_item(
                Key={
                    'execution_id': execution_name,
                    'agent_type': 'customer_processing'
                }
            )
            
            if 'Item' in response:
                item = response['Item']
                return {
                    'stored': True,
                    'processing_status': item.get('processing_status', 'unknown'),
                    'content_type': item.get('content_type', 'unknown'),
                    'customer_name': item.get('customer_name', 'unknown'),
                    'timestamp': item.get('timestamp', 'unknown'),
                    'has_file_analysis': 'file_analysis' in item,
                    'has_content_processing': 'content_processing' in item,
                    'has_needs_analysis': 'needs_analysis' in item,
                    'has_hypergraph_data': 'hypergraph_data' in item
                }
            else:
                return {'stored': False, 'error': 'No results found in DynamoDB'}
                
        except Exception as e:
            return {'stored': False, 'error': str(e)}

    def analyze_execution_history(self, execution_arn: str) -> Dict[str, Any]:
        """Analyze the execution history to understand the processing flow"""
        try:
            response = self.stepfunctions.get_execution_history(executionArn=execution_arn)
            events = response['events']
            
            analysis = {
                'total_events': len(events),
                'states_executed': [],
                'lambda_invocations': [],
                'errors': [],
                'execution_flow': []
            }
            
            for event in events:
                event_type = event['type']
                
                if event_type == 'StateEntered':
                    state_name = event['stateEnteredEventDetails']['name']
                    analysis['states_executed'].append(state_name)
                    analysis['execution_flow'].append(f"Entered: {state_name}")
                
                elif event_type == 'LambdaFunctionScheduled':
                    resource = event['lambdaFunctionScheduledEventDetails']['resource']
                    analysis['lambda_invocations'].append(resource)
                    analysis['execution_flow'].append(f"Lambda: {resource}")
                
                elif event_type in ['ExecutionFailed', 'TaskFailed', 'StateExited']:
                    if 'error' in event.get('executionFailedEventDetails', {}):
                        analysis['errors'].append(event)
            
            return analysis
            
        except Exception as e:
            return {'error': str(e)}

    def run_single_test(self, file_path: str, customer_folder: str, customer_name: str, expected_processing_path: str) -> Dict[str, Any]:
        """Run a single end-to-end test"""
        test_start_time = time.time()
        
        test_result = {
            'file_path': file_path,
            'customer_folder': customer_folder,
            'customer_name': customer_name,
            'expected_processing_path': expected_processing_path,
            'start_time': datetime.now().isoformat(),
            'status': 'UNKNOWN',
            'execution_time': 0,
            'stages': {}
        }
        
        try:
            # Stage 1: Verify file exists
            self.print_status(f"Testing: {customer_name} ({customer_folder})", 'INFO')
            self.print_status(f"File: {file_path}", 'INFO')
            
            if not self.verify_file_exists(file_path):
                test_result['status'] = 'FAILED'
                test_result['error'] = f'File not found in S3: {file_path}'
                self.print_status(f"File not found: {file_path}", 'ERROR')
                return test_result
            
            test_result['stages']['file_verification'] = {'status': 'SUCCESS'}
            self.print_status("File verified in S3", 'SUCCESS')
            
            # Stage 2: Start execution
            execution_info = self.start_execution(file_path, customer_folder, customer_name)
            test_result['execution_arn'] = execution_info['execution_arn']
            test_result['execution_name'] = execution_info['execution_name']
            test_result['stages']['execution_start'] = {'status': 'SUCCESS', 'execution_name': execution_info['execution_name']}
            
            # Stage 3: Monitor execution
            execution_result = self.monitor_execution(execution_info['execution_arn'])
            test_result['stages']['execution_monitoring'] = execution_result
            
            if execution_result['status'] != 'SUCCEEDED':
                test_result['status'] = 'FAILED'
                test_result['error'] = execution_result.get('error', 'Execution failed')
                return test_result
            
            # Stage 4: Verify results stored
            storage_result = self.verify_results_stored(execution_info['execution_name'])
            test_result['stages']['results_storage'] = storage_result
            
            if not storage_result.get('stored', False):
                test_result['status'] = 'PARTIAL'
                test_result['warning'] = 'Execution succeeded but results not found in DynamoDB'
            else:
                test_result['status'] = 'SUCCESS'
                self.print_status("Results verified in DynamoDB", 'SUCCESS')
            
            # Stage 5: Analyze execution history
            history_analysis = self.analyze_execution_history(execution_info['execution_arn'])
            test_result['stages']['execution_analysis'] = history_analysis
            
            # Calculate total execution time
            test_result['execution_time'] = time.time() - test_start_time
            
            self.print_status(f"Test completed: {test_result['status']} ({test_result['execution_time']:.1f}s)", 
                            'SUCCESS' if test_result['status'] == 'SUCCESS' else 'WARNING')
            
            return test_result
            
        except Exception as e:
            test_result['status'] = 'ERROR'
            test_result['error'] = str(e)
            test_result['execution_time'] = time.time() - test_start_time
            self.print_status(f"Test failed with error: {str(e)}", 'ERROR')
            return test_result

    def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run comprehensive test with multiple customer files"""
        self.print_status("🚀 Starting Comprehensive Framework Test", 'INFO')
        self.print_status("=" * 60, 'INFO')
        
        # Define test cases
        test_cases = [
            {
                'file_path': 'high_customers/00_tim_wolff/Berater = Netzwerk, Know-how, Backup.txt',
                'customer_folder': '00_tim_wolff',
                'customer_name': 'Tim Wolff',
                'expected_processing_path': 'FinancialProcessing'
            },
            {
                'file_path': 'high_customers/01_jon_fortt/Intel CEO Pat Gelsinger 102621 Full Fortt Knox 1 1 Innovation Interview.txt',
                'customer_folder': '01_jon_fortt',
                'customer_name': 'Jon Fortt',
                'expected_processing_path': 'InterviewProcessing'
            }
        ]
        
        # Run tests
        for i, test_case in enumerate(test_cases, 1):
            self.print_status(f"\n📋 Test {i}/{len(test_cases)}: {test_case['customer_name']}", 'INFO')
            self.print_status("-" * 40, 'INFO')
            
            result = self.run_single_test(**test_case)
            self.test_results['tests'].append(result)
            
            # Add delay between tests to avoid throttling
            if i < len(test_cases):
                self.print_status("Waiting 30 seconds before next test...", 'INFO')
                time.sleep(30)
        
        # Generate summary
        self.generate_test_summary()
        
        return self.test_results

    def generate_test_summary(self):
        """Generate comprehensive test summary"""
        tests = self.test_results['tests']
        total_tests = len(tests)
        successful_tests = len([t for t in tests if t['status'] == 'SUCCESS'])
        partial_tests = len([t for t in tests if t['status'] == 'PARTIAL'])
        failed_tests = len([t for t in tests if t['status'] in ['FAILED', 'ERROR']])
        
        avg_execution_time = sum(t['execution_time'] for t in tests) / total_tests if total_tests > 0 else 0
        
        self.test_results['summary'] = {
            'total_tests': total_tests,
            'successful_tests': successful_tests,
            'partial_tests': partial_tests,
            'failed_tests': failed_tests,
            'success_rate': (successful_tests / total_tests * 100) if total_tests > 0 else 0,
            'average_execution_time': avg_execution_time,
            'test_timestamp': datetime.now().isoformat()
        }

    def print_detailed_report(self):
        """Print detailed test report"""
        print("\n" + "=" * 80)
        print("🎯 ENHANCED DIGITAL TWIN AGENTIC FRAMEWORK - TEST REPORT")
        print("=" * 80)
        
        summary = self.test_results['summary']
        print(f"📊 Test Summary:")
        print(f"   Total Tests: {summary['total_tests']}")
        print(f"   Successful: {summary['successful_tests']} ✅")
        print(f"   Partial: {summary['partial_tests']} ⚠️")
        print(f"   Failed: {summary['failed_tests']} ❌")
        print(f"   Success Rate: {summary['success_rate']:.1f}%")
        print(f"   Average Execution Time: {summary['average_execution_time']:.1f}s")
        print(f"   Test Timestamp: {summary['test_timestamp']}")
        
        print(f"\n📋 Detailed Results:")
        print("-" * 80)
        
        for i, test in enumerate(self.test_results['tests'], 1):
            status_icon = {'SUCCESS': '✅', 'PARTIAL': '⚠️', 'FAILED': '❌', 'ERROR': '❌'}.get(test['status'], '❓')
            
            print(f"\n{i}. {test['customer_name']} ({test['customer_folder']}) {status_icon}")
            print(f"   File: {test['file_path']}")
            print(f"   Status: {test['status']}")
            print(f"   Execution Time: {test['execution_time']:.1f}s")
            
            if 'execution_name' in test:
                print(f"   Execution Name: {test['execution_name']}")
            
            # Show stage results
            stages = test.get('stages', {})
            for stage_name, stage_result in stages.items():
                stage_status = stage_result.get('status', 'UNKNOWN')
                stage_icon = {'SUCCESS': '✅', 'FAILED': '❌', 'ERROR': '❌'}.get(stage_status, '❓')
                print(f"     └─ {stage_name.replace('_', ' ').title()}: {stage_icon}")
                
                # Show additional details for storage results
                if stage_name == 'results_storage' and stage_result.get('stored'):
                    print(f"        └─ Processing Status: {stage_result.get('processing_status', 'unknown')}")
                    print(f"        └─ Content Type: {stage_result.get('content_type', 'unknown')}")
                    print(f"        └─ Has File Analysis: {'✅' if stage_result.get('has_file_analysis') else '❌'}")
                    print(f"        └─ Has Content Processing: {'✅' if stage_result.get('has_content_processing') else '❌'}")
                    print(f"        └─ Has Needs Analysis: {'✅' if stage_result.get('has_needs_analysis') else '❌'}")
                    print(f"        └─ Has Hypergraph Data: {'✅' if stage_result.get('has_hypergraph_data') else '❌'}")
            
            # Show errors if any
            if 'error' in test:
                print(f"   ❌ Error: {test['error']}")
            if 'warning' in test:
                print(f"   ⚠️ Warning: {test['warning']}")
        
        print("\n" + "=" * 80)
        
        # Overall assessment
        if summary['success_rate'] >= 100:
            print("🎉 EXCELLENT: All tests passed successfully!")
        elif summary['success_rate'] >= 80:
            print("✅ GOOD: Most tests passed with minor issues")
        elif summary['success_rate'] >= 50:
            print("⚠️ FAIR: Some tests failed, review needed")
        else:
            print("❌ POOR: Multiple test failures, investigation required")
        
        print("=" * 80)

def main():
    parser = argparse.ArgumentParser(description='Test Enhanced Digital Twin Agentic Framework')
    parser.add_argument('--profile', default='development', help='AWS profile to use')
    parser.add_argument('--region', default='us-west-1', help='AWS region')
    parser.add_argument('--environment', default='dev', help='Environment name')
    parser.add_argument('--timeout', type=int, default=300, help='Execution timeout in seconds')
    
    args = parser.parse_args()
    
    try:
        # Initialize tester
        tester = FrameworkTester(
            profile=args.profile,
            region=args.region,
            environment=args.environment
        )
        
        # Run comprehensive test
        results = tester.run_comprehensive_test()
        
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