#!/usr/bin/env python3
"""
Test V2 Lambda Function Directly
"""

import json
import boto3
import time
from botocore.exceptions import NoCredentialsError, ClientError

def test_v2_lambda_direct():
    """Test the V2 lambda function directly"""
    
    print("🧪 Testing Enhanced Hypergraph Builder V2 - Direct Lambda")
    print("=" * 70)
    
    try:
        # Initialize AWS session with development profile
        session = boto3.Session(profile_name='development')
        lambda_client = session.client('lambda', region_name='us-west-1')
        
        # Load test data
        with open('aws_hypergraph_input.json', 'r') as f:
            test_payload = json.load(f)
        
        # Test the V2 lambda function directly
        function_name = 'agentic-hypergraph-builder-dev'
        
        print(f"🚀 Invoking Lambda Function: {function_name}")
        print(f"   Customer: {test_payload['agent_spec']['processing_config']['customer_name']}")
        print(f"   File: {test_payload['agent_spec']['processing_config']['file_path']}")
        print()
        
        # Invoke the lambda
        start_time = time.time()
        
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='RequestResponse',
            Payload=json.dumps(test_payload)
        )
        
        elapsed_time = time.time() - start_time
        
        # Parse response
        status_code = response['StatusCode']
        payload = json.loads(response['Payload'].read())
        
        print(f"⏱️  Execution Time: {elapsed_time:.2f}s")
        print(f"📊 Status Code: {status_code}")
        print()
        
        if status_code == 200:
            print("🔍 ANALYZING V2 LAMBDA RESPONSE:")
            print("-" * 50)
            
            # Check response structure
            if 'body' in payload:
                try:
                    body_data = json.loads(payload['body'])
                    
                    print(f"✅ Response Structure:")
                    print(f"   Status Code: {payload.get('statusCode', 'N/A')}")
                    print(f"   Agent Type: {body_data.get('agent_type', 'N/A')}")
                    print(f"   Success: {body_data.get('success', 'N/A')}")
                    print(f"   Execution ID: {body_data.get('execution_id', 'N/A')}")
                    
                    # Analyze hypergraph result
                    result = body_data.get('result', {})
                    if result:
                        print(f"\n📊 Hypergraph Results:")
                        print(f"   Total Nodes: {result.get('total_nodes', 0)}")
                        print(f"   Total Edges: {result.get('total_edges', 0)}")
                        
                        # Show node types
                        nodes = result.get('nodes', [])
                        if nodes:
                            node_types = {}
                            for node in nodes:
                                node_type = node.get('type', 'unknown')
                                node_types[node_type] = node_types.get(node_type, 0) + 1
                            
                            print(f"   Node Types:")
                            for node_type, count in node_types.items():
                                print(f"     - {node_type}: {count}")
                        
                        # Show edge types
                        edges = result.get('edges', [])
                        if edges:
                            edge_types = {}
                            for edge in edges:
                                edge_type = edge.get('relationship_type', 'unknown')
                                edge_types[edge_type] = edge_types.get(edge_type, 0) + 1
                            
                            print(f"   Edge Types:")
                            for edge_type, count in edge_types.items():
                                print(f"     - {edge_type}: {count}")
                        
                        # Quality metrics
                        metrics = result.get('graph_metrics', {})
                        if metrics:
                            print(f"\n📈 Quality Metrics:")
                            print(f"   Quality Score: {metrics.get('quality_score', 'N/A')}")
                            print(f"   Completeness: {metrics.get('completeness', 'N/A')}")
                            print(f"   Coherence: {metrics.get('coherence', 'N/A')}")
                        
                        print(f"\n✅ V2 Lambda function working correctly!")
                        return True
                    else:
                        print(f"❌ No result data in response")
                        return False
                        
                except json.JSONDecodeError as e:
                    print(f"❌ Failed to parse response body: {str(e)}")
                    print(f"Raw body: {payload.get('body', 'No body')}")
                    return False
            else:
                print(f"❌ No body in response")
                print(f"Response keys: {list(payload.keys())}")
                return False
        else:
            print(f"❌ Lambda invocation failed with status {status_code}")
            if 'errorMessage' in payload:
                print(f"Error: {payload['errorMessage']}")
            return False
            
    except NoCredentialsError:
        print("❌ AWS credentials not found. Please configure your credentials.")
        return False
    except ClientError as e:
        print(f"❌ AWS Client Error: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_v2_lambda_direct()
    if success:
        print("\n🎉 V2 Direct Lambda test completed successfully!")
    else:
        print("\n❌ V2 Direct Lambda test FAILED!")
        exit(1)