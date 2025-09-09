#!/usr/bin/env python3
"""
Verify Fresh Test Results - Extract and compare hypergraph data from recent executions
"""

import boto3
import json
from datetime import datetime

def get_hypergraph_data(execution_id, profile='development', region='us-west-1'):
    """Extract hypergraph data from DynamoDB for a specific execution"""
    session = boto3.Session(profile_name=profile, region_name=region)
    dynamodb = session.resource('dynamodb')
    table = dynamodb.Table('agent-performance-metrics')
    
    try:
        response = table.get_item(
            Key={
                'execution_id': execution_id,
                'agent_type': 'customer_processing'
            }
        )
        
        if 'Item' not in response:
            return None
            
        item = response['Item']
        
        # Extract customer info
        customer_name = item.get('customer_name', 'Unknown')
        file_path = item.get('file_path', 'Unknown')
        
        # Extract hypergraph data
        hypergraph_raw = item.get('hypergraph_data', '{}')
        if isinstance(hypergraph_raw, str):
            hypergraph_data = json.loads(hypergraph_raw)
        else:
            hypergraph_data = hypergraph_raw
            
        # Extract needs analysis
        needs_raw = item.get('needs_analysis', '{}')
        if isinstance(needs_raw, str):
            needs_data = json.loads(needs_raw)
            if 'body' in needs_data:
                needs_body = json.loads(needs_data['body'])
                needs_result = needs_body.get('result', {})
            else:
                needs_result = needs_data
        else:
            needs_result = needs_raw
            
        return {
            'execution_id': execution_id,
            'customer_name': customer_name,
            'file_path': file_path,
            'hypergraph': hypergraph_data,
            'needs_analysis': needs_result,
            'processing_status': item.get('processing_status', 'unknown')
        }
        
    except Exception as e:
        print(f"Error retrieving data for {execution_id}: {str(e)}")
        return None

def analyze_hypergraph(data):
    """Analyze hypergraph structure"""
    if not data or 'hypergraph' not in data:
        return "No hypergraph data found"
        
    hg = data['hypergraph']
    nodes = hg.get('nodes', [])
    edges = hg.get('edges', [])
    
    # Count node types
    node_types = {}
    for node in nodes:
        node_type = node.get('type', 'unknown')
        node_types[node_type] = node_types.get(node_type, 0) + 1
    
    # Count edge types  
    edge_types = {}
    for edge in edges:
        edge_type = edge.get('type', 'unknown')
        edge_types[edge_type] = edge_types.get(edge_type, 0) + 1
        
    return {
        'total_nodes': len(nodes),
        'total_edges': len(edges),
        'node_types': node_types,
        'edge_types': edge_types,
        'nodes': nodes[:5],  # First 5 nodes for preview
        'edges': edges[:5]   # First 5 edges for preview
    }

def analyze_needs(data):
    """Analyze needs analysis results"""
    if not data or 'needs_analysis' not in data:
        return "No needs analysis found"
        
    needs = data['needs_analysis']
    
    return {
        'needs_scores': needs.get('needs_scores', {}),
        'dominant_needs': needs.get('dominant_needs', []),
        'behavioral_patterns': needs.get('behavioral_patterns', []),
        'personality_traits': needs.get('personality_traits', []),
        'life_themes': needs.get('life_themes', []),
        'confidence_score': needs.get('confidence_score', 0)
    }

def main():
    print("🔍 FRESH TEST RESULTS VERIFICATION")
    print("=" * 60)
    
    # Recent execution IDs from our fresh tests
    executions = [
        "test-00_tim_wolff-1757370208-0c3c9e9d",
        "test-01_jon_fortt-1757370279-4e5381bc"
    ]
    
    for execution_id in executions:
        print(f"\n📊 ANALYZING: {execution_id}")
        print("-" * 60)
        
        # Get data
        data = get_hypergraph_data(execution_id)
        if not data:
            print(f"❌ No data found for {execution_id}")
            continue
            
        print(f"👤 Customer: {data['customer_name']}")
        print(f"📁 File: {data['file_path']}")
        print(f"✅ Status: {data['processing_status']}")
        
        # Analyze hypergraph
        print(f"\n🕸️ HYPERGRAPH ANALYSIS:")
        hg_analysis = analyze_hypergraph(data)
        if isinstance(hg_analysis, dict):
            print(f"   Total Nodes: {hg_analysis['total_nodes']}")
            print(f"   Total Edges: {hg_analysis['total_edges']}")
            print(f"   Node Types: {hg_analysis['node_types']}")
            print(f"   Edge Types: {hg_analysis['edge_types']}")
            
            print(f"\n   Sample Nodes:")
            for i, node in enumerate(hg_analysis['nodes'][:3], 1):
                print(f"     {i}. {node.get('label', 'Unknown')} ({node.get('type', 'unknown')})")
                
            print(f"\n   Sample Edges:")
            for i, edge in enumerate(hg_analysis['edges'][:3], 1):
                print(f"     {i}. {edge.get('source', '?')} → {edge.get('target', '?')} ({edge.get('type', 'unknown')})")
        else:
            print(f"   {hg_analysis}")
        
        # Analyze needs
        print(f"\n🧠 NEEDS ANALYSIS:")
        needs_analysis = analyze_needs(data)
        if isinstance(needs_analysis, dict):
            print(f"   Needs Scores: {needs_analysis['needs_scores']}")
            print(f"   Dominant Needs: {needs_analysis['dominant_needs']}")
            print(f"   Behavioral Patterns: {needs_analysis['behavioral_patterns']}")
            print(f"   Personality Traits: {needs_analysis['personality_traits']}")
            print(f"   Life Themes: {needs_analysis['life_themes']}")
            print(f"   Confidence: {needs_analysis['confidence_score']}")
        else:
            print(f"   {needs_analysis}")
            
        print("\n" + "=" * 60)

if __name__ == "__main__":
    main()