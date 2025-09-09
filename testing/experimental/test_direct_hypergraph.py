#!/usr/bin/env python3
"""
Direct test of the enhanced hypergraph builder Lambda function
"""

import boto3
import json

def test_direct_hypergraph():
    # Initialize Lambda client
    session = boto3.Session(profile_name='development', region_name='us-west-1')
    lambda_client = session.client('lambda')
    
    print("🧪 Testing Enhanced Hypergraph Builder Directly")
    print("=" * 50)
    
    # Create test payload
    test_payload = {
        "agent_spec": {
            "agent_type": "enhanced_hypergraph_builder",
            "processing_config": {
                "file_path": "high_customers/00_tim_wolff/Berater = Netzwerk, Know-how, Backup.txt",
                "customer_folder": "00_tim_wolff",
                "customer_name": "Tim Wolff",
                "content_analysis": {
                    "content_type": "financial_advice"
                }
            }
        },
        "execution_id": "direct-test-enhanced-hypergraph"
    }
    
    print("🚀 Invoking enhanced hypergraph builder directly...")
    
    try:
        # Invoke the Lambda function directly
        response = lambda_client.invoke(
            FunctionName='agentic-hypergraph-builder-dev',
            InvocationType='RequestResponse',
            Payload=json.dumps(test_payload)
        )
        
        # Parse response
        response_payload = json.loads(response['Payload'].read())
        
        print(f"📊 Response Status Code: {response['StatusCode']}")
        print(f"📊 Function Status Code: {response_payload.get('statusCode', 'N/A')}")
        
        if response_payload.get('statusCode') == 200:
            print("✅ Function executed successfully!")
            
            # Parse the body
            body = json.loads(response_payload['body'])
            result = body.get('result', {})
            
            print(f"\n🔍 ENHANCED HYPERGRAPH RESULTS:")
            print("-" * 40)
            
            # Check enhancement features
            enhancement_features = body.get('enhancement_features', {})
            if enhancement_features:
                print(f"📊 Enhancement Features:")
                for feature, enabled in enhancement_features.items():
                    status_icon = "✅" if enabled else "❌"
                    print(f"   {status_icon} {feature.replace('_', ' ').title()}: {enabled}")
            
            # Graph statistics
            nodes = result.get('hypernodes', [])
            edges = result.get('hyperedges', [])
            
            print(f"\n📈 Graph Statistics:")
            print(f"   Total Nodes: {len(nodes)}")
            print(f"   Total Edges: {len(edges)}")
            
            # Node analysis
            if nodes:
                print(f"\n📋 Sample Nodes:")
                for i, node in enumerate(nodes[:5]):
                    print(f"   {i+1}. {node.get('content', 'N/A')} ({node.get('node_type', 'unknown')})")
            
            # Edge analysis
            if edges:
                print(f"\n🔗 Sample Edges:")
                for i, edge in enumerate(edges[:5]):
                    print(f"   {i+1}. {edge.get('source_id', 'N/A')} → {edge.get('target_id', 'N/A')} ({edge.get('edge_type', 'unknown')})")
            
            # Graph insights
            insights = result.get('graph_insights', {})
            if insights:
                print(f"\n💡 Graph Insights:")
                print(f"   Domain Focus: {insights.get('domain_focus', 'unknown')}")
                print(f"   Graph Complexity: {insights.get('graph_complexity', 'unknown')}")
            
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
            
            # Check for proper node types
            proper_types = [n for n in nodes if n.get('node_type') not in ['unknown', 'entity']]
            if len(proper_types) > 0:
                improvements.append(f"✅ Proper node classification ({len(proper_types)} nodes)")
            
            # Check for semantic edges
            semantic_edges = [e for e in edges if e.get('edge_type') in ['relates_to', 'semantic_similarity', 'influences']]
            if len(semantic_edges) > 0:
                improvements.append(f"✅ Semantic relationships ({len(semantic_edges)} edges)")
            
            for improvement in improvements:
                print(f"   {improvement}")
            
            if len(improvements) >= 4:
                print(f"\n🎉 EXCELLENT: Enhanced hypergraph builder is working!")
                return True
            elif len(improvements) >= 2:
                print(f"\n✅ GOOD: Partial enhancements working")
                return True
            else:
                print(f"\n⚠️ NEEDS WORK: Enhancements not fully working")
                return False
        
        else:
            print("❌ Function execution failed!")
            print(f"Error: {response_payload.get('body', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ Error invoking function: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_direct_hypergraph()
    exit(0 if success else 1)