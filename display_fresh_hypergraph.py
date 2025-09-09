#!/usr/bin/env python3
"""
Display Fresh Hypergraph Results - Extract and properly display V2 hypergraph data
"""

import boto3
import json
from datetime import datetime

def extract_hypergraph_from_execution_history(execution_arn, profile='development', region='us-west-1'):
    """Extract hypergraph data from Step Functions execution history"""
    session = boto3.Session(profile_name=profile, region_name=region)
    stepfunctions = session.client('stepfunctions')
    
    try:
        response = stepfunctions.get_execution_history(executionArn=execution_arn)
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
        print(f"Error extracting from execution history: {str(e)}")
        return None

def display_hypergraph_analysis(hg_data, customer_name):
    """Display comprehensive hypergraph analysis"""
    if not hg_data:
        print(f"❌ No hypergraph data found for {customer_name}")
        return
        
    print(f"\n🎯 HYPERGRAPH ANALYSIS: {customer_name}")
    print("=" * 60)
    
    # Basic metrics
    nodes = hg_data.get('hypernodes', [])
    edges = hg_data.get('hyperedges', [])
    metrics = hg_data.get('graph_metrics', {})
    
    print(f"📊 GRAPH METRICS:")
    print(f"   Total Nodes: {len(nodes)}")
    print(f"   Total Edges: {len(edges)}")
    print(f"   Average Confidence: {metrics.get('average_confidence', 0):.3f}")
    print(f"   Graph Density: {metrics.get('graph_density', 0):.3f}")
    print(f"   Quality Score: {hg_data.get('graph_insights', {}).get('quality_score', 0):.3f}")
    
    # Node type distribution
    node_types = metrics.get('node_type_distribution', {})
    print(f"\n🔗 NODE DISTRIBUTION:")
    for node_type, count in node_types.items():
        print(f"   {node_type}: {count}")
    
    # Edge type distribution
    edge_types = metrics.get('edge_type_distribution', {})
    print(f"\n🔗 EDGE DISTRIBUTION:")
    for edge_type, count in edge_types.items():
        print(f"   {edge_type}: {count}")
    
    # Sample nodes by type
    print(f"\n📋 SAMPLE NODES:")
    node_samples = {}
    for node in nodes:
        node_type = node.get('node_type', 'unknown')
        if node_type not in node_samples:
            node_samples[node_type] = []
        if len(node_samples[node_type]) < 3:  # Show max 3 per type
            node_samples[node_type].append(node)
    
    for node_type, sample_nodes in node_samples.items():
        print(f"\n   {node_type.upper()} NODES:")
        for node in sample_nodes:
            confidence = node.get('confidence', 0)
            content = node.get('content', 'Unknown')
            print(f"     • {content} (confidence: {confidence:.2f})")
    
    # Sample edges
    print(f"\n🔗 SAMPLE RELATIONSHIPS:")
    for i, edge in enumerate(edges[:5], 1):  # Show first 5 edges
        source_id = edge.get('source_node_id', 'unknown')
        target_id = edge.get('target_node_id', 'unknown')
        edge_type = edge.get('edge_type', 'unknown')
        confidence = edge.get('confidence', 0)
        
        # Find node contents
        source_content = "Unknown"
        target_content = "Unknown"
        for node in nodes:
            if node.get('id') == source_id:
                source_content = node.get('content', 'Unknown')
            if node.get('id') == target_id:
                target_content = node.get('content', 'Unknown')
        
        print(f"   {i}. {source_content} --[{edge_type}]--> {target_content} (conf: {confidence:.2f})")
    
    # Graph insights
    insights = hg_data.get('graph_insights', {})
    print(f"\n💡 GRAPH INSIGHTS:")
    print(f"   Central Entities: {insights.get('central_entities', [])}")
    print(f"   Most Common Relationship: {insights.get('most_common_relationship', 'unknown')}")
    print(f"   Entity Diversity: {insights.get('entity_diversity', 0)}")
    
    # Processing metadata
    metadata = hg_data.get('processing_metadata', {})
    print(f"\n🔧 PROCESSING FEATURES:")
    for feature, enabled in metadata.items():
        status = "✅" if enabled else "❌"
        print(f"   {status} {feature.replace('_', ' ').title()}")

def main():
    print("🔍 FRESH HYPERGRAPH RESULTS ANALYSIS")
    print("=" * 60)
    
    # Recent execution ARNs from our fresh tests
    executions = [
        {
            'name': 'Tim Wolff',
            'arn': 'arn:aws:states:us-west-1:765455500375:execution:agentic-framework-processing-workflow-dev:test-00_tim_wolff-1757370208-0c3c9e9d'
        },
        {
            'name': 'Jon Fortt', 
            'arn': 'arn:aws:states:us-west-1:765455500375:execution:agentic-framework-processing-workflow-dev:test-01_jon_fortt-1757370279-4e5381bc'
        }
    ]
    
    for execution in executions:
        print(f"\n🎯 ANALYZING: {execution['name']}")
        print("-" * 60)
        
        # Extract hypergraph data from execution history
        hg_data = extract_hypergraph_from_execution_history(execution['arn'])
        
        # Display analysis
        display_hypergraph_analysis(hg_data, execution['name'])
        
        print("\n" + "=" * 60)

if __name__ == "__main__":
    main()