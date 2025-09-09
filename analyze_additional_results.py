#!/usr/bin/env python3
"""
Analyze Additional Test Results - Detailed hypergraph analysis for new content
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

def analyze_content_differences(hg_data, content_description):
    """Analyze hypergraph for content-specific insights"""
    if not hg_data:
        return "No hypergraph data available"
    
    nodes = hg_data.get('hypernodes', [])
    edges = hg_data.get('hyperedges', [])
    
    analysis = {
        'content_type': content_description,
        'total_nodes': len(nodes),
        'total_edges': len(edges),
        'entities_by_type': {},
        'key_concepts': [],
        'behavioral_patterns': [],
        'personality_traits': [],
        'human_needs': [],
        'relationships': [],
        'content_themes': []
    }
    
    # Categorize nodes
    for node in nodes:
        node_type = node.get('node_type', 'unknown')
        content = node.get('content', 'Unknown')
        confidence = node.get('confidence', 0)
        
        if node_type not in analysis['entities_by_type']:
            analysis['entities_by_type'][node_type] = []
        
        analysis['entities_by_type'][node_type].append({
            'content': content,
            'confidence': confidence
        })
        
        # Categorize by semantic meaning
        if node_type == 'behavioral_pattern':
            analysis['behavioral_patterns'].append(content)
        elif node_type == 'personality_trait':
            analysis['personality_traits'].append(content)
        elif node_type == 'need':
            analysis['human_needs'].append(content)
        elif node_type == 'concept':
            analysis['key_concepts'].append(content)
    
    # Analyze relationships
    for edge in edges:
        source_id = edge.get('source_node_id', '')
        target_id = edge.get('target_node_id', '')
        edge_type = edge.get('edge_type', 'unknown')
        confidence = edge.get('confidence', 0)
        
        # Find source and target content
        source_content = "Unknown"
        target_content = "Unknown"
        for node in nodes:
            if node.get('id') == source_id:
                source_content = node.get('content', 'Unknown')
            if node.get('id') == target_id:
                target_content = node.get('content', 'Unknown')
        
        analysis['relationships'].append({
            'source': source_content,
            'target': target_content,
            'type': edge_type,
            'confidence': confidence
        })
    
    return analysis

def display_detailed_analysis(analysis, customer_name):
    """Display detailed content analysis"""
    print(f"\n🎯 DETAILED ANALYSIS: {customer_name}")
    print(f"📄 Content Type: {analysis['content_type']}")
    print("=" * 70)
    
    print(f"📊 GRAPH STRUCTURE:")
    print(f"   Total Nodes: {analysis['total_nodes']}")
    print(f"   Total Edges: {analysis['total_edges']}")
    print(f"   Graph Density: {analysis['total_edges']/(analysis['total_nodes']*(analysis['total_nodes']-1)) if analysis['total_nodes'] > 1 else 0:.3f}")
    
    print(f"\n🧠 PSYCHOLOGICAL PROFILE:")
    if analysis['behavioral_patterns']:
        print(f"   Behavioral Patterns: {', '.join(analysis['behavioral_patterns'])}")
    if analysis['personality_traits']:
        print(f"   Personality Traits: {', '.join(analysis['personality_traits'])}")
    if analysis['human_needs']:
        print(f"   Human Needs: {', '.join(analysis['human_needs'])}")
    
    print(f"\n💡 KEY CONCEPTS:")
    if analysis['key_concepts']:
        for concept in analysis['key_concepts']:
            print(f"   • {concept}")
    else:
        print("   No key concepts identified")
    
    print(f"\n🔗 RELATIONSHIPS:")
    if analysis['relationships']:
        for i, rel in enumerate(analysis['relationships'][:5], 1):  # Show first 5
            print(f"   {i}. {rel['source']} --[{rel['type']}]--> {rel['target']} (conf: {rel['confidence']:.2f})")
    else:
        print("   No relationships identified")
    
    print(f"\n📋 ENTITY BREAKDOWN:")
    for entity_type, entities in analysis['entities_by_type'].items():
        print(f"   {entity_type.upper()} ({len(entities)}):")
        for entity in entities[:3]:  # Show first 3 of each type
            print(f"     • {entity['content']} (conf: {entity['confidence']:.2f})")
        if len(entities) > 3:
            print(f"     ... and {len(entities) - 3} more")

def compare_content_types(analysis1, analysis2, customer1, customer2):
    """Compare two different content types"""
    print(f"\n🔄 CONTENT TYPE COMPARISON")
    print("=" * 70)
    
    print(f"📊 STRUCTURAL DIFFERENCES:")
    print(f"   {customer1}: {analysis1['total_nodes']} nodes, {analysis1['total_edges']} edges")
    print(f"   {customer2}: {analysis2['total_nodes']} nodes, {analysis2['total_edges']} edges")
    
    # Node density comparison
    density1 = analysis1['total_edges']/(analysis1['total_nodes']*(analysis1['total_nodes']-1)) if analysis1['total_nodes'] > 1 else 0
    density2 = analysis2['total_edges']/(analysis2['total_nodes']*(analysis2['total_nodes']-1)) if analysis2['total_nodes'] > 1 else 0
    
    print(f"   Graph Density:")
    print(f"     {customer1}: {density1:.3f}")
    print(f"     {customer2}: {density2:.3f}")
    
    if density1 > density2:
        print(f"   → {customer1}'s content shows more interconnected concepts")
    elif density2 > density1:
        print(f"   → {customer2}'s content shows more interconnected concepts")
    else:
        print(f"   → Both contents show similar connectivity patterns")
    
    print(f"\n🧠 PSYCHOLOGICAL PROFILE DIFFERENCES:")
    
    # Behavioral patterns comparison
    patterns1 = set(analysis1['behavioral_patterns'])
    patterns2 = set(analysis2['behavioral_patterns'])
    common_patterns = patterns1.intersection(patterns2)
    unique1 = patterns1 - patterns2
    unique2 = patterns2 - patterns1
    
    print(f"   Behavioral Patterns:")
    if common_patterns:
        print(f"     Common: {', '.join(common_patterns)}")
    if unique1:
        print(f"     Unique to {customer1}: {', '.join(unique1)}")
    if unique2:
        print(f"     Unique to {customer2}: {', '.join(unique2)}")
    
    # Personality traits comparison
    traits1 = set(analysis1['personality_traits'])
    traits2 = set(analysis2['personality_traits'])
    common_traits = traits1.intersection(traits2)
    unique_traits1 = traits1 - traits2
    unique_traits2 = traits2 - traits1
    
    print(f"   Personality Traits:")
    if common_traits:
        print(f"     Common: {', '.join(common_traits)}")
    if unique_traits1:
        print(f"     Unique to {customer1}: {', '.join(unique_traits1)}")
    if unique_traits2:
        print(f"     Unique to {customer2}: {', '.join(unique_traits2)}")
    
    # Needs comparison
    needs1 = set(analysis1['human_needs'])
    needs2 = set(analysis2['human_needs'])
    common_needs = needs1.intersection(needs2)
    unique_needs1 = needs1 - needs2
    unique_needs2 = needs2 - needs1
    
    print(f"   Human Needs:")
    if common_needs:
        print(f"     Common: {', '.join(common_needs)}")
    if unique_needs1:
        print(f"     Unique to {customer1}: {', '.join(unique_needs1)}")
    if unique_needs2:
        print(f"     Unique to {customer2}: {', '.join(unique_needs2)}")

def main():
    print("🔍 ADDITIONAL FILES - DETAILED HYPERGRAPH ANALYSIS")
    print("=" * 70)
    
    # Execution ARNs from the additional tests (you'll need to update these with actual ARNs)
    executions = [
        {
            'name': 'Tim Wolff',
            'content': 'Positive Environment & Mindset Content',
            'arn': 'arn:aws:states:us-west-1:765455500375:execution:agentic-framework-processing-workflow-dev:additional-test-00_tim_wolff-1757373089-b30be28f'
        },
        {
            'name': 'Jon Fortt',
            'content': 'CEO Interview - Front CEO Mathilde Collin',
            'arn': 'arn:aws:states:us-west-1:765455500375:execution:agentic-framework-processing-workflow-dev:additional-test-01_jon_fortt-1757373159-61185e56'
        }
    ]
    
    analyses = []
    
    for execution in executions:
        print(f"\n🎯 ANALYZING: {execution['name']} - {execution['content']}")
        print("-" * 70)
        
        # Extract hypergraph data
        hg_data = extract_hypergraph_from_execution_history(execution['arn'])
        
        if hg_data:
            # Analyze content
            analysis = analyze_content_differences(hg_data, execution['content'])
            analyses.append((analysis, execution['name']))
            
            # Display detailed analysis
            display_detailed_analysis(analysis, execution['name'])
        else:
            print(f"❌ No hypergraph data found for {execution['name']}")
    
    # Compare the two content types
    if len(analyses) >= 2:
        analysis1, customer1 = analyses[0]
        analysis2, customer2 = analyses[1]
        compare_content_types(analysis1, analysis2, customer1, customer2)
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()