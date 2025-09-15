#!/usr/bin/env python3
"""
Neptune Bulk Upload Trigger Lambda
Asynchronously triggers bulk upload of graph data to Neptune using the bulk upload script

This Lambda function is called asynchronously from the State Machine to trigger
Neptune bulk upload operations without blocking the main workflow.
"""

import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Dict, Any
import boto3
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
cloudwatch = boto3.client('cloudwatch')
s3_client = boto3.client('s3')

def lambda_handler(event, context):
    """
    AWS Lambda handler for triggering Neptune bulk upload operations
    
    Args:
        event: Lambda event containing bulk upload parameters
        context: Lambda context object
        
    Returns:
        Dict with operation results and status
    """
    correlation_id = context.aws_request_id
    
    try:
        # Extract event data
        bucket_name = event.get('bucket_name')
        customer_id = event.get('customer_id')
        extraction_id = event.get('extraction_id')
        s3_location = event.get('s3_location')
        nodes_count = event.get('nodes_count', 0)
        edges_count = event.get('edges_count', 0)
        source_file = event.get('source_file')
        execution_id = event.get('execution_id')
        async_mode = event.get('async_mode', True)
        
        logger.info(f"Starting Neptune bulk upload trigger for customer {customer_id[:8] if customer_id else 'unknown'}... "
                   f"(correlation_id: {correlation_id})")
        
        # Validate required parameters
        if not bucket_name or not customer_id:
            raise ValueError("bucket_name and customer_id are required")
        
        # Emit start metrics
        emit_metric('NeptuneBulkUploadTriggered', 1, {'customer_id': customer_id})
        
        # Prepare bulk upload command
        bulk_upload_script = '/opt/python/neptune_bulk_upload_simple.py'
        
        # Check if bulk upload script exists in the Lambda package
        if not os.path.exists(bulk_upload_script):
            # Fallback to simulation mode if script not available
            logger.warning("Bulk upload script not found in Lambda package, using simulation mode")
            return simulate_bulk_upload(event, correlation_id)
        
        # Prepare command arguments
        cmd_args = [
            sys.executable, bulk_upload_script,
            '--bucket', bucket_name,
            '--customer', customer_id,
            '--profile', 'lambda',  # Use Lambda execution role
            '--region', os.environ.get('AWS_DEFAULT_REGION', 'us-west-1')
        ]
        
        # Add extraction filter if specified
        if extraction_id:
            # Note: The bulk upload script would need to be enhanced to support extraction filtering
            logger.info(f"Targeting specific extraction: {extraction_id}")
        
        logger.info(f"Executing bulk upload command: {' '.join(cmd_args)}")
        
        # Execute bulk upload script
        start_time = time.time()
        
        try:
            # Run the bulk upload script
            result = subprocess.run(
                cmd_args,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                env={
                    **os.environ,
                    'AWS_DEFAULT_REGION': os.environ.get('AWS_DEFAULT_REGION', 'us-west-1')
                }
            )
            
            execution_time = time.time() - start_time
            
            if result.returncode == 0:
                logger.info(f"Bulk upload completed successfully in {execution_time:.1f}s")
                logger.info(f"Bulk upload output: {result.stdout}")
                
                # Parse output for statistics (if available)
                stats = parse_bulk_upload_output(result.stdout)
                
                # Emit success metrics
                emit_metric('NeptuneBulkUploadSuccess', 1, {'customer_id': customer_id})
                emit_metric('NeptuneBulkUploadDuration', execution_time, {'customer_id': customer_id}, 'Seconds')
                
                if stats.get('nodes_processed'):
                    emit_metric('NeptuneBulkUploadNodesProcessed', stats['nodes_processed'], {'customer_id': customer_id})
                if stats.get('edges_processed'):
                    emit_metric('NeptuneBulkUploadEdgesProcessed', stats['edges_processed'], {'customer_id': customer_id})
                
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'message': 'Neptune bulk upload completed successfully',
                        'correlation_id': correlation_id,
                        'customer_id': customer_id[:8] + '...',
                        'execution_time_seconds': execution_time,
                        'async_mode': async_mode,
                        'bulk_upload_stats': stats,
                        'extraction_id': extraction_id,
                        'nodes_count': nodes_count,
                        'edges_count': edges_count
                    })
                }
            else:
                logger.error(f"Bulk upload failed with return code {result.returncode}")
                logger.error(f"Bulk upload stderr: {result.stderr}")
                
                # Emit failure metrics
                emit_metric('NeptuneBulkUploadFailure', 1, {'customer_id': customer_id})
                
                return {
                    'statusCode': 500,
                    'body': json.dumps({
                        'error': f'Bulk upload script failed with return code {result.returncode}',
                        'correlation_id': correlation_id,
                        'stderr': result.stderr,
                        'stdout': result.stdout
                    })
                }
                
        except subprocess.TimeoutExpired:
            logger.error("Bulk upload script timed out after 5 minutes")
            emit_metric('NeptuneBulkUploadTimeout', 1, {'customer_id': customer_id})
            
            return {
                'statusCode': 408,
                'body': json.dumps({
                    'error': 'Bulk upload operation timed out',
                    'correlation_id': correlation_id,
                    'timeout_seconds': 300
                })
            }
            
    except Exception as e:
        error_msg = f"Unexpected error in Neptune bulk upload trigger: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        # Emit error metrics
        emit_metric('NeptuneBulkUploadTriggerError', 1, {'customer_id': customer_id or 'unknown'})
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': error_msg,
                'correlation_id': correlation_id
            })
        }

def simulate_bulk_upload(event: Dict[str, Any], correlation_id: str) -> Dict[str, Any]:
    """
    Simulate bulk upload operation when script is not available
    
    Args:
        event: Lambda event data
        correlation_id: Request correlation ID
        
    Returns:
        Simulated response
    """
    customer_id = event.get('customer_id', 'unknown')
    nodes_count = event.get('nodes_count', 0)
    edges_count = event.get('edges_count', 0)
    
    logger.info(f"SIMULATION: Would bulk upload {nodes_count} nodes and {edges_count} edges for customer {customer_id}")
    
    # Simulate processing time
    processing_time = min((nodes_count + edges_count) * 0.01, 5.0)
    time.sleep(processing_time)
    
    # Emit simulation metrics
    emit_metric('NeptuneBulkUploadSimulation', 1, {'customer_id': customer_id})
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Neptune bulk upload simulation completed',
            'correlation_id': correlation_id,
            'customer_id': customer_id[:8] + '...',
            'simulation_mode': True,
            'nodes_count': nodes_count,
            'edges_count': edges_count,
            'processing_time_seconds': processing_time
        })
    }

def parse_bulk_upload_output(output: str) -> Dict[str, Any]:
    """
    Parse bulk upload script output to extract statistics
    
    Args:
        output: Script stdout output
        
    Returns:
        Dictionary with parsed statistics
    """
    stats = {}
    
    try:
        # Look for common patterns in bulk upload output
        lines = output.split('\n')
        
        for line in lines:
            if 'Customers Processed:' in line:
                try:
                    stats['customers_processed'] = int(line.split(':')[1].strip())
                except:
                    pass
            elif 'Total Nodes:' in line:
                try:
                    stats['nodes_processed'] = int(line.split(':')[1].strip())
                except:
                    pass
            elif 'Total Edges:' in line:
                try:
                    stats['edges_processed'] = int(line.split(':')[1].strip())
                except:
                    pass
            elif 'Success Rate:' in line:
                try:
                    stats['success_rate'] = float(line.split(':')[1].strip().replace('%', ''))
                except:
                    pass
        
        logger.info(f"Parsed bulk upload statistics: {stats}")
        
    except Exception as e:
        logger.warning(f"Failed to parse bulk upload output: {str(e)}")
    
    return stats

def emit_metric(metric_name: str, value: float, dimensions: Dict[str, str] = None, unit: str = 'Count'):
    """
    Emit custom CloudWatch metric
    
    Args:
        metric_name: Name of the metric
        value: Metric value
        dimensions: Optional metric dimensions
        unit: CloudWatch unit type
    """
    try:
        metric_data = {
            'MetricName': metric_name,
            'Value': value,
            'Unit': unit,
            'Timestamp': datetime.now(timezone.utc)
        }
        
        if dimensions:
            metric_data['Dimensions'] = [
                {'Name': k, 'Value': v} for k, v in dimensions.items()
            ]
        
        cloudwatch.put_metric_data(
            Namespace='NeptuneBulkUpload',
            MetricData=[metric_data]
        )
        
    except Exception as e:
        logger.warning(f"Failed to emit CloudWatch metric {metric_name}: {str(e)}")

# For local testing
if __name__ == "__main__":
    # Test event
    test_event = {
        "bucket_name": "agentic-framework-customer-graphs-dev-765455500375",
        "customer_id": "00_tim_wolff",
        "extraction_id": "test-extraction",
        "s3_location": "s3://test-bucket/test-path",
        "nodes_count": 13,
        "edges_count": 4,
        "source_file": "test-file.txt",
        "execution_id": "test-execution",
        "async_mode": True
    }
    
    class MockContext:
        aws_request_id = "test-correlation-id"
    
    result = lambda_handler(test_event, MockContext())
    print(json.dumps(result, indent=2))