#!/usr/bin/env python3
"""
Test V2 hypergraph builder with actual AWS data format
"""

import json
import sys
sys.path.append('lambda-functions')

def test_v2_with_aws_format():
    """Test V2 hypergraph builder with the actual AWS data format"""
    
    print("🧪 Testing V2 with AWS Data Format")
    print("=" * 50)
    
    # Load the actual AWS payload
    with open('aws_hypergraph_input.json', 'r') as f:
        aws_payload = json.load(f)
    
    print("📋 AWS Payload Structure:")
    print(f"   • agent_spec: {type(aws_payload.get('agent_spec', {}))}")
    print(f"   • execution_id: {aws_payload.get('execution_id', 'N/A')}")
    
    processing_config = aws_payload['agent_spec']['processing_config']
    print(f"   • processing_config keys: {list(processing_config.keys())}")
    print()
    
    try:
        # Import and test the V2 builder
        from enhanced_hypergraph_builder_agent_v2 import EnhancedHypergraphBuilderV2
        
        builder = EnhancedHypergraphBuilderV2()
        
        # Test with the actual AWS format
        print("🚀 Testing V2 with AWS format...")
        result = builder.build_enhanced_hypergraph(aws_payload)
        
        print("✅ V2 processing completed!")
        print()
        
        # Analyze results
        print("📊 V2 Results with AWS Format:")
        print("-" * 40)
        print(f"   Total Nodes: {result['total_nodes']}")
        print(f"   Total Edges: {result['total_edges']}")
        
        # Show node types
        nodes = result.get('hypernodes', [])
        node_types = {}
        for node in nodes:
            node_type = node.get('node_type', 'unknown')
            if node_type not in node_types:
                node_types[node_type] = []
            node_types[node_type].append(node.get('content', 'Unknown'))
        
        print(f"\n📋 Node Types:")
        for node_type, node_list in node_types.items():
            print(f"   • {node_type}: {len(node_list)}")
            for content in node_list[:3]:
                print(f"     - {content}")
        
        # Show edge types
        edges = result.get('hyperedges', [])
        edge_types = {}
        for edge in edges:
            edge_type = edge.get('edge_type', 'unknown')
            edge_types[edge_type] = edge_types.get(edge_type, 0) + 1
        
        print(f"\n🔗 Edge Types:")
        for edge_type, count in edge_types.items():
            print(f"   • {edge_type}: {count}")
        
        # Check processing metadata
        metadata = result.get('processing_metadata', {})
        print(f"\n🔍 Processing Metadata:")
        for key, value in metadata.items():
            print(f"   • {key}: {value}")
        
        # Assessment
        success_indicators = []
        if result['total_nodes'] > 0:
            success_indicators.append("Generated nodes")
        if result['total_edges'] > 0:
            success_indicators.append("Generated edges")
        if len(node_types) > 1:
            success_indicators.append("Multiple node types")
        if any(nt != 'unknown' for nt in node_types.keys()):
            success_indicators.append("Proper node classification")
        if metadata.get('clean_entity_extraction'):
            success_indicators.append("V2 processing confirmed")
        
        print(f"\n🎯 Success Indicators:")
        for indicator in success_indicators:
            print(f"   ✅ {indicator}")
        
        if len(success_indicators) >= 3:
            print(f"\n🎉 SUCCESS: V2 handles AWS format correctly!")
            return True
        else:
            print(f"\n⚠️  PARTIAL: V2 needs more work for AWS format")
            return False
            
    except Exception as e:
        print(f"❌ Error testing V2: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_v2_with_aws_format()
    exit(0 if success else 1)