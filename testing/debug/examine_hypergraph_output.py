#!/usr/bin/env python3
"""
Script to examine current hypergraph builder output
"""

import boto3
import json
from pprint import pprint

def examine_hypergraph_output():
    # Initialize DynamoDB
    session = boto3.Session(profile_name='development', region_name='us-west-1')
    dynamodb = session.resource('dynamodb')
    table = dynamodb.Table('agent-performance-metrics')
    
    # Get the test execution result
    execution_id = "test-00_tim_wolff-1756434139-70a045c3"
    
    try:
        response = table.get_item(
            Key={
                'execution_id': execution_id,
                'agent_type': 'customer_processing'
            }
        )
        
        if 'Item' in response:
            item = response['Item']
            
            # Extract hypergraph data
            if 'hypergraph_data' in item:
                hypergraph_str = item['hypergraph_data']
                
                # Parse the JSON string
                hypergraph_data = json.loads(hypergraph_str)
                
                print("🔍 CURRENT HYPERGRAPH BUILDER OUTPUT ANALYSIS")
                print("=" * 60)
                
                # Parse the nested structure
                if 'body' in hypergraph_data:
                    body_data = json.loads(hypergraph_data['body'])
                    result = body_data.get('result', {})
                    
                    print(f"📊 HYPERGRAPH STATISTICS:")
                    print(f"   Total Nodes: {len(result.get('hypernodes', []))}")
                    print(f"   Total Edges: {len(result.get('hyperedges', []))}")
                    
                    print(f"\n🔗 NODES ANALYSIS:")
                    nodes = result.get('hypernodes', [])
                    node_types = {}
                    
                    for node in nodes:
                        node_type = node.get('type', 'unknown')
                        if node_type not in node_types:
                            node_types[node_type] = []
                        node_types[node_type].append(node)
                    
                    for node_type, type_nodes in node_types.items():
                        print(f"\n   {node_type.upper()} NODES ({len(type_nodes)}):")
                        for node in type_nodes[:5]:  # Show first 5
                            label = node.get('label', 'No label')
                            properties = node.get('properties', {})
                            print(f"     • {label} - {properties}")
                    
                    print(f"\n🔗 EDGES ANALYSIS:")
                    edges = result.get('hyperedges', [])
                    edge_types = {}
                    
                    for edge in edges:
                        edge_type = edge.get('type', 'unknown')
                        if edge_type not in edge_types:
                            edge_types[edge_type] = []
                        edge_types[edge_type].append(edge)
                    
                    for edge_type, type_edges in edge_types.items():
                        print(f"\n   {edge_type.upper()} EDGES ({len(type_edges)}):")
                        for edge in type_edges[:3]:  # Show first 3
                            source = edge.get('source', 'unknown')
                            target = edge.get('target', 'unknown')
                            properties = edge.get('properties', {})
                            print(f"     • {source} → {target} - {properties}")
                    
                    print(f"\n📋 DETAILED NODE BREAKDOWN:")
                    print("-" * 40)
                    for i, node in enumerate(nodes[:10]):  # Show first 10 nodes
                        print(f"{i+1}. ID: {node.get('id', 'N/A')}")
                        print(f"   Type: {node.get('type', 'N/A')}")
                        print(f"   Label: {node.get('label', 'N/A')}")
                        print(f"   Properties: {node.get('properties', {})}")
                        print()
                    
                    print(f"\n📋 DETAILED EDGE BREAKDOWN:")
                    print("-" * 40)
                    for i, edge in enumerate(edges[:10]):  # Show first 10 edges
                        print(f"{i+1}. ID: {edge.get('id', 'N/A')}")
                        print(f"   Type: {edge.get('type', 'N/A')}")
                        print(f"   Source: {edge.get('source', 'N/A')}")
                        print(f"   Target: {edge.get('target', 'N/A')}")
                        print(f"   Properties: {edge.get('properties', {})}")
                        print()
                    
                    print(f"\n🎯 ISSUES IDENTIFIED:")
                    print("-" * 40)
                    
                    issues = []
                    
                    # Check for entity classification issues
                    entity_nodes = [n for n in nodes if n.get('type') == 'entity']
                    for entity in entity_nodes:
                        if entity.get('properties', {}).get('entity_type') == 'unknown':
                            issues.append(f"❌ Entity '{entity.get('label')}' has unknown type")
                    
                    # Check for edge quality
                    if len(edges) < len(nodes) * 0.5:
                        issues.append(f"❌ Too few edges ({len(edges)}) for {len(nodes)} nodes")
                    
                    # Check for semantic relationships
                    semantic_edges = [e for e in edges if 'semantic' in e.get('type', '').lower()]
                    if len(semantic_edges) == 0:
                        issues.append("❌ No semantic relationships detected")
                    
                    # Check for entity relationships
                    entity_edges = [e for e in edges if any(n.get('type') == 'entity' for n in nodes if n.get('id') in [e.get('source'), e.get('target')])]
                    if len(entity_edges) < len(entity_nodes):
                        issues.append("❌ Entities are not well connected")
                    
                    for issue in issues:
                        print(f"   {issue}")
                    
                    if not issues:
                        print("   ✅ No major issues detected")
                    
                    print(f"\n💡 IMPROVEMENT RECOMMENDATIONS:")
                    print("-" * 40)
                    print("   1. 🤖 Use LLM for better entity classification")
                    print("   2. 🔗 Improve semantic relationship detection")
                    print("   3. 📊 Add domain-specific entity types (PERSON, ORGANIZATION, CONCEPT)")
                    print("   4. 🧠 Connect entities to psychological needs more intelligently")
                    print("   5. 📈 Add confidence scoring for relationships")
                    print("   6. 🎯 Create more meaningful edge types (INFLUENCES, RELATES_TO, PART_OF)")
                
                else:
                    print("❌ Could not parse hypergraph data structure")
                    print("Raw data:", hypergraph_data)
            else:
                print("❌ No hypergraph data found in the result")
        else:
            print(f"❌ No data found for execution ID: {execution_id}")
            
    except Exception as e:
        print(f"❌ Error examining hypergraph output: {str(e)}")

if __name__ == "__main__":
    examine_hypergraph_output()