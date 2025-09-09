#!/usr/bin/env python3
"""
Comprehensive AWS End-to-End Test for Enhanced Hypergraph Builder V2
Tests the V2 version in the actual AWS environment with full workflow
"""

import boto3
import json
import time
from datetime import datetime

def test_v2_aws_deployment():
    """Test the V2 hypergraph builder in AWS environment end-to-end"""
    
    print("🧪 Testing Enhanced Hypergraph Builder V2 - AWS End-to-End")
    print("=" * 70)
    
    # Initialize AWS clients with development profile
    session = boto3.Session(profile_name='development')
    stepfunctions = session.client('stepfunctions', region_name='us-west-1')
    dynamodb = session.resource('dynamodb', region_name='us-west-1')
    lambda_client = session.client('lambda', region_name='us-west-1')
    
    # First, verify the V2 function is deployed correctly
    print("🔍 Verifying V2 Deployment...")
    try:
        response = lambda_client.get_function(FunctionName='agentic-hypergraph-builder-dev')
        handler = response['Configuration']['Handler']
        code_size = response['Configuration']['CodeSize']
        last_modified = response['Configuration']['LastModified']
        
        print(f"   Handler: {handler}")
        print(f"   Code Size: {code_size} bytes")
        print(f"   Last Modified: {last_modified}")
        
        if 'v2' in handler:
            print("   ✅ V2 handler detected")
        else:
            print("   ⚠️  Handler may not be V2")
            
    except Exception as e:
        print(f"   ❌ Error checking function: {str(e)}")
        return False
    
    print()
    
    # Test with Tim Wolff data (confirmed working)
    execution_name = f'v2-tim-wolff-test-{int(time.time())}'
    
    # Step Functions workflow ARN
    workflow_arn = 'arn:aws:states:us-west-1:765455500375:stateMachine:agentic-framework-processing-workflow-dev'
    
    # Test input with Tim Wolff data (known working)
    test_input = {
        'file_path': 'high_customers/00_tim_wolff/Berater = Netzwerk, Know-how, Backup.txt',
        'customer_folder': '00_tim_wolff',
        'customer_name': 'Tim Wolff',
        'processing_config': {
            'enable_detailed_analysis': True,
            'confidence_threshold': 0.7,
            'test_execution': True
        }
    }
    
    print(f"🚀 Starting V2 Validation Test: {execution_name}")
    print(f"   Customer: {test_input['customer_name']}")
    print(f"   File: {test_input['file_path']}")
    print(f"   Customer Folder: {test_input['customer_folder']}")
    print(f"   🎯 Confirming V2 system stability")
    print()
    
    try:
        # Start execution
        response = stepfunctions.start_execution(
            stateMachineArn=workflow_arn,
            name=execution_name,
            input=json.dumps(test_input)
        )
        
        execution_arn = response['executionArn']
        print(f"✅ Execution started: {execution_arn}")
        
        # Monitor execution
        print("⏳ Monitoring execution...")
        start_time = time.time()
        
        while True:
            response = stepfunctions.describe_execution(executionArn=execution_arn)
            status = response['status']
            
            elapsed = time.time() - start_time
            print(f"⏳ Status: {status} ({elapsed:.1f}s)")
            
            if status == 'SUCCEEDED':
                print("✅ Execution completed successfully!")
                break
            elif status == 'FAILED':
                print("❌ Execution failed!")
                print(f"Error: {response.get('error', 'Unknown error')}")
                return False
            elif status == 'TIMED_OUT':
                print("⏰ Execution timed out!")
                return False
            elif elapsed > 120:  # 2 minute timeout
                print("⏰ Test timeout reached!")
                return False
            
            time.sleep(2)
        
        print()
        
        # Get execution output
        execution_output = json.loads(response.get('output', '{}'))
        
        # Debug: Show the actual execution output structure
        print("🔍 RAW EXECUTION OUTPUT:")
        print("-" * 30)
        print(f"Keys: {list(execution_output.keys())}")
        for key, value in execution_output.items():
            if isinstance(value, dict):
                print(f"{key}: {list(value.keys())}")
            else:
                print(f"{key}: {type(value)}")
        print()
        
        # Analyze the hypergraph results
        print("🔍 ANALYZING V2 HYPERGRAPH RESULTS:")
        print("-" * 50)
        
        # Check if hypergraph data exists - V2 format
        hypergraph_result = execution_output.get('hypergraph_result', {})
        
        # Also check for V2 lambda response format
        if not hypergraph_result and 'enhanced_hypergraph_builder_agent_v2' in execution_output:
            v2_response = execution_output['enhanced_hypergraph_builder_agent_v2']
            if isinstance(v2_response, dict) and 'body' in v2_response:
                try:
                    body_data = json.loads(v2_response['body'])
                    hypergraph_result = body_data.get('result', {})
                    print(f"📋 Found V2 result in lambda response format")
                except json.JSONDecodeError:
                    print(f"❌ Failed to parse V2 lambda response body")
        
        # Also check direct result format
        if not hypergraph_result and 'result' in execution_output:
            hypergraph_result = execution_output['result']
            print(f"📋 Found result in direct format")
        if not hypergraph_result:
            print("❌ No hypergraph result found in execution output")
            return False
        
        # Extract hypergraph data
        if 'body' in hypergraph_result:
            try:
                body_data = json.loads(hypergraph_result['body'])
                hypergraph_data = body_data.get('result', {})
            except json.JSONDecodeError:
                hypergraph_data = hypergraph_result.get('result', {})
        else:
            hypergraph_data = hypergraph_result.get('result', {})
        
        if not hypergraph_data:
            print("❌ No hypergraph data found")
            return False
        
        # Analyze nodes
        nodes = hypergraph_data.get('hypernodes', [])
        edges = hypergraph_data.get('hyperedges', [])
        
        print(f"📊 Graph Statistics:")
        print(f"   Total Nodes: {len(nodes)}")
        print(f"   Total Edges: {len(edges)}")
        print()
        
        # Analyze node types
        node_types = {}
        person_nodes = []
        
        for node in nodes:
            node_type = node.get('node_type', 'unknown')
            content = node.get('content', 'Unknown')
            
            if node_type not in node_types:
                node_types[node_type] = []
            node_types[node_type].append(content)
            
            if node_type == 'person':
                person_nodes.append(node)
        
        print(f"📋 Node Type Distribution:")
        for node_type, node_list in node_types.items():
            print(f"   • {node_type.title()}: {len(node_list)}")
            # Show first few examples
            for i, content in enumerate(node_list[:3]):
                print(f"     - {content}")
            if len(node_list) > 3:
                print(f"     ... and {len(node_list) - 3} more")
        print()
        
        # Analyze edge types
        edge_types = {}
        edges_with_evidence = 0
        
        for edge in edges:
            edge_type = edge.get('edge_type', 'unknown')
            evidence = edge.get('evidence', [])
            
            if edge_type not in edge_types:
                edge_types[edge_type] = []
            edge_types[edge_type].append(edge)
            
            if evidence and len(evidence) > 0:
                edges_with_evidence += 1
        
        print(f"🔗 Edge Type Distribution:")
        for edge_type, edge_list in edge_types.items():
            avg_confidence = sum(e.get('confidence', 0) for e in edge_list) / len(edge_list)
            print(f"   • {edge_type.title()}: {len(edge_list)} (avg confidence: {avg_confidence:.2f})")
        print()
        
        # Show sample relationships with evidence
        print(f"🔍 Sample Relationships with Evidence:")
        sample_count = 0
        for edge in edges[:5]:  # Show first 5 edges
            source_node = next((n for n in nodes if n.get('id') == edge.get('source_node_id')), {})
            target_node = next((n for n in nodes if n.get('id') == edge.get('target_node_id')), {})
            
            source_content = source_node.get('content', 'Unknown')
            target_content = target_node.get('content', 'Unknown')
            edge_type = edge.get('edge_type', 'unknown')
            confidence = edge.get('confidence', 0)
            evidence = edge.get('evidence', [])
            reasoning = edge.get('reasoning', 'No reasoning provided')
            
            sample_count += 1
            print(f"   {sample_count}. {source_content} → {target_content}")
            print(f"      Type: {edge_type}")
            print(f"      Confidence: {confidence:.2f}")
            print(f"      Evidence: {evidence}")
            print(f"      Reasoning: {reasoning}")
            print()
        
        # Quality assessment
        print("🎯 V2 QUALITY ASSESSMENT:")
        print("-" * 40)
        
        # Check for clean person classification
        person_classified_correctly = len(person_nodes) > 0 and all(
            n.get('confidence', 0) > 0.8 for n in person_nodes
        )
        
        # Check for meaningful relationships
        meaningful_relationships = len([e for e in edges if e.get('confidence', 0) > 0.6])
        
        # Check for evidence in relationships
        relationships_with_evidence = edges_with_evidence
        
        # Check for entity type diversity
        entity_type_diversity = len(node_types)
        
        # Check for relationship type diversity
        relationship_type_diversity = len(edge_types)
        
        print(f"   ✅ Clean Person Classification: {person_classified_correctly}")
        print(f"   ✅ Meaningful Relationships: {meaningful_relationships}/{len(edges)}")
        print(f"   ✅ Relationships with Evidence: {relationships_with_evidence}/{len(edges)}")
        print(f"   ✅ Entity Type Diversity: {entity_type_diversity} types")
        print(f"   ✅ Relationship Type Diversity: {relationship_type_diversity} types")
        
        # Check for V2 specific improvements
        v2_indicators = []
        
        # 1. Person entity properly classified
        if person_classified_correctly:
            v2_indicators.append("Person entity properly classified")
        
        # 2. Multiple entity types
        if entity_type_diversity >= 4:
            v2_indicators.append("Rich entity type diversity")
        
        # 3. Evidence-based relationships
        if relationships_with_evidence > len(edges) * 0.5:
            v2_indicators.append("Evidence-based relationships")
        
        # 4. Semantic relationship types
        semantic_types = ['specializes_in', 'demonstrates', 'influences', 'relates_to']
        has_semantic_types = any(et in semantic_types for et in edge_types.keys())
        if has_semantic_types:
            v2_indicators.append("Semantic relationship types")
        
        # 5. Processing metadata indicating V2
        processing_metadata = hypergraph_data.get('processing_metadata', {})
        if processing_metadata.get('clean_entity_extraction') or processing_metadata.get('clean_relationship_extraction'):
            v2_indicators.append("V2 processing metadata detected")
        
        print()
        print("🔍 V2 SPECIFIC IMPROVEMENTS DETECTED:")
        for indicator in v2_indicators:
            print(f"   ✅ {indicator}")
        
        if not v2_indicators:
            print("   ⚠️  No V2 specific improvements detected")
        
        # Overall assessment
        quality_score = 0
        total_checks = 5
        
        if person_classified_correctly:
            quality_score += 1
        if meaningful_relationships > len(edges) * 0.7:
            quality_score += 1
        if relationships_with_evidence > len(edges) * 0.5:
            quality_score += 1
        if entity_type_diversity >= 4:
            quality_score += 1
        if relationship_type_diversity >= 3:
            quality_score += 1
        
        quality_percentage = (quality_score / total_checks) * 100
        
        print()
        if quality_percentage >= 80:
            print(f"🎉 EXCELLENT: V2 AWS deployment is working great!")
            print(f"   Quality Score: {quality_percentage:.0f}%")
            print(f"   V2 Improvements: {len(v2_indicators)}/5")
        elif quality_percentage >= 60:
            print(f"✅ GOOD: V2 AWS deployment is working well!")
            print(f"   Quality Score: {quality_percentage:.0f}%")
            print(f"   V2 Improvements: {len(v2_indicators)}/5")
        else:
            print(f"⚠️  NEEDS WORK: V2 AWS deployment needs improvement")
            print(f"   Quality Score: {quality_percentage:.0f}%")
            print(f"   V2 Improvements: {len(v2_indicators)}/5")
        
        # Check DynamoDB storage
        print()
        print("🗄️  Verifying DynamoDB Storage...")
        try:
            table = dynamodb.Table('agentic-framework-results')
            response = table.get_item(Key={'execution_id': execution_name})
            
            if 'Item' in response:
                item = response['Item']
                print("   ✅ Results stored in DynamoDB")
                print(f"   Processing Status: {item.get('processing_status', 'unknown')}")
                print(f"   Content Type: {item.get('content_type', 'unknown')}")
                
                # Check for hypergraph data in storage
                if 'hypergraph_data' in item:
                    print("   ✅ Hypergraph data stored")
                else:
                    print("   ⚠️  No hypergraph data in storage")
            else:
                print("   ❌ No results found in DynamoDB")
                
        except Exception as e:
            print(f"   ❌ Error checking DynamoDB: {str(e)}")
        
        print()
        print("=" * 70)
        print("🎯 AWS END-TO-END TEST SUMMARY")
        print("=" * 70)
        print(f"Execution Name: {execution_name}")
        print(f"Execution Time: {elapsed:.1f}s")
        print(f"Graph Quality: {quality_percentage:.0f}%")
        print(f"V2 Features: {len(v2_indicators)}/5")
        print(f"Nodes Generated: {len(nodes)}")
        print(f"Edges Generated: {len(edges)}")
        print(f"Evidence Coverage: {relationships_with_evidence}/{len(edges)}")
        
        return quality_percentage >= 60
        
    except Exception as e:
        print(f"❌ Error during AWS test: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_v2_aws_deployment()
    if success:
        print("\n🎉 V2 AWS deployment test PASSED!")
    else:
        print("\n❌ V2 AWS deployment test FAILED!")
    exit(0 if success else 1)