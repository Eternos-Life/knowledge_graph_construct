"""
AWS Lambda Function: 6 Human Needs Analysis Agent - CLEAN VERSION
Simplified input handling for Step Functions workflow
"""

import json
import boto3
import os
import time
import uuid
from decimal import Decimal
from typing import Dict, List, Any

def lambda_handler(event, context):
    """
    Clean Lambda handler for needs analysis agent
    """
    start_time = time.time()
    
    try:
        print(f"Received event keys: {list(event.keys())}")
        
        # Extract execution ID
        execution_id = event.get('execution_id', context.aws_request_id)
        
        # Find content data from Step Functions event
        content_data = None
        
        # Method 1: Check interview_result from Step Functions
        if 'interview_result' in event:
            interview_result = event['interview_result']
            print(f"Found interview_result: {type(interview_result)}")
            
            if isinstance(interview_result, dict) and 'Payload' in interview_result:
                payload = interview_result['Payload']
                if isinstance(payload, dict) and 'body' in payload:
                    body = payload['body']
                    if isinstance(body, str):
                        try:
                            body_data = json.loads(body)
                            if 'result' in body_data and 'raw_text' in body_data['result']:
                                raw_text = body_data['result']['raw_text']
                                entities = body_data['result'].get('entities', [])
                                key_insights = body_data['result'].get('key_insights', {})
                                themes = key_insights.get('main_themes', [])
                                
                                content_data = {
                                    'raw_text': raw_text,
                                    'entities': entities,
                                    'themes': themes
                                }
                                print(f"✅ Found content from interview_result: {len(raw_text):,} chars")
                        except json.JSONDecodeError as e:
                            print(f"Failed to parse interview result body: {e}")
        
        # Method 2: Fallback - try to load from S3 directly
        if not content_data:
            file_path = event.get('agent_spec', {}).get('processing_config', {}).get('file_path', '')
            if file_path:
                print(f"Attempting S3 fallback for: {file_path}")
                try:
                    s3 = boto3.client('s3')
                    if file_path.startswith('s3://'):
                        # Parse S3 URL
                        parts = file_path.replace('s3://', '').split('/', 1)
                        bucket_name = parts[0]
                        s3_key = parts[1]
                    else:
                        bucket_name = os.environ.get('S3_INPUT_BUCKET', 'agentic-framework-input-files-dev-765455500375')
                        s3_key = file_path
                    
                    response = s3.get_object(Bucket=bucket_name, Key=s3_key)
                    raw_text = response['Body'].read().decode('utf-8')
                    
                    # Remove frontmatter if present
                    if raw_text.startswith('---'):
                        end_marker = raw_text.find('---', 3)
                        if end_marker > 0:
                            raw_text = raw_text[end_marker + 3:].strip()
                    
                    content_data = {
                        'raw_text': raw_text,
                        'entities': [],
                        'themes': []
                    }
                    print(f"✅ Loaded content from S3: {len(raw_text):,} chars")
                    
                except Exception as e:
                    print(f"S3 fallback failed: {e}")
        
        # Validate we have content
        if not content_data or not content_data.get('raw_text'):
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'execution_id': execution_id,
                    'agent_type': 'needs_analysis',
                    'error': 'No text content found for analysis',
                    'success': False
                })
            }
        
        # Perform needs analysis
        raw_text = content_data['raw_text']
        entities = content_data.get('entities', [])
        themes = content_data.get('themes', [])
        
        print(f"Analyzing {len(raw_text):,} characters of text")
        
        # Simple needs analysis (using basic keyword matching for reliability)
        needs_scores = analyze_needs_simple(raw_text)
        
        # Create dominant needs list
        dominant_needs = sorted(needs_scores.items(), key=lambda x: x[1], reverse=True)[:3]
        
        # Create result
        result = {
            'needs_scores': needs_scores,
            'dominant_needs': dominant_needs,
            'behavioral_patterns': extract_patterns(raw_text),
            'personality_traits': extract_traits(raw_text, needs_scores),
            'life_themes': themes if themes else extract_themes(raw_text),
            'confidence_score': 0.8,
            'processing_time': time.time() - start_time
        }
        
        print(f"Analysis complete. Top need: {dominant_needs[0][0] if dominant_needs else 'None'}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'execution_id': execution_id,
                'agent_type': 'needs_analysis',
                'result': result,
                'success': True
            })
        }
        
    except Exception as e:
        print(f"Error in needs analysis: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        
        return {
            'statusCode': 500,
            'body