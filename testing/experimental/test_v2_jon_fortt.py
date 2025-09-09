#!/usr/bin/env python3
"""
Test V2 Lambda Function with Jon Fortt Data
"""

import json
import boto3
import time
from botocore.exceptions import NoCredentialsError, ClientError

def test_v2_with_jon_fortt():
    """Test the V2 lambda function with Jon Fortt data"""
    
    print("🧪 Testing Enhanced Hypergraph Builder V2 - Jon Fortt Profile")
    print("=" * 70)
    
    try:
        # Initialize AWS session
        session = boto3.Session(profile_name='development')
        lambda_client = session.client('lambda', region_name='us-west-1')
        
        # Create Jon Fortt test payload (similar to AWS format)
        test_payload = {
            "agent_spec": {
                "agent_type": "hypergraph_builder",
                "processing_config": {
                    "customer_name": "Jon Fortt",
                    "customer_folder": "01_jon_fortt",
                    "file_path": "high_customers/01_jon_fortt/Jon Fortt Interview Transcript.txt",
                    "customer_context": True,
                    "needs_analysis": {
                        "statusCode": 200,
                        "body": json.dumps({
                            "execution_id": "jon-fortt-test-" + str(int(time.time())),
                            "agent_type": "needs_analysis",
                            "result": {
                                "needs_scores": {
                                    "certainty": 0.6,
                                    "variety": 0.9,
                                    "significance": 0.8,
                                    "connection": 0.7,
                                    "growth": 0.8,
                                    "contribution": 0.7
                                },
                                "dominant_needs": ["Variety", "Significance", "Growth"],
                                "behavioral_patterns": [
                                    "Innovation seeker",
                                    "Technology enthusiast", 
                                    "Media professional",
                                    "Network builder"
                                ],
                                "personality_traits": [
                                    "Curious",
                                    "Articulate",
                                    "Tech-savvy",
                                    "Professional"
                                ],
                                "life_themes": [
                                    "Technology innovation",
                                    "Media excellence",
                                    "Professional growth"
                                ],
                                "confidence_score": 0.85
                            },
                            "success": True
                        })
                    }
                }
            },
            "execution_id": "jon-fortt-v2-test-" + str(int(time.time()))
        }
        
        # Test the V2 lambda function directly
        function_name = 'agentic-hypergraph-builder-dev'
        
        print(f"🚀 Invoking V2 Lambda with Jon Fortt Profile")
        print(f"   Function: {function_name}")
        print(f"   Customer: {test_payload['agent_spec']['processing_config']['customer_name']}")
        print(f"   File: {test_payload['agent_spec']['processing_config']['file_path']}")
        print(f"   Dominant Needs: {test_payload['agent_spec']['processing_config']['needs_analysis']['body']}")
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
            print("🔍 ANALYZING JON FORTT V2 RESULTS:")
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
                        print(f"\n📊 Jon Fortt Hypergraph Results:")
                        print(f"   Total Nodes: {result.get('total_nodes', 0)}")
                        print(f"   Total Edges: {result.get('total_edges', 0)}")
                        
                        # Show node types and samples
                        nodes = result.get('nodes', [])
                        if nodes:
                            node_types = {}
                            sample_nodes = {}
                            
                            for node in nodes:
                                node_type = node.get('type', 'unknown')
                                node_text = node.get('text', 'N/A')
                                
                                node_types[node_type] = node_types.get(node_type, 0) + 1
                                
                                if node_type not in sample_nodes:
                                    sample_nodes[node_type] = []
                                if len(sample_nodes[node_type]) < 2:
                                    sample_nodes[node_type].append(node_text)
                            
                            print(f"\n   📋 Node Analysis:")
                            for node_type, count in node_types.items():
                                print(f"     - {node_type}: {count} nodes")
                                if node_type in sample_nodes:
                                    for sample in sample_nodes[node_type]:
                                        print(f"       • {sample}")
                        
                        # Show edge types
                        edges = result.get('edges', [])
                        if edges:
                            edge_types = {}
                            for edge in edges:
                                edge_type = edge.get('relationship_type', 'unknown')
                                edge_types[edge_type] = edge_types.get(edge_type, 0) + 1
                            
                            print(f"\n   🔗 Relationship Analysis:")
                            for edge_type, count in edge_types.items():
                                print(f"     - {edge_type}: {count} relationships")
                        
                        # Quality metrics
                        metrics = result.get('graph_metrics', {})
                        if metrics:
                            print(f"\n📈 Quality Metrics:")
                            print(f"   Quality Score: {metrics.get('quality_score', 'N/A')}")
                            print(f"   Completeness: {metrics.get('completeness', 'N/A')}")
                            print(f"   Coherence: {metrics.get('coherence', 'N/A')}")
                        
                        # Compare with expected Jon Fortt characteristics
                        print(f"\n🎯 Jon Fortt Profile Validation:")
                        jon_fortt_indicators = [
                            "Jon Fortt", "Technology", "Media", "Innovation", 
                            "Variety", "Significance", "Growth", "Curious", "Tech-savvy"
                        ]
                        
                        found_indicators = []
                        for node in nodes:
                            node_text = node.get('text', '')
                            for indicator in jon_fortt_indicators:
                                if indicator.lower() in node_text.lower():
                                    found_indicators.append(f"{indicator} → {node_text}")
                        
                        if found_indicators:
                            print(f"   ✅ Profile indicators found:")
                            for indicator in found_indicators[:5]:  # Show top 5
                                print(f"     • {indicator}")
                        else:
                            print(f"   ⚠️  No specific profile indicators found")
                        
                        print(f"\n✅ V2 successfully processed Jon Fortt profile!")
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
    success = test_v2_with_jon_fortt()
    if success:
        print("\n🎉 Jon Fortt V2 test completed successfully!")
    else:
        print("\n❌ Jon Fortt V2 test FAILED!")
        exit(1)