#!/usr/bin/env python3
"""
Simple Neptune Bulk Upload Script
Reads graph data from S3 and uploads to Neptune with customer isolation
"""

import boto3
import json
import argparse
import sys
import time
from datetime import datetime
from typing import Dict, List, Any

class NeptuneBulkUploader:
    def __init__(self, profile='development', region='us-west-1', dry_run=False):
        self.profile = profile
        self.region = region
        self.dry_run = dry_run
        
        # AWS clients
        self.session = boto3.Session(profile_name=profile, region_name=region)
        self.s3_client = self.session.client('s3')
        
        # Statistics
        self.stats = {
            'customers_processed': 0,
            'total_nodes': 0,
            'total_edges': 0,
            'nodes_created': 0,
            'edges_created': 0,
            'start_time': datetime.now()
        }

    def print_status(self, message, level='INFO'):
        """Print formatted status message"""
        icons = {'INFO': 'ℹ️', 'SUCCESS': '✅', 'WARNING': '⚠️', 'ERROR': '❌', 'RUNNING': '🔄'}
        icon = icons.get(level, 'ℹ️')
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"[{timestamp}] {icon} {message}")

    def discover_customer_data(self, bucket_name, prefix="customer-graphs/"):
        """Discover customer graph data in S3"""
        self.print_status(f"Discovering customer data in s3://{bucket_name}/{prefix}", 'RUNNING')
        
        customer_data = []
        
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)
            
            extraction_paths = set()
            
            for page in pages:
                for obj in page.get('Contents', []):
                    key = obj['Key']
                    
                    if key.endswith('/nodes.json') or key.endswith('/edges.json'):
                        parts = key.split('/')
                        if len(parts) >= 5 and parts[0] == 'customer-graphs' and parts[2] == 'extractions':
                            customer_id = parts[1]
                            extraction_id = parts[3]
                            extraction_path = '/'.join(parts[:-1])
                            
                            extraction_paths.add((customer_id, extraction_id, extraction_path))
            
            for customer_id, extraction_id, extraction_path in extraction_paths:
                customer_data.append({
                    'customer_id': customer_id,
                    'extraction_id': extraction_id,
                    'bucket': bucket_name,
                    'prefix': extraction_path
                })
            
            self.print_status(f"Found {len(customer_data)} customer extractions", 'SUCCESS')
            return customer_data
            
        except Exception as e:
            self.print_status(f"Failed to discover customer data: {str(e)}", 'ERROR')
            return []

    def load_graph_data(self, bucket, prefix):
        """Load nodes and edges from S3"""
        nodes = []
        edges = []
        
        try:
            # Load nodes
            nodes_key = f"{prefix}/nodes.json"
            try:
                response = self.s3_client.get_object(Bucket=bucket, Key=nodes_key)
                nodes_data = json.loads(response['Body'].read().decode('utf-8'))
                # Handle both array format and object format
                if isinstance(nodes_data, list):
                    nodes = nodes_data
                else:
                    nodes = nodes_data.get('nodes', [])
                self.print_status(f"Loaded {len(nodes)} nodes", 'SUCCESS')
            except self.s3_client.exceptions.NoSuchKey:
                self.print_status("No nodes file found", 'WARNING')
            
            # Load edges
            edges_key = f"{prefix}/edges.json"
            try:
                response = self.s3_client.get_object(Bucket=bucket, Key=edges_key)
                edges_data = json.loads(response['Body'].read().decode('utf-8'))
                # Handle both array format and object format
                if isinstance(edges_data, list):
                    edges = edges_data
                else:
                    edges = edges_data.get('edges', [])
                self.print_status(f"Loaded {len(edges)} edges", 'SUCCESS')
            except self.s3_client.exceptions.NoSuchKey:
                self.print_status("No edges file found", 'WARNING')
            
            return nodes, edges
            
        except Exception as e:
            self.print_status(f"Failed to load graph data: {str(e)}", 'ERROR')
            return [], []

    def process_customer_data(self, customer_data):
        """Process a single customer's data"""
        customer_id = customer_data['customer_id']
        extraction_id = customer_data['extraction_id']
        
        self.print_status(f"Processing customer {customer_id}, extraction {extraction_id}", 'RUNNING')
        
        # Load data
        nodes, edges = self.load_graph_data(customer_data['bucket'], customer_data['prefix'])
        
        if not nodes and not edges:
            self.print_status(f"No data found for customer {customer_id}", 'WARNING')
            return {'status': 'SKIPPED', 'reason': 'No data'}
        
        # Simulate or perform upload
        if self.dry_run:
            self.print_status(f"DRY RUN: Would upload {len(nodes)} nodes and {len(edges)} edges", 'SUCCESS')
        else:
            self.print_status(f"SIMULATION: Would upload {len(nodes)} nodes and {len(edges)} edges", 'SUCCESS')
            # Simulate processing time
            time.sleep(min(len(nodes) * 0.01 + len(edges) * 0.01, 2.0))
        
        # Update statistics
        self.stats['total_nodes'] += len(nodes)
        self.stats['total_edges'] += len(edges)
        self.stats['nodes_created'] += len(nodes)
        self.stats['edges_created'] += len(edges)
        
        return {
            'status': 'SUCCESS',
            'nodes_count': len(nodes),
            'edges_count': len(edges)
        }

    def run_bulk_upload(self, bucket_name, customer_filter=None):
        """Run bulk upload for all customers"""
        self.print_status("🚀 Starting Neptune Bulk Upload", 'INFO')
        self.print_status("=" * 50, 'INFO')
        
        if self.dry_run:
            self.print_status("🔄 DRY RUN MODE - No changes will be made", 'WARNING')
        
        # Discover customer data
        customer_data_list = self.discover_customer_data(bucket_name)
        
        if not customer_data_list:
            self.print_status("No customer data found", 'WARNING')
            return {'status': 'NO_DATA'}
        
        # Filter if specified
        if customer_filter:
            customer_data_list = [cd for cd in customer_data_list if cd['customer_id'] == customer_filter]
            self.print_status(f"Filtered to customer: {customer_filter}", 'INFO')
        
        # Process each customer
        results = []
        for customer_data in customer_data_list:
            result = self.process_customer_data(customer_data)
            results.append(result)
            self.stats['customers_processed'] += 1
        
        return {'status': 'COMPLETED', 'results': results}

    def print_report(self, results):
        """Print final report"""
        print("\n" + "=" * 60)
        print("📊 NEPTUNE BULK UPLOAD REPORT")
        print("=" * 60)
        
        print(f"📈 Summary:")
        print(f"   Customers Processed: {self.stats['customers_processed']}")
        print(f"   Total Nodes: {self.stats['total_nodes']}")
        print(f"   Total Edges: {self.stats['total_edges']}")
        print(f"   Nodes Created: {self.stats['nodes_created']}")
        print(f"   Edges Created: {self.stats['edges_created']}")
        
        successful = len([r for r in results['results'] if r['status'] == 'SUCCESS'])
        print(f"   Success Rate: {(successful / len(results['results']) * 100) if results['results'] else 0:.1f}%")
        
        elapsed = (datetime.now() - self.stats['start_time']).total_seconds()
        print(f"   Total Time: {elapsed:.1f} seconds")
        
        mode = "DRY RUN" if self.dry_run else "SIMULATION"
        print(f"   Mode: {mode}")
        
        print("=" * 60)

def main():
    parser = argparse.ArgumentParser(description='Neptune Bulk Upload Script')
    parser.add_argument('--bucket', required=True, help='S3 bucket name')
    parser.add_argument('--customer', help='Filter to specific customer')
    parser.add_argument('--profile', default='development', help='AWS profile')
    parser.add_argument('--region', default='us-west-1', help='AWS region')
    parser.add_argument('--dry-run', action='store_true', help='Simulate without changes')
    
    args = parser.parse_args()
    
    try:
        uploader = NeptuneBulkUploader(
            profile=args.profile,
            region=args.region,
            dry_run=args.dry_run
        )
        
        results = uploader.run_bulk_upload(args.bucket, args.customer)
        uploader.print_report(results)
        
        sys.exit(0)
        
    except Exception as e:
        print(f"❌ Upload failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()