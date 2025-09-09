#!/usr/bin/env python3
"""
AWS Data Format Diagnostic Test
Analyzes the exact data format passed to the V2 hypergraph builder in AWS
"""

import boto3
import json
import time

def test_aws_data_format():
    """Test to understand the AWS data format passed to V2 hypergraph builder"""
    
    print("🔍 AWS Data Format Diagnostic Test")
    print("=" * 50)
    
    # Initialize AWS clients
    session = boto3.Session(profile_name='development')
    stepfunctions = session.client('stepfunctions', region_name='us-west-1')
    
    # Create a simple test execution
    execution_name = f'data-format-test-{int(time.time())}'
    workflow_arn = 'arn:aws:states:us-west-1:765455500375:stateMachine:agentic-framework-processing-workflow-dev'
    
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
    
    print(f"🚀 Starting data format test: {execution_name}")
    
    try:
        # Start execution
        response = stepfunctions.start_execution(
            stateMachineArn=workflow_arn,
            name=execution_name,
            input=json.dumps(test_input)
        )
        
        execution_arn = response['executionArn']
        print(f"✅ Execution started: {execution_arn}")
        
        # Wait for completion
        while True:
            response = stepfunctions.describe_execution(executionArn=execution_arn)
            status = response['status']
            
            if status == 'SUCCEEDED':
                print("✅ Execution completed!")
                break
            elif status in ['FAILED', 'TIMED_OUT']:
                print(f"❌ Execution {status}")
                return False
            
            time.sleep(2)
        
        # Get execution history to see the hypergraph builder input
        print("\n🔍 Analyzing Step Functions execution history...")
        history = stepfunctions.get_execution_history(executionArn=execution_arn)
        
        # Find the hypergraph builder task
        hypergraph_task = None
        for event in history['events']:
            if event['type'] == 'TaskScheduled':
                params = event.get('taskScheduledEventDetails', {}).get('parameters', '')
                if 'agentic-hypergraph-builder-dev' in params:
                    hypergraph_task = json.loads(params)
                    break
        
        if not hypergraph_task:
            print("❌ Could not find hypergraph builder task in execution history")
            return False
        
        print("✅ Found hypergraph builder task!")
        print("\n📋 HYPERGRAPH BUILDER INPUT DATA STRUCTURE:")
        print("=" * 60)
        
        # Extract the payload sent to hypergraph builder
        payload = hypergraph_task.get('Payload', {})
        
        print("🔍 Top-level payload structure:")
        for key in payload.keys():
            print(f"   • {key}: {type(payload[key])}")
        
        # Examine agent_spec
        agent_spec = payload.get('agent_spec', {})
        print(f"\n🔍 agent_spec structure:")
        for key in agent_spec.keys():
            print(f"   • {key}: {type(agent_spec[key])}")
        
        # Examine processing_config
        processing_config = agent_spec.get('processing_config', {})
        print(f"\n🔍 processing_config structure:")
        for key in processing_config.keys():
            value_type = type(processing_config[key])
            if isinstance(processing_config[key], dict):
                print(f"   • {key}: {value_type} (keys: {list(processing_config[key].keys())})")
            elif isinstance(processing_config[key], str) and len(processing_config[key]) > 100:
                print(f"   • {key}: {value_type} (length: {len(processing_config[key])})")
            else:
                print(f"   • {key}: {value_type}")
        
        # Look for needs_analysis data
        needs_analysis = processing_config.get('needs_analysis', {})
        if needs_analysis:
            print(f"\n🔍 needs_analysis structure:")
            for key in needs_analysis.keys():
                value_type = type(needs_analysis[key])
                if isinstance(needs_analysis[key], str) and len(needs_analysis[key]) > 100:
                    print(f"   • {key}: {value_type} (length: {len(needs_analysis[key])})")
                else:
                    print(f"   • {key}: {value_type}")
            
            # If there's a body field, try to parse it
            if 'body' in needs_analysis:
                try:
                    body_data = json.loads(needs_analysis['body'])
                    print(f"\n🔍 needs_analysis.body parsed structure:")
                    for key in body_data.keys():
                        print(f"   • {key}: {type(body_data[key])}")
                    
                    # Look at the result
                    result = body_data.get('result', {})
                    if result:
                        print(f"\n🔍 needs_analysis.body.result structure:")
                        for key in result.keys():
                            value_type = type(result[key])
                            if isinstance(result[key], list):
                                print(f"   • {key}: {value_type} (length: {len(result[key])})")
                            else:
                                print(f"   • {key}: {value_type}")
                except json.JSONDecodeError:
                    print("   ⚠️  Could not parse needs_analysis.body as JSON")
        
        # Look for file analysis data
        file_analysis_keys = ['file_analysis', 'interview_data', 'content_result', 'financial_result']
        for key in file_analysis_keys:
            if key in processing_config:
                print(f"\n🔍 {key} structure:")
                data = processing_config[key]
                if isinstance(data, dict):
                    for subkey in data.keys():
                        value_type = type(data[subkey])
                        if isinstance(data[subkey], str) and len(data[subkey]) > 100:
                            print(f"   • {subkey}: {value_type} (length: {len(data[subkey])})")
                        else:
                            print(f"   • {subkey}: {value_type}")
                else:
                    print(f"   • Type: {type(data)}")
        
        # Save the full payload for detailed analysis
        print(f"\n💾 Saving full payload to 'aws_hypergraph_input.json' for detailed analysis...")
        with open('aws_hypergraph_input.json', 'w') as f:
            json.dump(payload, f, indent=2, default=str)
        
        print("\n🎯 KEY FINDINGS:")
        print("-" * 30)
        
        # Check what data sources are available
        data_sources = []
        if 'needs_analysis' in processing_config:
            data_sources.append("needs_analysis")
        if 'file_analysis' in processing_config:
            data_sources.append("file_analysis")
        if 'interview_data' in processing_config:
            data_sources.append("interview_data")
        if 'financial_result' in processing_config:
            data_sources.append("financial_result")
        
        print(f"📊 Available data sources: {data_sources}")
        
        # Check the customer info
        customer_name = processing_config.get('customer_name', 'Not found')
        customer_folder = processing_config.get('customer_folder', 'Not found')
        file_path = processing_config.get('file_path', 'Not found')
        
        print(f"👤 Customer Name: {customer_name}")
        print(f"📁 Customer Folder: {customer_folder}")
        print(f"📄 File Path: {file_path}")
        
        print(f"\n✅ Data format analysis complete!")
        print(f"📄 Full payload saved to: aws_hypergraph_input.json")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during test: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_aws_data_format()
    if success:
        print("\n🎉 Data format analysis completed successfully!")
    else:
        print("\n❌ Data format analysis failed!")