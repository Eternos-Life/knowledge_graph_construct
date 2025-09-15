#!/usr/bin/env python3
"""
Neptune Customer Graph Reader
Comprehensive tool for reading per-customer graph nodes and edges from Neptune database
"""

import boto3
import json
import argparse
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional
import pandas as pd

# Neptune/Gremlin libraries
try:
    from gremlin_python.driver import client
    from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
    from gremlin_python.process.anonymous_traversal import traversal
    from gremlin_python.process.graph_traversal import __
    from gremlin_python.process.traversal import T
    NEPTUNE_AVAILABLE = True
except ImportError:
    print("⚠️  Neptune/Gremlin libraries not installed")
    print("📦 Install with: pip install gremlinpython")
    NEPTUNE_AVAILABLE = False

class NeptuneCustomerGraphReader:
    def __init__(self, profile='development', region='us-west-1', environment='dev'):
        self.profile = profile
        self.region = region
        self.environment = environment
        
        # AWS clients
        self.session = boto3.Session(profile_name=profile, region_name=region)
        self.s3_client = self.session.client('s3')
        
        # Neptune connection (will be initialized when needed)
        self.neptune_endpoint = None
        self.gremlin_client = None
        self.g = None
        
        # Configuration
        self.account_id = self.session.client('sts').get_caller_identity()['Account']
        self.bucket_name = f"agentic-framework-customer-graphs-{environment}-{self.account_id}"

    def print_status(self, message: str, level: str = 'INFO'):
        """Print formatted status message"""
        icons = {'INFO': 'ℹ️', 'SUCCESS': '✅', 'WARNING': '⚠️', 'ERROR': '❌', 'RUNNING': '🔄'}
        icon = icons.get(level, 'ℹ️')
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"[{timestamp}] {icon} {message}")

    def get_neptune_endpoint(self) -> Optional[str]:
        """Get Neptune cluster endpoint from AWS"""
        try:
            neptune_client = self.session.client('neptune')
            response = neptune_client.describe_db_clusters()
            
            for cluster in response['DBClusters']:
                if cluster['Engine'] == 'neptune' and self.environment in cluster['DBClusterIdentifier']:
                    endpoint = cluster['Endpoint']
                    self.print_status(f"Found Neptune endpoint: {endpoint}", 'SUCCESS')
                    return endpoint
            
            self.print_status("No Neptune cluster found", 'WARNING')
            return None
            
        except Exception as e:
            self.print_status(f"Failed to get Neptune endpoint: {str(e)}", 'ERROR')
            return None

    def connect_to_neptune(self) -> bool:
        """Connect to Neptune database"""
        if not NEPTUNE_AVAILABLE:
            self.print_status("Neptune libraries not available", 'ERROR')
            return False
        
        try:
            if not self.neptune_endpoint:
                self.neptune_endpoint = self.get_neptune_endpoint()
                if not self.neptune_endpoint:
                    return False
            
            # Create Gremlin connection
            gremlin_endpoint = f"wss://{self.neptune_endpoint}:8182/gremlin"
            self.print_status(f"Connecting to Neptune: {gremlin_endpoint}", 'RUNNING')
            
            connection = DriverRemoteConnection(gremlin_endpoint, 'g')
            self.g = traversal().withRemote(connection)
            
            # Test connection
            vertex_count = self.g.V().count().next()
            self.print_status(f"Connected to Neptune - {vertex_count} vertices total", 'SUCCESS')
            return True
            
        except Exception as e:
            self.print_status(f"Failed to connect to Neptune: {str(e)}", 'ERROR')
            return False

    def list_customers_in_s3(self) -> List[str]:
        """List all customers with graph data in S3"""
        try:
            self.print_status("Discovering customers in S3", 'RUNNING')
            
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix='customer-graphs/')
            
            customers = set()
            for page in pages:
                for obj in page.get('Contents', []):
                    key_parts = obj['Key'].split('/')
                    if len(key_parts) >= 2 and key_parts[0] == 'customer-graphs':
                        customers.add(key_parts[1])
            
            customer_list = sorted(list(customers))
            self.print_status(f"Found {len(customer_list)} customers: {', '.join(customer_list)}", 'SUCCESS')
            return customer_list
            
        except Exception as e:
            self.print_status(f"Failed to list customers: {str(e)}", 'ERROR')
            return []

    def get_customer_extractions_s3(self, customer_id: str) -> List[Dict[str, Any]]:
        """Get all extractions for a customer from S3"""
        try:
            self.print_status(f"Getting extractions for customer {customer_id}", 'RUNNING')
            
            prefix = f"customer-graphs/{customer_id}/extractions/"
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix)
            
            extractions = []
            for page in pages:
                for obj in page.get('Contents', []):
                    if obj['Key'].endswith('/nodes.json'):
                        extraction_path = '/'.join(obj['Key'].split('/')[:-1])
                        extraction_id = extraction_path.split('/')[-1]
                        
                        # Check if edges.json also exists
                        edges_key = f"{extraction_path}/edges.json"
                        try:
                            self.s3_client.head_object(Bucket=self.bucket_name, Key=edges_key)
                            has_edges = True
                        except:
                            has_edges = False
                        
                        extractions.append({
                            'extraction_id': extraction_id,
                            'path': extraction_path,
                            'timestamp': obj['LastModified'],
                            'has_nodes': True,
                            'has_edges': has_edges
                        })
            
            # Sort by timestamp (newest first)
            extractions.sort(key=lambda x: x['timestamp'], reverse=True)
            
            self.print_status(f"Found {len(extractions)} extractions for {customer_id}", 'SUCCESS')
            return extractions
            
        except Exception as e:
            self.print_status(f"Failed to get extractions: {str(e)}", 'ERROR')
            return []

    def read_customer_nodes_s3(self, customer_id: str, extraction_id: str = None) -> List[Dict[str, Any]]:
        """Read customer nodes from S3"""
        try:
            # Get latest extraction if not specified
            if not extraction_id:
                extractions = self.get_customer_extractions_s3(customer_id)
                if not extractions:
                    self.print_status(f"No extractions found for customer {customer_id}", 'WARNING')
                    return []
                extraction_id = extractions[0]['extraction_id']
                self.print_status(f"Using latest extraction: {extraction_id}", 'INFO')
            
            # Load nodes
            nodes_key = f"customer-graphs/{customer_id}/extractions/{extraction_id}/nodes.json"
            self.print_status(f"Reading nodes from: {nodes_key}", 'RUNNING')
            
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=nodes_key)
            nodes_data = json.loads(response['Body'].read().decode('utf-8'))
            
            # Handle both array and object formats
            if isinstance(nodes_data, list):
                nodes = nodes_data
            else:
                nodes = nodes_data.get('nodes', [])
            
            self.print_status(f"Loaded {len(nodes)} nodes for customer {customer_id}", 'SUCCESS')
            return nodes
            
        except Exception as e:
            self.print_status(f"Failed to read nodes: {str(e)}", 'ERROR')
            return []

    def read_customer_edges_s3(self, customer_id: str, extraction_id: str = None) -> List[Dict[str, Any]]:
        """Read customer edges from S3"""
        try:
            # Get latest extraction if not specified
            if not extraction_id:
                extractions = self.get_customer_extractions_s3(customer_id)
                if not extractions:
                    self.print_status(f"No extractions found for customer {customer_id}", 'WARNING')
                    return []
                extraction_id = extractions[0]['extraction_id']
                self.print_status(f"Using latest extraction: {extraction_id}", 'INFO')
            
            # Load edges
            edges_key = f"customer-graphs/{customer_id}/extractions/{extraction_id}/edges.json"
            self.print_status(f"Reading edges from: {edges_key}", 'RUNNING')
            
            try:
                response = self.s3_client.get_object(Bucket=self.bucket_name, Key=edges_key)
                edges_data = json.loads(response['Body'].read().decode('utf-8'))
                
                # Handle both array and object formats
                if isinstance(edges_data, list):
                    edges = edges_data
                else:
                    edges = edges_data.get('edges', [])
                
                self.print_status(f"Loaded {len(edges)} edges for customer {customer_id}", 'SUCCESS')
                return edges
                
            except self.s3_client.exceptions.NoSuchKey:
                self.print_status(f"No edges file found for extraction {extraction_id}", 'WARNING')
                return []
            
        except Exception as e:
            self.print_status(f"Failed to read edges: {str(e)}", 'ERROR')
            return []

    def read_customer_nodes_neptune(self, customer_id: str) -> List[Dict[str, Any]]:
        """Read customer nodes directly from Neptune"""
        if not self.connect_to_neptune():
            return []
        
        try:
            self.print_status(f"Querying Neptune for customer {customer_id} nodes", 'RUNNING')
            
            # Query nodes with customer_id property
            vertices = self.g.V().has('customer_id', customer_id).valueMap(True).toList()
            
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
            
            self.print_status(f"Found {len(nodes)} nodes in Neptune for customer {customer_id}", 'SUCCESS')
            return nodes
            
        except Exception as e:
            self.print_status(f"Failed to query Neptune nodes: {str(e)}", 'ERROR')
            return []

    def read_customer_edges_neptune(self, customer_id: str) -> List[Dict[str, Any]]:
        """Read customer edges directly from Neptune"""
        if not self.connect_to_neptune():
            return []
        
        try:
            self.print_status(f"Querying Neptune for customer {customer_id} edges", 'RUNNING')
            
            # Query edges between vertices with customer_id
            edges_query = (self.g.V().has('customer_id', customer_id)
                          .outE()
                          .where(__.inV().has('customer_id', customer_id))
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
            
            self.print_status(f"Found {len(edges)} edges in Neptune for customer {customer_id}", 'SUCCESS')
            return edges
            
        except Exception as e:
            self.print_status(f"Failed to query Neptune edges: {str(e)}", 'ERROR')
            return []

    def analyze_customer_graph(self, customer_id: str, source: str = 'auto') -> Dict[str, Any]:
        """Analyze customer graph data"""
        self.print_status(f"🔍 Analyzing customer graph: {customer_id}", 'INFO')
        self.print_status("=" * 50, 'INFO')
        
        nodes = []
        edges = []
        
        # Determine data source
        if source == 'auto':
            # For local development, use S3 directly (Neptune is in VPC)
            self.print_status("Using S3 data source (Neptune is in VPC)", 'INFO')
            nodes = self.read_customer_nodes_s3(customer_id)
            edges = self.read_customer_edges_s3(customer_id)
        
        elif source == 'neptune':
            nodes = self.read_customer_nodes_neptune(customer_id)
            edges = self.read_customer_edges_neptune(customer_id)
        
        elif source == 's3':
            nodes = self.read_customer_nodes_s3(customer_id)
            edges = self.read_customer_edges_s3(customer_id)
        
        if not nodes and not edges:
            self.print_status(f"No graph data found for customer {customer_id}", 'WARNING')
            return {}
        
        # Analyze node types
        node_types = {}
        for node in nodes:
            node_type = node.get('node_type', node.get('label', 'unknown'))
            node_types[node_type] = node_types.get(node_type, 0) + 1
        
        # Analyze edge types
        edge_types = {}
        for edge in edges:
            edge_type = edge.get('edge_type', edge.get('label', 'unknown'))
            edge_types[edge_type] = edge_types.get(edge_type, 0) + 1
        
        # Create analysis
        analysis = {
            'customer_id': customer_id,
            'source': source,
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_nodes': len(nodes),
                'total_edges': len(edges),
                'node_types': len(node_types),
                'edge_types': len(edge_types)
            },
            'node_types': node_types,
            'edge_types': edge_types,
            'nodes': nodes,
            'edges': edges
        }
        
        return analysis

    def export_customer_data(self, customer_id: str, output_format: str = 'json', 
                           output_file: str = None, source: str = 'auto') -> bool:
        """Export customer graph data to various formats"""
        
        analysis = self.analyze_customer_graph(customer_id, source)
        if not analysis:
            return False
        
        # Generate output filename if not provided
        if not output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"customer_{customer_id}_graph_{timestamp}.{output_format}"
        
        try:
            if output_format == 'json':
                with open(output_file, 'w') as f:
                    json.dump(analysis, f, indent=2, default=str)
                
            elif output_format == 'csv':
                # Export nodes and edges as separate CSV files
                nodes_file = output_file.replace('.csv', '_nodes.csv')
                edges_file = output_file.replace('.csv', '_edges.csv')
                
                if analysis['nodes']:
                    pd.DataFrame(analysis['nodes']).to_csv(nodes_file, index=False)
                    self.print_status(f"Nodes exported to: {nodes_file}", 'SUCCESS')
                
                if analysis['edges']:
                    pd.DataFrame(analysis['edges']).to_csv(edges_file, index=False)
                    self.print_status(f"Edges exported to: {edges_file}", 'SUCCESS')
                
            elif output_format == 'summary':
                # Create human-readable summary
                summary = f"""
Customer Graph Analysis Report
==============================

Customer ID: {analysis['customer_id']}
Data Source: {analysis['source']}
Generated: {analysis['timestamp']}

Graph Summary:
- Total Nodes: {analysis['summary']['total_nodes']}
- Total Edges: {analysis['summary']['total_edges']}
- Node Types: {analysis['summary']['node_types']}
- Edge Types: {analysis['summary']['edge_types']}

Node Type Distribution:
"""
                for node_type, count in analysis['node_types'].items():
                    summary += f"- {node_type}: {count}\n"
                
                summary += "\nEdge Type Distribution:\n"
                for edge_type, count in analysis['edge_types'].items():
                    summary += f"- {edge_type}: {count}\n"
                
                with open(output_file, 'w') as f:
                    f.write(summary)
            
            self.print_status(f"Data exported to: {output_file}", 'SUCCESS')
            return True
            
        except Exception as e:
            self.print_status(f"Failed to export data: {str(e)}", 'ERROR')
            return False

    def print_customer_summary(self, customer_id: str, source: str = 'auto'):
        """Print a summary of customer graph data"""
        analysis = self.analyze_customer_graph(customer_id, source)
        if not analysis:
            return
        
        print(f"\n📊 Customer Graph Summary: {customer_id}")
        print("=" * 60)
        print(f"Data Source: {analysis['source'].upper()}")
        print(f"Total Nodes: {analysis['summary']['total_nodes']}")
        print(f"Total Edges: {analysis['summary']['total_edges']}")
        
        if analysis['node_types']:
            print(f"\n🔵 Node Types ({len(analysis['node_types'])}):")
            for node_type, count in sorted(analysis['node_types'].items(), key=lambda x: x[1], reverse=True):
                print(f"   {node_type}: {count}")
        
        if analysis['edge_types']:
            print(f"\n🔗 Edge Types ({len(analysis['edge_types'])}):")
            for edge_type, count in sorted(analysis['edge_types'].items(), key=lambda x: x[1], reverse=True):
                print(f"   {edge_type}: {count}")
        
        # Show sample nodes
        if analysis['nodes']:
            print(f"\n📋 Sample Nodes (first 3):")
            for i, node in enumerate(analysis['nodes'][:3]):
                node_id = node.get('id', 'N/A')
                node_type = node.get('node_type', node.get('label', 'unknown'))
                content = node.get('content', node.get('name', 'N/A'))
                print(f"   {i+1}. [{node_type}] {content[:50]}{'...' if len(str(content)) > 50 else ''}")
        
        print("=" * 60)

def main():
    parser = argparse.ArgumentParser(description='Neptune Customer Graph Reader')
    parser.add_argument('--customer', help='Customer ID to analyze')
    parser.add_argument('--list-customers', action='store_true', help='List all customers')
    parser.add_argument('--source', choices=['auto', 'neptune', 's3'], default='auto', 
                       help='Data source (auto=try Neptune first, then S3)')
    parser.add_argument('--export', choices=['json', 'csv', 'summary'], 
                       help='Export format')
    parser.add_argument('--output', help='Output file name')
    parser.add_argument('--profile', default='development', help='AWS profile')
    parser.add_argument('--region', default='us-west-1', help='AWS region')
    parser.add_argument('--environment', default='dev', help='Environment')
    
    args = parser.parse_args()
    
    try:
        reader = NeptuneCustomerGraphReader(
            profile=args.profile,
            region=args.region,
            environment=args.environment
        )
        
        if args.list_customers:
            customers = reader.list_customers_in_s3()
            if customers:
                print(f"\n📋 Available Customers ({len(customers)}):")
                for customer in customers:
                    print(f"   - {customer}")
            else:
                print("No customers found")
            return
        
        if not args.customer:
            print("❌ Please specify --customer or use --list-customers")
            sys.exit(1)
        
        # Analyze customer
        if args.export:
            success = reader.export_customer_data(
                args.customer, 
                args.export, 
                args.output, 
                args.source
            )
            if not success:
                sys.exit(1)
        else:
            reader.print_customer_summary(args.customer, args.source)
        
    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Operation failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()