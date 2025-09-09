#!/usr/bin/env python3
"""
Test Additional Customer Files - Test different content from existing customers
"""

import boto3
import json
import time
import sys
from datetime import datetime
from typing import Dict, List, Any
import uuid

class AdditionalFilesTester:
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
        
        # Test results
        self.test_results = []

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
            execution_name = f"additional-test-{customer_folder}-{int(time.time())}-{str(uuid.uuid4())[:8]}"
            
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

    def extract_hypergraph_from_execution(self, execution_arn: str):
        """Extract hypergraph data from Step Functions execution history"""
        try:
            response = self.stepfunctions.get_execution_history(executionArn=execution_arn)
            events = response['events']
            
            # Look for the hypergraph builder task completion
            for event in events:
                if event['type'] == 'TaskSucceeded':
                    details = event.get('taskSucceededEventDetails', {})
                    output = details.get('output', '{}')
                    
                    try:
                        output_data = json.loads(output)
                        
                        # Check if this is the hypergraph result
                        if 'hypergraph_result' in output_data:
                            hg_result = output_data['hypergraph_result']
                            if 'Payload' in hg_result:
                                payload = hg_result['Payload']
                                if 'body' in payload:
                                    body_str = payload['body']
                                    body_data = json.loads(body_str)
                                    if 'result' in body_data:
                                        return body_data['result']
                        
                        # Also check direct payload structure
                        if 'Payload' in output_data:
                            payload = output_data['Payload']
                            if 'body' in payload:
                                body_str = payload['body']
                                body_data = json.loads(body_str)
                                if 'result' in body_data and 'hypernodes' in body_data['result']:
                                    return body_data['result']
                                    
                    except json.JSONDecodeError:
                        continue
                        
            return None
            
        except Exception as e:
            print(f"Error extracting hypergraph: {str(e)}")
            return None

    def run_single_test(self, file_path: str, customer_folder: str, customer_name: str, content_description: str) -> Dict[str, Any]:
        """Run a single test with a specific file"""
        test_start_time = time.time()
        
        test_result = {
            'file_path': file_path,
            'customer_folder': customer_folder,
            'customer_name': customer_name,
            'content_description': content_description,
            'start_time': datetime.now().isoformat(),
            'status': 'UNKNOWN',
            'execution_time': 0
        }
        
        try:
            # Verify file exists
            self.print_status(f"Testing: {customer_name} - {content_description}", 'INFO')
            self.print_status(f"File: {file_path}", 'INFO')
            
            if not self.verify_file_exists(file_path):
                test_result['status'] = 'FAILED'
                test_result['error'] = f'File not found in S3: {file_path}'
                self.print_status(f"File not found: {file_path}", 'ERROR')
                return test_result
            
            self.print_status("File verified in S3", 'SUCCESS')
            
            # Start execution
            execution_info = self.start_execution(file_path, customer_folder, customer_name)
            test_result['execution_arn'] = execution_info['execution_arn']
            test_result['execution_name'] = execution_info['execution_name']
            
            # Monitor execution
            execution_result = self.monitor_execution(execution_info['execution_arn'])
            
            if execution_result['status'] != 'SUCCEEDED':
                test_result['status'] = 'FAILED'
                test_result['error'] = execution_result.get('error', 'Execution failed')
                return test_result
            
            # Extract hypergraph data
            hypergraph_data = self.extract_hypergraph_from_execution(execution_info['execution_arn'])
            test_result['hypergraph_data'] = hypergraph_data
            
            if hypergraph_data:
                nodes = hypergraph_data.get('hypernodes', [])
                edges = hypergraph_data.get('hyperedges', [])
                metrics = hypergraph_data.get('graph_metrics', {})
                
                test_result['nodes_count'] = len(nodes)
                test_result['edges_count'] = len(edges)
                test_result['quality_score'] = hypergraph_data.get('graph_insights', {}).get('quality_score', 0)
                test_result['node_types'] = metrics.get('node_type_distribution', {})
                test_result['edge_types'] = metrics.get('edge_type_distribution', {})
                
                test_result['status'] = 'SUCCESS'
                self.print_status(f"Hypergraph extracted: {len(nodes)} nodes, {len(edges)} edges", 'SUCCESS')
            else:
                test_result['status'] = 'PARTIAL'
                test_result['warning'] = 'Execution succeeded but hypergraph data not found'
            
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

    def run_additional_files_test(self) -> Dict[str, Any]:
        """Run tests with different files from existing customers"""
        self.print_status("🚀 Starting Additional Files Test", 'INFO')
        self.print_status("=" * 60, 'INFO')
        
        # Define test cases with different content types
        test_cases = [
            {
                'file_path': 'high_customers/00_tim_wolff/Die Bedeutung eines positiven Umfelds.txt',
                'customer_folder': '00_tim_wolff',
                'customer_name': 'Tim Wolff',
                'content_description': 'Positive Environment & Mindset Content'
            },
            {
                'file_path': 'high_customers/01_jon_fortt/Mathilde Collin Front CEO A Fortt Knox Conversation.txt',
                'customer_folder': '01_jon_fortt',
                'customer_name': 'Jon Fortt',
                'content_description': 'CEO Interview - Front CEO Mathilde Collin'
            }
        ]
        
        # Run tests
        for i, test_case in enumerate(test_cases, 1):
            self.print_status(f"\n📋 Test {i}/{len(test_cases)}: {test_case['customer_name']}", 'INFO')
            self.print_status(f"Content: {test_case['content_description']}", 'INFO')
            self.print_status("-" * 40, 'INFO')
            
            result = self.run_single_test(**test_case)
            self.test_results.append(result)
            
            # Add delay between tests to avoid throttling
            if i < len(test_cases):
                self.print_status("Waiting 30 seconds before next test...", 'INFO')
                time.sleep(30)
        
        return self.test_results

    def print_comparison_report(self):
        """Print detailed comparison report"""
        print("\n" + "=" * 80)
        print("🎯 ADDITIONAL FILES TEST - COMPARISON REPORT")
        print("=" * 80)
        
        successful_tests = [t for t in self.test_results if t['status'] == 'SUCCESS']
        
        if not successful_tests:
            print("❌ No successful tests to compare")
            return
        
        print(f"📊 Test Summary:")
        print(f"   Total Tests: {len(self.test_results)}")
        print(f"   Successful: {len(successful_tests)} ✅")
        print(f"   Success Rate: {len(successful_tests)/len(self.test_results)*100:.1f}%")
        
        print(f"\n📋 Detailed Comparison:")
        print("-" * 80)
        
        for i, test in enumerate(successful_tests, 1):
            print(f"\n{i}. {test['customer_name']} - {test['content_description']}")
            print(f"   File: {test['file_path']}")
            print(f"   Execution Time: {test['execution_time']:.1f}s")
            print(f"   Nodes: {test.get('nodes_count', 0)}")
            print(f"   Edges: {test.get('edges_count', 0)}")
            print(f"   Quality Score: {test.get('quality_score', 0):.3f}")
            
            # Node type distribution
            node_types = test.get('node_types', {})
            if node_types:
                print(f"   Node Types: {dict(node_types)}")
            
            # Edge type distribution
            edge_types = test.get('edge_types', {})
            if edge_types:
                print(f"   Edge Types: {dict(edge_types)}")
            
            # Sample nodes
            if test.get('hypergraph_data'):
                nodes = test['hypergraph_data'].get('hypernodes', [])
                print(f"   Sample Entities:")
                for node in nodes[:5]:  # Show first 5 nodes
                    content = node.get('content', 'Unknown')
                    node_type = node.get('node_type', 'unknown')
                    confidence = node.get('confidence', 0)
                    print(f"     • {content} ({node_type}, conf: {confidence:.2f})")
        
        # Comparison insights
        print(f"\n💡 Comparison Insights:")
        print("-" * 40)
        
        if len(successful_tests) >= 2:
            test1, test2 = successful_tests[0], successful_tests[1]
            
            print(f"Content Type Differences:")
            print(f"   {test1['customer_name']}: {test1.get('nodes_count', 0)} nodes, {test1.get('edges_count', 0)} edges")
            print(f"   {test2['customer_name']}: {test2.get('nodes_count', 0)} nodes, {test2.get('edges_count', 0)} edges")
            
            # Quality comparison
            q1 = test1.get('quality_score', 0)
            q2 = test2.get('quality_score', 0)
            print(f"Quality Scores:")
            print(f"   {test1['customer_name']}: {q1:.3f}")
            print(f"   {test2['customer_name']}: {q2:.3f}")
            
            if q1 > q2:
                print(f"   → {test1['customer_name']}'s content produced higher quality graph")
            elif q2 > q1:
                print(f"   → {test2['customer_name']}'s content produced higher quality graph")
            else:
                print(f"   → Both contents produced similar quality graphs")
        
        print("\n" + "=" * 80)

def main():
    try:
        # Initialize tester
        tester = AdditionalFilesTester(
            profile='development',
            region='us-west-1',
            environment='dev'
        )
        
        # Run additional files test
        results = tester.run_additional_files_test()
        
        # Print comparison report
        tester.print_comparison_report()
        
        # Exit with appropriate code
        successful_tests = [t for t in results if t['status'] == 'SUCCESS']
        if len(successful_tests) >= len(results) * 0.8:  # 80% success rate
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