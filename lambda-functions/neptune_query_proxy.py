#!/usr/bin/env python3
"""
Neptune Query Proxy Lambda
Provides HTTP API access to Neptune from outside VPC
"""

import json
import os
import logging
from typing import Dict, Any, List

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Neptune/Gremlin libraries
try:
    from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
    from gremlin_python.process.anonymous_traversal import traversal
    from gremlin_python.process.graph_traversal import __
    from gremlin_python.process.traversal import T
    GREMLIN_AVAILABLE = True
except ImportError:
    logger.error("Gremlin libraries not available")
    GREMLIN_AVAILABLE = False

def lambda_handler(event, context):
    """
    AWS Lambda handler for Neptune query proxy
    
    Expected event format:
    {
        "customer_id": "00_tim_wolff",
        "query_type": "nodes|edges|summary",
        "limit": 100
    }
    """
    
    correlation_id = context.aws_request_id
    logger.info(f"Neptune query proxy started (correlation_id: {correlation_id})")
    logger.info(f"Received event: {json.dumps(event)}")
    
    try:
        # Validate Gremlin availability
        if not GREMLIN_AVAILABLE:
            return create_error_response(500, "Gremlin libraries not available", correlation_id)
        
        # Parse request - handle API Gateway event format
        if 'body' in event:
            # API Gateway event format
            body = json.loads(event['body']) if event['body'] else {}
            customer_id = body.get('customer_id')
            query_type = body.get('query_type', 'nodes')
            limit = body.get('limit', 100)
        else:
            # Direct Lambda invocation format
            customer_id = event.get('customer_id')
            query_type = event.get('query_type', 'nodes')
            limit = event.get('limit', 100)
        
        if not customer_id:
            return create_error_response(400, "customer_id is required", correlation_id)
        
        # Get Neptune endpoint
        neptune_endpoint = os.environ.get('NEPTUNE_ENDPOINT')
        if not neptune_endpoint:
            return create_error_response(500, "NEPTUNE_ENDPOINT not configured", correlation_id)
        
        logger.info(f"Querying Neptune for customer {customer_id}, type: {query_type}")
        
        # Connect to Neptune
        connection = DriverRemoteConnection(f"wss://{neptune_endpoint}:8182/gremlin", 'g')
        g = traversal().withRemote(connection)
        
        # Execute query based on type
        if query_type == 'nodes':
            results = query_customer_nodes(g, customer_id, limit)
        elif query_type == 'edges':
            results = query_customer_edges(g, customer_id, limit)
        elif query_type == 'summary':
            results = query_customer_summary(g, customer_id)
        else:
            return create_error_response(400, f"Invalid query_type: {query_type}", correlation_id)
        
        # Close connection
        connection.close()
        
        logger.info(f"Query completed successfully, returned {len(results.get('data', []))} items")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            },
            'body': json.dumps({
                'customer_id': customer_id,
                'query_type': query_type,
                'correlation_id': correlation_id,
                'results': results
            }, default=str)
        }
        
    except Exception as e:
        logger.error(f"Query failed: {str(e)}", exc_info=True)
        return create_error_response(500, f"Query failed: {str(e)}", correlation_id)

def query_customer_nodes(g, customer_id: str, limit: int) -> Dict[str, Any]:
    """Query customer nodes from Neptune"""
    try:
        # Query vertices with customer_id property
        vertices = g.V().has('customer_id', customer_id).limit(limit).valueMap(True).toList()
        
        nodes = []
        for vertex in vertices:
            node = {
                'id': str(vertex[T.id]),
                'label': str(vertex[T.label]) if T.label in vertex else 'Unknown'
            }
            
            # Add all properties
            for key, value in vertex.items():
                if key not in [T.id, T.label]:
                    # Handle list values (Neptune often returns lists)
                    if isinstance(value, list) and len(value) == 1:
                        node[key] = value[0]
                    else:
                        node[key] = value
            
            nodes.append(node)
        
        return {
            'data': nodes,
            'count': len(nodes),
            'type': 'nodes'
        }
        
    except Exception as e:
        raise Exception(f"Failed to query nodes: {str(e)}")

def query_customer_edges(g, customer_id: str, limit: int) -> Dict[str, Any]:
    """Query customer edges from Neptune"""
    try:
        # Query edges between vertices with customer_id
        edges_query = (g.V().has('customer_id', customer_id)
                      .outE()
                      .where(__.inV().has('customer_id', customer_id))
                      .limit(limit)
                      .project('id', 'label', 'outV', 'inV', 'properties')
                      .by(T.id)
                      .by(T.label)
                      .by(__.outV().id())
                      .by(__.inV().id())
                      .by(__.valueMap()))
        
        edge_results = edges_query.toList()
        
        edges = []
        for edge_data in edge_results:
            edge = {
                'id': str(edge_data['id']),
                'label': str(edge_data['label']),
                'source': str(edge_data['outV']),
                'target': str(edge_data['inV']),
            }
            
            # Add edge properties
            properties = edge_data.get('properties', {})
            for key, value in properties.items():
                if isinstance(value, list) and len(value) == 1:
                    edge[key] = value[0]
                else:
                    edge[key] = value
            
            edges.append(edge)
        
        return {
            'data': edges,
            'count': len(edges),
            'type': 'edges'
        }
        
    except Exception as e:
        raise Exception(f"Failed to query edges: {str(e)}")

def query_customer_summary(g, customer_id: str) -> Dict[str, Any]:
    """Query customer graph summary from Neptune"""
    try:
        # Count nodes by type
        node_counts = {}
        vertices = g.V().has('customer_id', customer_id).valueMap(True).toList()
        
        for vertex in vertices:
            node_type = vertex.get('node_type', [vertex.get(T.label, 'unknown')])[0]
            node_counts[node_type] = node_counts.get(node_type, 0) + 1
        
        # Count edges by type
        edge_counts = {}
        edges = (g.V().has('customer_id', customer_id)
                .outE()
                .where(__.inV().has('customer_id', customer_id))
                .valueMap(True).toList())
        
        for edge in edges:
            edge_type = edge.get('edge_type', [edge.get(T.label, 'unknown')])[0]
            edge_counts[edge_type] = edge_counts.get(edge_type, 0) + 1
        
        return {
            'data': {
                'total_nodes': len(vertices),
                'total_edges': len(edges),
                'node_types': node_counts,
                'edge_types': edge_counts
            },
            'type': 'summary'
        }
        
    except Exception as e:
        raise Exception(f"Failed to query summary: {str(e)}")

def create_error_response(status_code: int, message: str, correlation_id: str) -> Dict[str, Any]:
    """Create standardized error response"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'error': message,
            'correlation_id': correlation_id
        })
    }

# For local testing
if __name__ == "__main__":
    # Test event
    test_event = {
        "customer_id": "00_tim_wolff",
        "query_type": "nodes",
        "limit": 10
    }
    
    class MockContext:
        aws_request_id = "test-correlation-id"
    
    # Mock environment
    os.environ['NEPTUNE_ENDPOINT'] = 'agentic-framework-neptune-dev.cluster-czwowusuervy.us-west-1.neptune.amazonaws.com'
    
    result = lambda_handler(test_event, MockContext())
    print(json.dumps(result, indent=2))