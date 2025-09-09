#!/usr/bin/env python3
"""
Test script to compare Enhanced Hypergraph Builder V1 vs V2
Focus on cleaner entity and relationship extraction
"""

import boto3
import json
import time
from datetime import datetime

def test_hypergraph_v2():
    """Test the enhanced hypergraph builder V2 with cleaner extraction"""
    
    print("🧪 Testing Enhanced Hypergraph Builder V2 - Cleaner Extraction")
    print("=" * 70)
    
    # Initialize AWS clients
    lambda_client = boto3.client('lambda', region_name='us-west-1')
    
    # Test data - simulating the data structure from the framework
    test_event = {
        'execution_id': f'test-v2-{int(time.time())}',
        'agent_spec': {
            'processing_config': {
                'customer_name': 'Tim Wolff',
                'file_path': 'high_customers/00_tim_wolff/Berater = Netzwerk, Know-how, Backup.txt',
                'raw_text': """
                Tim Wolff ist ein erfahrener Finanzberater mit über 15 Jahren Erfahrung. 
                Er spezialisiert sich auf Versicherungen, Investmentplanung und Risikomanagement.
                Als strategischer Planner hilft er Kunden bei der langfristigen Finanzplanung.
                Seine analytische Herangehensweise und sein umfassendes Netzwerk machen ihn zu einem 
                vertrauenswürdigen Berater. Tim ist bekannt für seine vorsichtige aber effektive 
                Beratung in Versicherungsfragen und Investmentstrategien.
                """,
                'key_insights': {
                    'skills_and_competencies': [
                        'Financial advisory expertise',
                        'Insurance specialization', 
                        'Investment planning',
                        'Risk management',
                        'Strategic planning'
                    ],
                    'main_themes': [
                        'Financial advisory',
                        'Insurance consulting',
                        'Investment strategies'
                    ],
                    'goals_and_aspirations': [
                        'Long-term client relationships',
                        'Comprehensive financial planning',
                        'Risk mitigation strategies'
                    ]
                },
                'entities': [
                    {
                        'text': 'Tim Wolff',
                        'type': 'PERSON',
                        'confidence': 0.95,
                        'context': 'Primary financial advisor'
                    },
                    {
                        'text': 'Financial Planning',
                        'type': 'BUSINESS_CONCEPT',
                        'confidence': 0.9,
                        'context': 'Core service offering'
                    }
                ],
                'needs_analysis': {
                    'needs_scores': {
                        'certainty': 0.8,
                        'growth': 0.6,
                        'significance': 0.5,
                        'connection': 0.4,
                        'variety': 0.3,
                        'contribution': 0.7
                    },
                    'dominant_needs': [
                        ('certainty', 0.8),
                        ('contribution', 0.7),
                        ('growth', 0.6)
                    ],
                    'behavioral_patterns': [
                        'Strategic planner',
                        'Risk-averse advisor',
                        'Client-focused consultant',
                        'Analytical decision maker'
                    ],
                    'personality_traits': [
                        'Analytical',
                        'Cautious',
                        'Trustworthy',
                        'Detail-oriented',
                        'Client-focused'
                    ],
                    'life_themes': [
                        'Professional expertise development',
                        'Client relationship building',
                        'Financial security focus'
                    ]
                }
            }
        }
    }
    
    print("🚀 Testing V2 Enhanced Hypergraph Builder...")
    
    try:
        # Test the V2 version directly (import and run locally)
        import sys
        sys.path.append('lambda-functions')
        
        from enhanced_hypergraph_builder_agent_v2 import EnhancedHypergraphBuilderV2
        
        builder_v2 = EnhancedHypergraphBuilderV2()
        
        # Extract analysis data from test event
        analysis_data = test_event['agent_spec']['processing_config']
        
        # Build hypergraph with V2
        result_v2 = builder_v2.build_enhanced_hypergraph(analysis_data)
        
        print("✅ V2 Hypergraph Builder completed successfully!")
        print()
        
        # Analyze V2 results
        print("📊 V2 ENHANCED HYPERGRAPH RESULTS:")
        print("-" * 50)
        
        print(f"📈 Graph Statistics:")
        print(f"   Total Nodes: {result_v2['total_nodes']}")
        print(f"   Total Edges: {result_v2['total_edges']}")
        print()
        
        # Analyze node types
        node_types = {}
        for node in result_v2['hypernodes']:
            node_type = node['node_type']
            if node_type not in node_types:
                node_types[node_type] = []
            node_types[node_type].append(node['content'])
        
        print(f"📋 Node Type Distribution:")
        for node_type, nodes in node_types.items():
            print(f"   • {node_type.title()}: {len(nodes)}")
            for node in nodes[:3]:  # Show first 3
                print(f"     - {node}")
        print()
        
        # Analyze edge types
        edge_types = {}
        for edge in result_v2['hyperedges']:
            edge_type = edge['edge_type']
            if edge_type not in edge_types:
                edge_types[edge_type] = []
            edge_types[edge_type].append({
                'source': edge['source_node_id'],
                'target': edge['target_node_id'],
                'confidence': edge['confidence']
            })
        
        print(f"🔗 Edge Type Distribution:")
        for edge_type, edges in edge_types.items():
            print(f"   • {edge_type.title()}: {len(edges)}")
            avg_confidence = sum(e['confidence'] for e in edges) / len(edges)
            print(f"     Average Confidence: {avg_confidence:.2f}")
        print()
        
        # Show graph insights
        insights = result_v2.get('graph_insights', {})
        print(f"💡 Graph Insights:")
        print(f"   Central Entities: {insights.get('central_entities', [])}")
        print(f"   Graph Density: {insights.get('graph_density', 0):.3f}")
        print(f"   Entity Diversity: {insights.get('entity_diversity', 0)}")
        print(f"   Quality Score: {insights.get('quality_score', 0):.2f}")
        print()
        
        # Show sample relationships with evidence
        print(f"🔍 Sample Relationships with Evidence:")
        for i, edge in enumerate(result_v2['hyperedges'][:5]):
            source_node = next((n for n in result_v2['hypernodes'] if n['id'] == edge['source_node_id']), {})
            target_node = next((n for n in result_v2['hypernodes'] if n['id'] == edge['target_node_id']), {})
            
            print(f"   {i+1}. {source_node.get('content', 'Unknown')} → {target_node.get('content', 'Unknown')}")
            print(f"      Type: {edge['edge_type']}")
            print(f"      Confidence: {edge['confidence']:.2f}")
            print(f"      Evidence: {edge.get('evidence', ['No evidence'])}")
            print(f"      Reasoning: {edge.get('reasoning', 'No reasoning')}")
            print()
        
        # Quality assessment
        print("🎯 V2 QUALITY ASSESSMENT:")
        print("-" * 40)
        
        # Check for clean entity classification
        person_nodes = [n for n in result_v2['hypernodes'] if n['node_type'] == 'person']
        clean_person_classification = len(person_nodes) > 0 and all(
            n.get('confidence', 0) > 0.8 for n in person_nodes
        )
        
        # Check for meaningful relationships
        meaningful_relationships = len([e for e in result_v2['hyperedges'] if e.get('confidence', 0) > 0.6])
        
        # Check for evidence in relationships
        relationships_with_evidence = len([e for e in result_v2['hyperedges'] if e.get('evidence') and len(e['evidence']) > 0])
        
        print(f"   ✅ Clean Person Classification: {clean_person_classification}")
        print(f"   ✅ Meaningful Relationships: {meaningful_relationships}/{len(result_v2['hyperedges'])}")
        print(f"   ✅ Relationships with Evidence: {relationships_with_evidence}/{len(result_v2['hyperedges'])}")
        print(f"   ✅ Entity Type Diversity: {len(node_types)} types")
        print(f"   ✅ Relationship Type Diversity: {len(edge_types)} types")
        
        # Overall assessment
        quality_indicators = [
            clean_person_classification,
            meaningful_relationships > len(result_v2['hyperedges']) * 0.5,
            relationships_with_evidence > len(result_v2['hyperedges']) * 0.3,
            len(node_types) >= 4,
            len(edge_types) >= 2
        ]
        
        quality_score = sum(quality_indicators) / len(quality_indicators)
        
        if quality_score >= 0.8:
            print(f"🎉 EXCELLENT: V2 Hypergraph Builder shows significant improvement!")
        elif quality_score >= 0.6:
            print(f"✅ GOOD: V2 Hypergraph Builder shows good improvement!")
        else:
            print(f"⚠️  NEEDS WORK: V2 Hypergraph Builder needs more improvement")
        
        print(f"   Overall Quality Score: {quality_score:.1%}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing V2: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_hypergraph_v2()
    exit(0 if success else 1)