#!/usr/bin/env python3
"""
Test script for the enhanced hypergraph builder
"""

import boto3
import json
import time
from datetime import datetime

def test_enhanced_hypergraph():
    # Initialize AWS clients
    session = boto3.Session(profile_name='development', region_name='us-west-1')
    stepfunctions = session.client('stepfunctions')
    dynamodb = session.resource('dynamodb')
    
    # Configuration
    state_machine_arn = "arn:aws:states:us-west-1:765455500375:stateMachine:agentic-framework-processing-workflow-dev"
    performance_table = dynamodb.Table('agent-performance-metrics')
    
    print("🧪 Testing Enhanced Hypergraph Builder")
    print("=" * 50)
    
    # Create test execution
    execution_name = f"enhanced-hypergraph-test-{int(time.time())}"
    
    input_data = {
        "file_path": "high_customers/00_tim_wolff/Berater = Netzwerk, Know-how, Backup.txt",
        "customer_folder": "00_tim_wolff",
        "customer_name": "Tim Wolff",
        "processing_config": {
            "enable_detailed_analysis": True,
            "confidence_threshold": 0.7,
            "test_enhanced_hypergraph": True
        }
    }
    
    print(f"🚀 Starting test execution: {execution_name}")
    
    # Start execution
    response = stepfunctions.start_execution(
        stateMachineArn=state_machine_arn,
        name=execution_name,
        input=json.dumps(input_data, default=str)
    )
    
    execution_arn = response['executionArn']
    print(f"✅ Execution started: {execution_arn}")
    
    # Monitor execution
    print("⏳ Monitoring execution...")
    start_time = time.time()
    
    while time.time() - start_time < 120:  # 2 minute timeout
        execution_status = stepfunctions.describe_execution(executionArn=execution_arn)
        status = execution_status['status']
        
        if status == 'SUCCEEDED':
            print("✅ Execution completed successfully!")
            
            # Wait a moment for DynamoDB write
            time.sleep(2)
            
            # Check results
            try:
                result = performance_table.get_item(
                    Key={
                        'execution_id': execution_name,
                        'agent_type': 'customer_processing'
                    }
                )
                
                if 'Item' in result:
                    item = result['Item']
                    
                    if 'hypergraph_data' in item:
                        hypergraph_str = item['hypergraph_data']
                        hypergraph_data = json.loads(hypergraph_str)
                        
                        print("\n🔍 ENHANCED HYPERGRAPH RESULTS:")
                        print("-" * 40)
                        
                        # Parse the response
                        if 'body' in hypergraph_data:
                            body_data = json.loads(hypergraph_data['body'])
                            result_data = body_data.get('result', {})
                            
                            # Check for enhancement features
                            enhancement_features = body_data.get('enhancement_features', {})
                            
                            print(f"📊 Enhancement Features:")
                            for feature, enabled in enhancement_features.items():
                                status_icon = "✅" if enabled else "❌"
                                print(f"   {status_icon} {feature.replace('_', ' ').title()}: {enabled}")
                            
                            print(f"\n📈 Graph Statistics:")
                            print(f"   Total Nodes: {len(result_data.get('hypernodes', []))}")
                            print(f"   Total Edges: {len(result_data.get('hyperedges', []))}")
                            
                            # Check for improved entity classification
                            nodes = result_data.get('hypernodes', [])
                            entities_with_types = [n for n in nodes if n.get('node_type') != 'unknown']
                            
                            print(f"\n🎯 Entity Classification:")
                            print(f"   Entities with proper types: {len(entities_with_types)}/{len([n for n in nodes if 'entity' in n.get('node_type', '')])}")
                            
                            # Show node types
                            node_types = {}
                            for node in nodes:
                                node_type = node.get('node_type', 'unknown')
                                node_types[node_type] = node_types.get(node_type, 0) + 1
                            
                            print(f"\n📋 Node Type Distribution:")
                            for node_type, count in sorted(node_types.items()):
                                print(f"   • {node_type.replace('_', ' ').title()}: {count}")
                            
                            # Check for semantic relationships
                            edges = result_data.get('hyperedges', [])
                            semantic_edges = [e for e in edges if 'semantic' in e.get('edge_type', '').lower() or 'relates_to' in e.get('edge_type', '').lower()]
                            
                            print(f"\n🔗 Relationship Quality:")
                            print(f"   Semantic relationships: {len(semantic_edges)}")
                            print(f"   Total relationships: {len(edges)}")
                            
                            # Show edge types
                            edge_types = {}
                            for edge in edges:
                                edge_type = edge.get('edge_type', 'unknown')
                                edge_types[edge_type] = edge_types.get(edge_type, 0) + 1
                            
                            print(f"\n📋 Edge Type Distribution:")
                            for edge_type, count in sorted(edge_types.items()):
                                print(f"   • {edge_type.replace('_', ' ').title()}: {count}")
                            
                            # Check for graph insights
                            insights = result_data.get('graph_insights', {})
                            if insights:
                                print(f"\n💡 Graph Insights:")
                                print(f"   Domain Focus: {insights.get('domain_focus', 'unknown')}")
                                print(f"   Graph Complexity: {insights.get('graph_complexity', 'unknown')}")
                                print(f"   Relationship Diversity: {insights.get('relationship_diversity', 0)}")
                            
                            # Overall assessment
                            print(f"\n🎯 ENHANCEMENT ASSESSMENT:")
                            
                            improvements = []
                            if enhancement_features.get('llm_entity_classification'):
                                improvements.append("✅ LLM-powered entity classification")
                            if enhancement_features.get('semantic_relationships'):
                                improvements.append("✅ Semantic relationship detection")
                            if enhancement_features.get('domain_specific_analysis'):
                                improvements.append("✅ Domain-specific analysis")
                            if enhancement_features.get('psychological_need_mapping'):
                                improvements.append("✅ Psychological need mapping")
                            
                            if len(semantic_edges) > 0:
                                improvements.append("✅ Semantic relationships detected")
                            
                            if len(entities_with_types) > 0:
                                improvements.append("✅ Proper entity classification")
                            
                            for improvement in improvements:
                                print(f"   {improvement}")
                            
                            if len(improvements) >= 4:
                                print(f"\n🎉 EXCELLENT: Enhanced hypergraph builder is working!")
                            elif len(improvements) >= 2:
                                print(f"\n✅ GOOD: Partial enhancements working")
                            else:
                                print(f"\n⚠️ NEEDS WORK: Enhancements not fully working")
                        
                        else:
                            print("❌ Could not parse hypergraph response structure")
                    else:
                        print("❌ No hypergraph data found in results")
                else:
                    print("❌ No results found in DynamoDB")
                    
            except Exception as e:
                print(f"❌ Error checking results: {str(e)}")
            
            return True
            
        elif status == 'FAILED':
            print("❌ Execution failed!")
            print(f"Error: {execution_status.get('error', 'Unknown error')}")
            return False
            
        elif status in ['TIMED_OUT', 'ABORTED']:
            print(f"❌ Execution {status.lower()}")
            return False
        
        # Still running
        elapsed = time.time() - start_time
        print(f"⏳ Still running... ({elapsed:.1f}s)")
        time.sleep(5)
    
    print("❌ Test timed out")
    return False

if __name__ == "__main__":
    success = test_enhanced_hypergraph()
    exit(0 if success else 1)