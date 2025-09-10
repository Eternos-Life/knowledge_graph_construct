"""
Graph Extraction Agent - Extracts nodes and edges from enhanced hypergraph builder output
Parses the enhanced_hypergraph_builder_agent_v2.py JSON output format and prepares data for persistence
"""

import json
import uuid
import boto3
import time
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from decimal import Decimal
import logging
from botocore.exceptions import ClientError, BotoCoreError
import os
import traceback

# Configure structured logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# CloudWatch metrics client
cloudwatch = boto3.client('cloudwatch')

class CorrelationContext:
    """Context manager for correlation ID tracking"""
    
    def __init__(self, correlation_id: str = None):
        self.correlation_id = correlation_id or str(uuid.uuid4())[:8]
        self.start_time = time.time()
    
    def log_info(self, message: str, **kwargs):
        """Log info message with correlation ID"""
        logger.info(f"[{self.correlation_id}] {message}", extra=kwargs)
    
    def log_warning(self, message: str, **kwargs):
        """Log warning message with correlation ID"""
        logger.warning(f"[{self.correlation_id}] {message}", extra=kwargs)
    
    def log_error(self, message: str, **kwargs):
        """Log error message with correlation ID"""
        logger.error(f"[{self.correlation_id}] {message}", extra=kwargs)
    
    def log_debug(self, message: str, **kwargs):
        """Log debug message with correlation ID"""
        logger.debug(f"[{self.correlation_id}] {message}", extra=kwargs)
    
    def get_duration(self) -> float:
        """Get elapsed time since context creation"""
        return time.time() - self.start_time

class CloudWatchMetrics:
    """CloudWatch metrics emission for monitoring"""
    
    def __init__(self, namespace: str = "CustomerGraphPersistence"):
        self.namespace = namespace
        self.cloudwatch = cloudwatch
    
    def emit_extraction_success(self, customer_id: str, nodes_count: int, edges_count: int, duration: float):
        """Emit successful extraction metrics"""
        try:
            self.cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=[
                    {
                        'MetricName': 'ExtractionSuccess',
                        'Value': 1,
                        'Unit': 'Count',
                        'Dimensions': [
                            {'Name': 'CustomerID', 'Value': self._sanitize_dimension_value(customer_id)}
                        ]
                    },
                    {
                        'MetricName': 'NodesExtracted',
                        'Value': nodes_count,
                        'Unit': 'Count',
                        'Dimensions': [
                            {'Name': 'CustomerID', 'Value': self._sanitize_dimension_value(customer_id)}
                        ]
                    },
                    {
                        'MetricName': 'EdgesExtracted',
                        'Value': edges_count,
                        'Unit': 'Count',
                        'Dimensions': [
                            {'Name': 'CustomerID', 'Value': self._sanitize_dimension_value(customer_id)}
                        ]
                    },
                    {
                        'MetricName': 'ExtractionDuration',
                        'Value': duration,
                        'Unit': 'Seconds',
                        'Dimensions': [
                            {'Name': 'CustomerID', 'Value': self._sanitize_dimension_value(customer_id)}
                        ]
                    }
                ]
            )
        except Exception as e:
            logger.warning(f"Failed to emit success metrics: {str(e)}")
    
    def emit_extraction_failure(self, customer_id: str, error_type: str, duration: float):
        """Emit extraction failure metrics"""
        try:
            self.cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=[
                    {
                        'MetricName': 'ExtractionFailure',
                        'Value': 1,
                        'Unit': 'Count',
                        'Dimensions': [
                            {'Name': 'CustomerID', 'Value': self._sanitize_dimension_value(customer_id)},
                            {'Name': 'ErrorType', 'Value': error_type}
                        ]
                    },
                    {
                        'MetricName': 'ExtractionDuration',
                        'Value': duration,
                        'Unit': 'Seconds',
                        'Dimensions': [
                            {'Name': 'CustomerID', 'Value': self._sanitize_dimension_value(customer_id)},
                            {'Name': 'Status', 'Value': 'Failed'}
                        ]
                    }
                ]
            )
        except Exception as e:
            logger.warning(f"Failed to emit failure metrics: {str(e)}")
    
    def emit_s3_operation_metrics(self, operation: str, success: bool, duration: float, customer_id: str):
        """Emit S3 operation metrics"""
        try:
            self.cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=[
                    {
                        'MetricName': f'S3{operation}{"Success" if success else "Failure"}',
                        'Value': 1,
                        'Unit': 'Count',
                        'Dimensions': [
                            {'Name': 'CustomerID', 'Value': self._sanitize_dimension_value(customer_id)},
                            {'Name': 'Operation', 'Value': operation}
                        ]
                    },
                    {
                        'MetricName': f'S3{operation}Duration',
                        'Value': duration,
                        'Unit': 'Seconds',
                        'Dimensions': [
                            {'Name': 'CustomerID', 'Value': self._sanitize_dimension_value(customer_id)},
                            {'Name': 'Operation', 'Value': operation}
                        ]
                    }
                ]
            )
        except Exception as e:
            logger.warning(f"Failed to emit S3 operation metrics: {str(e)}")
    
    def _sanitize_dimension_value(self, value: str) -> str:
        """Sanitize dimension values for CloudWatch"""
        # Remove sensitive data and limit length
        sanitized = str(value)[:50]
        # Replace any potentially sensitive patterns
        import re
        sanitized = re.sub(r'[^\w\-_.]', '_', sanitized)
        return sanitized or 'unknown'

class ErrorCategorizer:
    """Categorizes errors for appropriate response strategies"""
    
    ERROR_CATEGORIES = {
        'VALIDATION_ERROR': {
            'description': 'Input validation failed',
            'retry': False,
            'alert': False
        },
        'PARSING_ERROR': {
            'description': 'Hypergraph data parsing failed',
            'retry': False,
            'alert': True
        },
        'S3_TRANSIENT_ERROR': {
            'description': 'Temporary S3 service issue',
            'retry': True,
            'alert': False
        },
        'S3_PERMISSION_ERROR': {
            'description': 'S3 access permission denied',
            'retry': False,
            'alert': True
        },
        'S3_STORAGE_ERROR': {
            'description': 'S3 storage operation failed',
            'retry': True,
            'alert': True
        },
        'INTERNAL_ERROR': {
            'description': 'Unexpected internal error',
            'retry': False,
            'alert': True
        }
    }
    
    @classmethod
    def categorize_error(cls, error: Exception) -> str:
        """Categorize error based on type and message"""
        error_str = str(error).lower()
        
        if isinstance(error, GraphExtractionError):
            if 'validation' in error_str or 'required' in error_str:
                return 'VALIDATION_ERROR'
            elif 'parse' in error_str or 'format' in error_str:
                return 'PARSING_ERROR'
            else:
                return 'INTERNAL_ERROR'
        
        elif isinstance(error, S3StorageError):
            if 'access denied' in error_str or 'forbidden' in error_str:
                return 'S3_PERMISSION_ERROR'
            elif 'timeout' in error_str or 'throttl' in error_str or 'service unavailable' in error_str:
                return 'S3_TRANSIENT_ERROR'
            else:
                return 'S3_STORAGE_ERROR'
        
        elif isinstance(error, (ClientError, BotoCoreError)):
            error_code = getattr(error, 'response', {}).get('Error', {}).get('Code', '')
            if error_code in ['AccessDenied', 'Forbidden']:
                return 'S3_PERMISSION_ERROR'
            elif error_code in ['ServiceUnavailable', 'Throttling', 'RequestTimeout']:
                return 'S3_TRANSIENT_ERROR'
            else:
                return 'S3_STORAGE_ERROR'
        
        else:
            return 'INTERNAL_ERROR'
    
    @classmethod
    def get_error_info(cls, category: str) -> Dict[str, Any]:
        """Get error category information"""
        return cls.ERROR_CATEGORIES.get(category, cls.ERROR_CATEGORIES['INTERNAL_ERROR'])

class SensitiveDataSanitizer:
    """Sanitizes logs and error messages to prevent sensitive data exposure"""
    
    SENSITIVE_PATTERNS = [
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email addresses
        r'\b\d{3}-\d{2}-\d{4}\b',  # SSN pattern
        r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',  # Credit card pattern
        r'\b(?:password|pwd|secret|key|token)[\s=:]+\S+\b',  # Credentials
    ]
    
    @classmethod
    def sanitize_message(cls, message: str) -> str:
        """Remove sensitive data from log messages"""
        import re
        sanitized = message
        
        for pattern in cls.SENSITIVE_PATTERNS:
            sanitized = re.sub(pattern, '[REDACTED]', sanitized, flags=re.IGNORECASE)
        
        return sanitized
    
    @classmethod
    def sanitize_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively sanitize dictionary data"""
        if not isinstance(data, dict):
            return data
        
        sanitized = {}
        sensitive_keys = ['password', 'secret', 'key', 'token', 'credential', 'auth']
        
        for key, value in data.items():
            if any(sensitive_key in key.lower() for sensitive_key in sensitive_keys):
                sanitized[key] = '[REDACTED]'
            elif isinstance(value, dict):
                sanitized[key] = cls.sanitize_dict(value)
            elif isinstance(value, str):
                sanitized[key] = cls.sanitize_message(value)
            else:
                sanitized[key] = value
        
        return sanitized

@dataclass
class ExtractedNode:
    """Extracted node data structure for graph persistence"""
    id: str
    customer_id: str
    label: str
    node_type: str
    confidence: float
    attributes: Dict[str, Any]
    source_file: str
    created_at: str
    metadata: Dict[str, Any]

@dataclass
class ExtractedEdge:
    """Extracted edge data structure for graph persistence"""
    id: str
    customer_id: str
    source_node_id: str
    target_node_id: str
    relationship_type: str
    weight: float
    attributes: Dict[str, Any]
    source_file: str
    created_at: str
    metadata: Dict[str, Any]

@dataclass
class ExtractionResult:
    """Result of graph extraction process"""
    extraction_id: str
    customer_id: str
    extracted_nodes: List[ExtractedNode]
    extracted_edges: List[ExtractedEdge]
    s3_location: str
    extraction_metadata: Dict[str, Any]

class HypergraphParser:
    """Parses enhanced hypergraph builder output format"""
    
    def __init__(self, correlation_context: CorrelationContext):
        self.ctx = correlation_context
        self.supported_node_types = {
            'person', 'organization', 'concept', 'skill', 'need', 
            'behavioral_pattern', 'personality_trait', 'financial_instrument',
            'business_concept', 'topic'
        }
        self.supported_edge_types = {
            'demonstrates', 'relates_to', 'influences', 'requires', 'enables',
            'part_of', 'similar_to', 'works_with', 'specializes_in', 'interviews',
            'discusses', 'affiliated_with', 'uses'
        }
    
    def parse_hypergraph_output(self, hypergraph_data: Dict[str, Any], 
                               customer_id: str, source_file: str) -> Tuple[List[ExtractedNode], List[ExtractedEdge]]:
        """
        Parse hypergraph output and extract nodes and edges
        
        Args:
            hypergraph_data: Output from enhanced_hypergraph_builder_agent_v2
            customer_id: Customer identifier for data isolation
            source_file: Source file path for traceability
            
        Returns:
            Tuple of (extracted_nodes, extracted_edges)
        """
        try:
            # Handle both hypernodes/hyperedges and nodes/edges formats
            if 'hypernodes' in hypergraph_data or 'hyperedges' in hypergraph_data:
                # Enhanced hypergraph format
                hypernodes = hypergraph_data.get('hypernodes', [])
                hyperedges = hypergraph_data.get('hyperedges', [])
                self.ctx.log_debug(f"Processing enhanced format: {len(hypernodes)} hypernodes, {len(hyperedges)} hyperedges")
                extracted_nodes = self._extract_nodes(hypernodes, customer_id, source_file)
                extracted_edges = self._extract_edges(hyperedges, customer_id, source_file)
            else:
                # Standard nodes/edges format - convert to hypernodes/hyperedges format
                nodes = hypergraph_data.get('nodes', [])
                edges = hypergraph_data.get('edges', [])
                self.ctx.log_debug(f"Processing standard format: {len(nodes)} nodes, {len(edges)} edges")
                
                # Convert nodes to hypernodes format
                hypernodes = []
                for node in nodes:
                    hypernode = {
                        'content': node.get('text', node.get('content', node.get('label', ''))),
                        'node_type': node.get('type', node.get('node_type', 'concept')),
                        'confidence': node.get('confidence', node.get('weight', 0.5)),
                        'timestamp': node.get('timestamp', ''),
                        'metadata': node.get('metadata', {})
                    }
                    hypernodes.append(hypernode)
                
                # Convert edges to hyperedges format
                hyperedges = []
                for edge in edges:
                    hyperedge = {
                        'source_node_id': edge.get('source', edge.get('source_id', edge.get('from', ''))),
                        'target_node_id': edge.get('target', edge.get('target_id', edge.get('to', ''))),
                        'edge_type': edge.get('type', edge.get('edge_type', edge.get('relationship', 'relates_to'))),
                        'confidence': edge.get('confidence', edge.get('weight', 0.5)),
                        'timestamp': edge.get('timestamp', ''),
                        'metadata': edge.get('metadata', {})
                    }
                    hyperedges.append(hyperedge)
                
                extracted_nodes = self._extract_nodes(hypernodes, customer_id, source_file)
                extracted_edges = self._extract_edges(hyperedges, customer_id, source_file)
            
            self.ctx.log_info(f"Successfully parsed {len(extracted_nodes)} nodes and {len(extracted_edges)} edges")
            
            return extracted_nodes, extracted_edges
            
        except Exception as e:
            logger.error(f"Error parsing hypergraph output: {str(e)}")
            raise ValueError(f"Failed to parse hypergraph data: {str(e)}")
    
    def _extract_nodes(self, hypernodes: List[Dict], customer_id: str, source_file: str) -> List[ExtractedNode]:
        """Extract and validate nodes from hypernodes"""
        extracted_nodes = []
        current_time = datetime.now(timezone.utc).isoformat()
        
        for hypernode in hypernodes:
            try:
                # Generate consistent node ID
                node_id = self._generate_node_id(hypernode, customer_id)
                
                # Extract and validate node type
                node_type = hypernode.get('node_type', 'concept').lower()
                if node_type not in self.supported_node_types:
                    self.ctx.log_warning(f"Unknown node type '{node_type}', defaulting to 'concept'")
                    node_type = 'concept'
                
                # Extract confidence score
                confidence = float(hypernode.get('confidence', 0.5))
                confidence = max(0.0, min(1.0, confidence))  # Clamp to [0,1]
                
                # Build attributes from hypernode data
                attributes = self._build_node_attributes(hypernode)
                
                # Build metadata
                metadata = self._build_node_metadata(hypernode)
                
                extracted_node = ExtractedNode(
                    id=node_id,
                    customer_id=customer_id,
                    label=hypernode.get('content', '').strip() or f"Node_{node_id[:8]}",
                    node_type=node_type,
                    confidence=confidence,
                    attributes=attributes,
                    source_file=source_file,
                    created_at=current_time,
                    metadata=metadata
                )
                
                extracted_nodes.append(extracted_node)
                
            except Exception as e:
                sanitized_error = SensitiveDataSanitizer.sanitize_message(str(e))
                sanitized_hypernode = SensitiveDataSanitizer.sanitize_dict(hypernode)
                self.ctx.log_error(f"Error extracting node: {sanitized_error}", extra={'hypernode': sanitized_hypernode})
                continue
        
        return extracted_nodes
    
    def _extract_edges(self, hyperedges: List[Dict], customer_id: str, source_file: str) -> List[ExtractedEdge]:
        """Extract and validate edges from hyperedges"""
        extracted_edges = []
        current_time = datetime.now(timezone.utc).isoformat()
        
        for hyperedge in hyperedges:
            try:
                # Generate consistent edge ID
                edge_id = self._generate_edge_id(hyperedge, customer_id)
                
                # Extract source and target node IDs
                source_node_id = hyperedge.get('source_node_id', '')
                target_node_id = hyperedge.get('target_node_id', '')
                
                if not source_node_id or not target_node_id:
                    sanitized_hyperedge = SensitiveDataSanitizer.sanitize_dict(hyperedge)
                    self.ctx.log_warning("Edge missing source or target node ID", extra={'hyperedge': sanitized_hyperedge})
                    continue
                
                # Extract and validate edge type
                edge_type = hyperedge.get('edge_type', 'relates_to').lower()
                if edge_type not in self.supported_edge_types:
                    self.ctx.log_warning(f"Unknown edge type '{edge_type}', defaulting to 'relates_to'")
                    edge_type = 'relates_to'
                
                # Extract confidence as weight
                weight = float(hyperedge.get('confidence', 0.5))
                weight = max(0.0, min(1.0, weight))  # Clamp to [0,1]
                
                # Build attributes from hyperedge data
                attributes = self._build_edge_attributes(hyperedge)
                
                # Build metadata
                metadata = self._build_edge_metadata(hyperedge)
                
                extracted_edge = ExtractedEdge(
                    id=edge_id,
                    customer_id=customer_id,
                    source_node_id=source_node_id,
                    target_node_id=target_node_id,
                    relationship_type=edge_type,
                    weight=weight,
                    attributes=attributes,
                    source_file=source_file,
                    created_at=current_time,
                    metadata=metadata
                )
                
                extracted_edges.append(extracted_edge)
                
            except Exception as e:
                sanitized_error = SensitiveDataSanitizer.sanitize_message(str(e))
                sanitized_hyperedge = SensitiveDataSanitizer.sanitize_dict(hyperedge)
                self.ctx.log_error(f"Error extracting edge: {sanitized_error}", extra={'hyperedge': sanitized_hyperedge})
                continue
        
        return extracted_edges
    
    def _generate_node_id(self, hypernode: Dict, customer_id: str) -> str:
        """Generate consistent node ID based on content and customer"""
        content = hypernode.get('content', '')
        node_type = hypernode.get('node_type', 'concept')
        
        # Create hash from content, type, and customer for consistency
        hash_input = f"{customer_id}:{node_type}:{content}".encode('utf-8')
        hash_value = hashlib.sha256(hash_input).hexdigest()[:16]
        
        return f"node_{hash_value}"
    
    def _generate_edge_id(self, hyperedge: Dict, customer_id: str) -> str:
        """Generate consistent edge ID based on source, target, and type"""
        source_id = hyperedge.get('source_node_id', '')
        target_id = hyperedge.get('target_node_id', '')
        edge_type = hyperedge.get('edge_type', 'relates_to')
        
        # Create hash from source, target, type, and customer for consistency
        hash_input = f"{customer_id}:{source_id}:{target_id}:{edge_type}".encode('utf-8')
        hash_value = hashlib.sha256(hash_input).hexdigest()[:16]
        
        return f"edge_{hash_value}"
    
    def _build_node_attributes(self, hypernode: Dict) -> Dict[str, Any]:
        """Build node attributes from hypernode data"""
        attributes = {}
        
        # Add timestamp information
        if 'timestamp' in hypernode:
            attributes['original_timestamp'] = hypernode['timestamp']
        
        # Add source information
        if 'source' in hypernode:
            attributes['extraction_source'] = hypernode['source']
        
        # Add needs classification if available
        needs_classification = hypernode.get('needs_classification', {})
        if needs_classification:
            attributes['needs_scores'] = needs_classification
            # Find dominant need
            if needs_classification:
                dominant_need = max(needs_classification.items(), key=lambda x: float(x[1]))
                attributes['dominant_need'] = dominant_need[0]
                attributes['dominant_need_score'] = float(dominant_need[1])
        
        # Add domain-specific properties
        domain_props = hypernode.get('domain_specific_properties', {})
        if domain_props:
            attributes.update(domain_props)
        
        return attributes
    
    def _build_edge_attributes(self, hyperedge: Dict) -> Dict[str, Any]:
        """Build edge attributes from hyperedge data"""
        attributes = {}
        
        # Add timestamp information
        if 'timestamp' in hyperedge:
            attributes['original_timestamp'] = hyperedge['timestamp']
        
        # Add evidence if available
        evidence = hyperedge.get('evidence', [])
        if evidence:
            attributes['evidence'] = evidence
            attributes['evidence_count'] = len(evidence)
        
        # Add reasoning if available
        reasoning = hyperedge.get('reasoning', '')
        if reasoning:
            attributes['reasoning'] = reasoning
        
        return attributes
    
    def _build_node_metadata(self, hypernode: Dict) -> Dict[str, Any]:
        """Build node metadata from hypernode data"""
        metadata = {}
        
        # Add original hypernode metadata
        original_metadata = hypernode.get('metadata', {})
        if original_metadata:
            metadata['original_metadata'] = original_metadata
        
        # Add extraction metadata
        metadata['extraction_method'] = 'enhanced_hypergraph_v2'
        metadata['extraction_timestamp'] = datetime.now(timezone.utc).isoformat()
        
        return metadata
    
    def _build_edge_metadata(self, hyperedge: Dict) -> Dict[str, Any]:
        """Build edge metadata from hyperedge data"""
        metadata = {}
        
        # Add original hyperedge metadata
        original_metadata = hyperedge.get('metadata', {})
        if original_metadata:
            metadata['original_metadata'] = original_metadata
        
        # Add extraction metadata
        metadata['extraction_method'] = 'enhanced_hypergraph_v2'
        metadata['extraction_timestamp'] = datetime.now(timezone.utc).isoformat()
        
        return metadata

class GraphExtractionError(Exception):
    """Custom exception for graph extraction errors"""
    pass

class S3StorageError(Exception):
    """Custom exception for S3 storage errors"""
    pass

class S3GraphStorage:
    """Handles S3 storage for extracted graph data with retry logic and validation"""
    
    def __init__(self, bucket_name: Optional[str] = None, correlation_context: CorrelationContext = None):
        self.s3_client = boto3.client('s3')
        self.bucket_name = bucket_name or os.environ.get('CUSTOMER_GRAPHS_BUCKET', 'customer-graphs-dev')
        self.max_retries = 3
        self.base_delay = 1.0  # Base delay for exponential backoff
        self.ctx = correlation_context
        self.metrics = CloudWatchMetrics()
    
    def store_graph_data(self, extraction_result: ExtractionResult) -> str:
        """
        Store extracted graph data to S3 with customer-specific prefixes
        
        Args:
            extraction_result: Result from graph extraction
            
        Returns:
            S3 location prefix for stored files
        """
        storage_start_time = time.time()
        
        try:
            # Build S3 prefix for customer isolation
            s3_prefix = self._build_s3_prefix(
                extraction_result.customer_id, 
                extraction_result.extraction_id
            )
            
            if self.ctx:
                self.ctx.log_info(f"Storing graph data to S3 prefix: {s3_prefix}")
            
            # Store nodes file
            nodes_key = f"{s3_prefix}/nodes.json"
            self._store_json_with_retry(nodes_key, [asdict(node) for node in extraction_result.extracted_nodes])
            
            # Store edges file
            edges_key = f"{s3_prefix}/edges.json"
            self._store_json_with_retry(edges_key, [asdict(edge) for edge in extraction_result.extracted_edges])
            
            # Store metadata file
            metadata_key = f"{s3_prefix}/metadata.json"
            self._store_json_with_retry(metadata_key, extraction_result.extraction_metadata)
            
            # Create and store manifest file
            manifest = self._create_manifest(extraction_result, s3_prefix)
            manifest_key = f"{s3_prefix}/manifest.json"
            self._store_json_with_retry(manifest_key, manifest)
            
            # Update customer-level manifest
            self._update_customer_manifest(extraction_result.customer_id, extraction_result.extraction_id, s3_prefix)
            
            # Validate stored files
            self._validate_stored_files(s3_prefix, extraction_result)
            
            # Emit success metrics
            storage_duration = time.time() - storage_start_time
            self.metrics.emit_s3_operation_metrics('Upload', True, storage_duration, extraction_result.customer_id)
            
            if self.ctx:
                self.ctx.log_info(f"Successfully stored graph data to S3 in {storage_duration:.2f}s")
            
            return f"s3://{self.bucket_name}/{s3_prefix}"
            
        except Exception as e:
            storage_duration = time.time() - storage_start_time
            self.metrics.emit_s3_operation_metrics('Upload', False, storage_duration, extraction_result.customer_id)
            
            sanitized_error = SensitiveDataSanitizer.sanitize_message(str(e))
            if self.ctx:
                self.ctx.log_error(f"Failed to store graph data to S3: {sanitized_error}")
            
            raise S3StorageError(f"S3 storage failed: {sanitized_error}")
    
    def _build_s3_prefix(self, customer_id: str, extraction_id: str) -> str:
        """Build S3 prefix for customer data isolation"""
        # Sanitize customer_id for S3 key safety
        safe_customer_id = self._sanitize_s3_key_component(customer_id)
        safe_extraction_id = self._sanitize_s3_key_component(extraction_id)
        
        # Build hierarchical prefix: customer-graphs/{customer_id}/extractions/{extraction_id}
        return f"customer-graphs/{safe_customer_id}/extractions/{safe_extraction_id}"
    
    def _sanitize_s3_key_component(self, component: str) -> str:
        """Sanitize string for safe use in S3 keys"""
        # Replace unsafe characters with underscores
        import re
        sanitized = re.sub(r'[^a-zA-Z0-9\-_.]', '_', component)
        # Remove leading/trailing underscores and limit length
        sanitized = sanitized.strip('_')[:50]
        return sanitized or 'unknown'
    
    def _store_json_with_retry(self, s3_key: str, data: Any) -> None:
        """Store JSON data to S3 with exponential backoff retry logic"""
        json_data = json.dumps(data, indent=2, default=str)
        
        for attempt in range(self.max_retries):
            try:
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=s3_key,
                    Body=json_data,
                    ContentType='application/json',
                    ServerSideEncryption='AES256',
                    Metadata={
                        'extraction-timestamp': datetime.now(timezone.utc).isoformat(),
                        'data-type': 'customer-graph-data'
                    }
                )
                if self.ctx:
                    self.ctx.log_debug(f"Successfully stored {s3_key} on attempt {attempt + 1}")
                return
                
            except (ClientError, BotoCoreError) as e:
                if attempt == self.max_retries - 1:
                    raise S3StorageError(f"Failed to store {s3_key} after {self.max_retries} attempts: {str(e)}")
                
                # Exponential backoff
                delay = self.base_delay * (2 ** attempt)
                sanitized_error = SensitiveDataSanitizer.sanitize_message(str(e))
                if self.ctx:
                    self.ctx.log_warning(f"S3 upload attempt {attempt + 1} failed for {s3_key}, retrying in {delay}s: {sanitized_error}")
                time.sleep(delay)
    
    def _create_manifest(self, extraction_result: ExtractionResult, s3_prefix: str) -> Dict[str, Any]:
        """Create manifest file with processing metadata and file references"""
        return {
            'extraction_id': extraction_result.extraction_id,
            'customer_id': extraction_result.customer_id,
            'extraction_timestamp': datetime.now(timezone.utc).isoformat(),
            'files': {
                'nodes': f"{s3_prefix}/nodes.json",
                'edges': f"{s3_prefix}/edges.json",
                'metadata': f"{s3_prefix}/metadata.json"
            },
            'statistics': {
                'total_nodes': len(extraction_result.extracted_nodes),
                'total_edges': len(extraction_result.extracted_edges),
                'node_types': self._count_node_types(extraction_result.extracted_nodes),
                'edge_types': self._count_edge_types(extraction_result.extracted_edges)
            },
            'source_metadata': extraction_result.extraction_metadata,
            'storage_metadata': {
                'bucket': self.bucket_name,
                'prefix': s3_prefix,
                'encryption': 'AES256'
            }
        }
    
    def _count_node_types(self, nodes: List[ExtractedNode]) -> Dict[str, int]:
        """Count nodes by type for manifest statistics"""
        type_counts = {}
        for node in nodes:
            node_type = node.node_type
            type_counts[node_type] = type_counts.get(node_type, 0) + 1
        return type_counts
    
    def _count_edge_types(self, edges: List[ExtractedEdge]) -> Dict[str, int]:
        """Count edges by type for manifest statistics"""
        type_counts = {}
        for edge in edges:
            edge_type = edge.relationship_type
            type_counts[edge_type] = type_counts.get(edge_type, 0) + 1
        return type_counts
    
    def _update_customer_manifest(self, customer_id: str, extraction_id: str, s3_prefix: str) -> None:
        """Update customer-level manifest with new extraction"""
        try:
            safe_customer_id = self._sanitize_s3_key_component(customer_id)
            customer_manifest_key = f"customer-graphs/{safe_customer_id}/manifest.json"
            
            # Try to get existing manifest
            try:
                response = self.s3_client.get_object(Bucket=self.bucket_name, Key=customer_manifest_key)
                customer_manifest = json.loads(response['Body'].read())
            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchKey':
                    # Create new customer manifest
                    customer_manifest = {
                        'customer_id': customer_id,
                        'created_at': datetime.now(timezone.utc).isoformat(),
                        'extractions': []
                    }
                else:
                    raise
            
            # Add new extraction to manifest
            extraction_entry = {
                'extraction_id': extraction_id,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'prefix': s3_prefix
            }
            customer_manifest['extractions'].append(extraction_entry)
            customer_manifest['last_updated'] = datetime.now(timezone.utc).isoformat()
            
            # Store updated manifest
            self._store_json_with_retry(customer_manifest_key, customer_manifest)
            
        except Exception as e:
            # Log error but don't fail the entire operation
            sanitized_error = SensitiveDataSanitizer.sanitize_message(str(e))
            if self.ctx:
                self.ctx.log_error(f"Failed to update customer manifest: {sanitized_error}")
            else:
                logger.error(f"Failed to update customer manifest: {sanitized_error}")
    
    def _validate_stored_files(self, s3_prefix: str, extraction_result: ExtractionResult) -> None:
        """Validate that all files were stored correctly with integrity checks"""
        required_files = ['nodes.json', 'edges.json', 'metadata.json', 'manifest.json']
        
        for filename in required_files:
            s3_key = f"{s3_prefix}/{filename}"
            try:
                # Check if file exists and get metadata
                response = self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
                
                # Validate file size (should not be empty)
                content_length = response.get('ContentLength', 0)
                if content_length == 0:
                    raise S3StorageError(f"Stored file {s3_key} is empty")
                
                if self.ctx:
                    self.ctx.log_debug(f"Validated {s3_key}: {content_length} bytes")
                
            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchKey':
                    raise S3StorageError(f"Required file {s3_key} was not stored")
                else:
                    raise S3StorageError(f"Failed to validate {s3_key}: {str(e)}")
        
        # Additional integrity check: verify node and edge counts match
        try:
            nodes_response = self.s3_client.get_object(Bucket=self.bucket_name, Key=f"{s3_prefix}/nodes.json")
            stored_nodes = json.loads(nodes_response['Body'].read())
            
            edges_response = self.s3_client.get_object(Bucket=self.bucket_name, Key=f"{s3_prefix}/edges.json")
            stored_edges = json.loads(edges_response['Body'].read())
            
            if len(stored_nodes) != len(extraction_result.extracted_nodes):
                raise S3StorageError(f"Node count mismatch: expected {len(extraction_result.extracted_nodes)}, stored {len(stored_nodes)}")
            
            if len(stored_edges) != len(extraction_result.extracted_edges):
                raise S3StorageError(f"Edge count mismatch: expected {len(extraction_result.extracted_edges)}, stored {len(stored_edges)}")
            
            if self.ctx:
                self.ctx.log_info(f"File integrity validation passed for {s3_prefix}")
            
        except json.JSONDecodeError as e:
            sanitized_error = SensitiveDataSanitizer.sanitize_message(str(e))
            raise S3StorageError(f"Stored JSON files are corrupted: {sanitized_error}")
        except Exception as e:
            sanitized_error = SensitiveDataSanitizer.sanitize_message(str(e))
            if self.ctx:
                self.ctx.log_warning(f"Could not perform full integrity check: {sanitized_error}")
            else:
                logger.warning(f"Could not perform full integrity check: {sanitized_error}")

class GraphExtractor:
    """Main graph extraction orchestrator"""
    
    def __init__(self, correlation_context: CorrelationContext = None):
        self.ctx = correlation_context or CorrelationContext()
        self.parser = HypergraphParser(self.ctx)
        self.s3_storage = S3GraphStorage(correlation_context=self.ctx)
        self.metrics = CloudWatchMetrics()
    
    def extract_graph_data(self, event: Dict[str, Any]) -> ExtractionResult:
        """
        Extract graph data from hypergraph builder output
        
        Args:
            event: Lambda event containing hypergraph data
            
        Returns:
            ExtractionResult with extracted nodes and edges
        """
        try:
            # Extract required fields from event
            execution_id = event.get('execution_id', str(uuid.uuid4()))
            customer_id = self._extract_customer_id(event)
            source_file = self._extract_source_file(event)
            hypergraph_data = self._extract_hypergraph_data(event)
            
            self.ctx.log_info(f"Starting graph extraction for customer: {customer_id[:8]}...")
            
            # Validate inputs
            self._validate_inputs(customer_id, hypergraph_data)
            
            # Parse hypergraph data
            extracted_nodes, extracted_edges = self.parser.parse_hypergraph_output(
                hypergraph_data, customer_id, source_file
            )
            
            # Generate extraction ID
            extraction_id = f"extraction_{int(time.time())}_{execution_id[:8]}"
            
            # Build extraction metadata
            extraction_metadata = {
                'execution_id': execution_id,
                'extraction_timestamp': datetime.now(timezone.utc).isoformat(),
                'source_file': source_file,
                'nodes_extracted': len(extracted_nodes),
                'edges_extracted': len(extracted_edges),
                'hypergraph_metrics': hypergraph_data.get('graph_metrics', {}),
                'processing_metadata': hypergraph_data.get('processing_metadata', {}),
                'correlation_id': self.ctx.correlation_id
            }
            
            # Create extraction result
            extraction_result = ExtractionResult(
                extraction_id=extraction_id,
                customer_id=customer_id,
                extracted_nodes=extracted_nodes,
                extracted_edges=extracted_edges,
                s3_location="",  # Will be set by S3 storage
                extraction_metadata=extraction_metadata
            )
            
            # Store to S3
            s3_location = self.s3_storage.store_graph_data(extraction_result)
            extraction_result.s3_location = s3_location
            
            # Emit success metrics
            duration = self.ctx.get_duration()
            self.metrics.emit_extraction_success(customer_id, len(extracted_nodes), len(extracted_edges), duration)
            
            self.ctx.log_info(f"Graph extraction completed successfully in {duration:.2f}s")
            
            return extraction_result
            
        except Exception as e:
            # Categorize error and emit metrics
            error_category = ErrorCategorizer.categorize_error(e)
            error_info = ErrorCategorizer.get_error_info(error_category)
            duration = self.ctx.get_duration()
            
            self.metrics.emit_extraction_failure(customer_id if 'customer_id' in locals() else 'unknown', error_category, duration)
            
            sanitized_error = SensitiveDataSanitizer.sanitize_message(str(e))
            self.ctx.log_error(f"Graph extraction failed ({error_category}): {sanitized_error}")
            
            # Include error category in exception for better handling
            raise GraphExtractionError(f"Failed to extract graph data ({error_category}): {sanitized_error}")
    
    def _extract_customer_id(self, event: Dict[str, Any]) -> str:
        """Extract customer ID from event"""
        # Try different possible locations
        customer_id = (
            event.get('customer_id') or
            event.get('agent_spec', {}).get('processing_config', {}).get('customer_id') or
            event.get('agent_spec', {}).get('processing_config', {}).get('customer_folder', '').replace('/', '') or
            'unknown_customer'
        )
        
        if customer_id == 'unknown_customer':
            self.ctx.log_warning("Could not extract customer_id from event, using 'unknown_customer'")
        
        return customer_id
    
    def _extract_source_file(self, event: Dict[str, Any]) -> str:
        """Extract source file path from event"""
        return (
            event.get('source_file') or
            event.get('agent_spec', {}).get('processing_config', {}).get('file_path') or
            'unknown_file'
        )
    
    def _extract_hypergraph_data(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Extract hypergraph data from event with comprehensive parsing"""
        # Log the full event structure for debugging
        self.ctx.log_info(f"Event keys: {list(event.keys())}")
        
        # The hypergraph data comes from the Step Functions in the 'result' field
        # which contains the Lambda response from the hypergraph builder
        result = event.get('result', {})
        
        self.ctx.log_info(f"Result type: {type(result)}")
        if isinstance(result, dict):
            self.ctx.log_info(f"Result keys: {list(result.keys())}")
        
        # Try multiple parsing strategies
        hypergraph_data = self._try_parse_hypergraph_data(result)
        if hypergraph_data:
            return hypergraph_data
        
        # If result is a string, try to parse it
        if isinstance(result, str):
            try:
                result = json.loads(result)
                self.ctx.log_info(f"Parsed result keys: {list(result.keys()) if isinstance(result, dict) else 'not dict'}")
                hypergraph_data = self._try_parse_hypergraph_data(result)
                if hypergraph_data:
                    return hypergraph_data
            except json.JSONDecodeError:
                self.ctx.log_error(f"Failed to parse result as JSON: {result[:200]}...")
        
        # Fallback: check if hypergraph data is directly in the event
        if 'hypernodes' in event and 'hyperedges' in event:
            self.ctx.log_info(f"Found hypergraph data directly in event")
            return event
        
        # Log detailed structure for debugging
        self.ctx.log_error(f"Could not find hypergraph data anywhere")
        self.ctx.log_error(f"Event structure: {json.dumps(event, indent=2, default=str)[:2000]}...")
        
        # Log the result structure in detail
        if isinstance(result, dict):
            self.ctx.log_error(f"Result structure details:")
            for key, value in result.items():
                if isinstance(value, dict):
                    self.ctx.log_error(f"  {key}: dict with keys {list(value.keys())}")
                    if key == 'body' and isinstance(value, dict) and 'result' in value:
                        nested_result = value['result']
                        self.ctx.log_error(f"    body.result keys: {list(nested_result.keys()) if isinstance(nested_result, dict) else 'not dict'}")
                elif isinstance(value, str) and key == 'body':
                    try:
                        parsed_body = json.loads(value)
                        self.ctx.log_error(f"  {key}: parsed JSON with keys {list(parsed_body.keys()) if isinstance(parsed_body, dict) else 'not dict'}")
                        if isinstance(parsed_body, dict) and 'result' in parsed_body:
                            nested_result = parsed_body['result']
                            self.ctx.log_error(f"    parsed_body.result keys: {list(nested_result.keys()) if isinstance(nested_result, dict) else 'not dict'}")
                    except json.JSONDecodeError:
                        self.ctx.log_error(f"  {key}: string (length {len(value)}) - {value[:200]}...")
                else:
                    self.ctx.log_error(f"  {key}: {type(value)} - {str(value)[:100]}...")
        
        return {}
    
    def _try_parse_hypergraph_data(self, data: Any) -> Dict[str, Any]:
        """Try to parse hypergraph data from various possible structures"""
        if not isinstance(data, dict):
            return {}
        
        # Strategy 1: Direct hypernodes/hyperedges or nodes/edges in data
        if ('hypernodes' in data and 'hyperedges' in data) or ('nodes' in data and 'edges' in data):
            self.ctx.log_info(f"Found hypergraph data directly in data")
            return data
        
        # Strategy 2: Step Functions Lambda response with Payload
        if 'Payload' in data and isinstance(data['Payload'], dict):
            payload = data['Payload']
            self.ctx.log_info(f"Found Step Functions Payload format")
            
            if 'statusCode' in payload and 'body' in payload:
                self.ctx.log_info(f"Found Lambda response in Payload, parsing body")
                body = payload['body']
                
                # Parse body if it's a string
                if isinstance(body, str):
                    try:
                        body = json.loads(body)
                        self.ctx.log_info(f"Parsed body keys: {list(body.keys()) if isinstance(body, dict) else 'not dict'}")
                    except json.JSONDecodeError:
                        self.ctx.log_error(f"Failed to parse body as JSON: {body[:200]}...")
                        return {}
                
                if isinstance(body, dict):
                    # Check if hypergraph data is in body.result
                    if 'result' in body and isinstance(body['result'], dict):
                        nested_result = body['result']
                        self.ctx.log_info(f"Found nested result keys: {list(nested_result.keys())}")
                        if ('hypernodes' in nested_result and 'hyperedges' in nested_result) or ('nodes' in nested_result and 'edges' in nested_result):
                            self.ctx.log_info(f"Found hypergraph data in body.result")
                            return nested_result
                    
                    # Check if hypergraph data is directly in body
                    if ('hypernodes' in body and 'hyperedges' in body) or ('nodes' in body and 'edges' in body):
                        self.ctx.log_info(f"Found hypergraph data directly in body")
                        return body
        
        # Strategy 3: Direct Lambda response with statusCode and body
        if 'statusCode' in data and 'body' in data:
            self.ctx.log_info(f"Found Lambda response format, parsing body")
            body = data['body']
            
            # Parse body if it's a string
            if isinstance(body, str):
                try:
                    body = json.loads(body)
                    self.ctx.log_info(f"Parsed body keys: {list(body.keys()) if isinstance(body, dict) else 'not dict'}")
                except json.JSONDecodeError:
                    self.ctx.log_error(f"Failed to parse body as JSON: {body[:200]}...")
                    return {}
            
            if isinstance(body, dict):
                # Check if hypergraph data is in body.result
                if 'result' in body and isinstance(body['result'], dict):
                    nested_result = body['result']
                    self.ctx.log_info(f"Found nested result keys: {list(nested_result.keys())}")
                    if ('hypernodes' in nested_result and 'hyperedges' in nested_result) or ('nodes' in nested_result and 'edges' in nested_result):
                        self.ctx.log_info(f"Found hypergraph data in body.result")
                        return nested_result
                
                # Check if hypergraph data is directly in body
                if ('hypernodes' in body and 'hyperedges' in body) or ('nodes' in body and 'edges' in body):
                    self.ctx.log_info(f"Found hypergraph data directly in body")
                    return body
        
        # Strategy 4: Body field without statusCode
        elif 'body' in data:
            body = data['body']
            if isinstance(body, str):
                try:
                    body = json.loads(body)
                except json.JSONDecodeError:
                    self.ctx.log_error(f"Failed to parse body as JSON: {body[:200]}...")
                    return {}
            
            if isinstance(body, dict):
                # Check if hypergraph data is in body.result
                if 'result' in body and isinstance(body['result'], dict):
                    nested_result = body['result']
                    if 'hypernodes' in nested_result and 'hyperedges' in nested_result:
                        return nested_result
                
                # Check if hypergraph data is directly in body
                if 'hypernodes' in body and 'hyperedges' in body:
                    return body
        
        # Strategy 5: Result field
        elif 'result' in data and isinstance(data['result'], dict):
            nested_result = data['result']
            if 'hypernodes' in nested_result and 'hyperedges' in nested_result:
                self.ctx.log_info(f"Found hypergraph data in result field")
                return nested_result
        
        return {}
    
    def _validate_inputs(self, customer_id: str, hypergraph_data: Dict[str, Any]) -> None:
        """Validate extraction inputs"""
        if not customer_id or customer_id == 'unknown_customer':
            raise GraphExtractionError("Valid customer_id is required")
        
        if not hypergraph_data:
            raise GraphExtractionError("Hypergraph data is required")
        
        # Handle both hypernodes/hyperedges and nodes/edges formats
        has_hypernodes = 'hypernodes' in hypergraph_data or 'hyperedges' in hypergraph_data
        has_nodes = 'nodes' in hypergraph_data or 'edges' in hypergraph_data
        
        if not has_hypernodes and not has_nodes:
            raise GraphExtractionError("Hypergraph data must contain 'hypernodes'/'hyperedges' or 'nodes'/'edges'")

def lambda_handler(event, context):
    """AWS Lambda handler for graph extraction"""
    
    # Create correlation context for request tracking
    execution_id = event.get('execution_id', context.aws_request_id)
    correlation_context = CorrelationContext(execution_id[:8])
    
    try:
        correlation_context.log_info("Graph extraction Lambda started")
        
        # Sanitize event for logging (remove sensitive data)
        sanitized_event = SensitiveDataSanitizer.sanitize_dict(event)
        correlation_context.log_debug("Processing event", extra={'event_keys': list(event.keys())})
        
        # Create extractor with correlation context
        extractor = GraphExtractor(correlation_context)
        
        # Extract graph data
        result = extractor.extract_graph_data(event)
        
        # Convert to serializable format (sanitize sensitive data)
        response_data = {
            'extraction_id': result.extraction_id,
            'customer_id': result.customer_id,
            'extracted_nodes': [asdict(node) for node in result.extracted_nodes],
            'extracted_edges': [asdict(edge) for edge in result.extracted_edges],
            's3_location': result.s3_location,
            'extraction_metadata': SensitiveDataSanitizer.sanitize_dict(result.extraction_metadata)
        }
        
        correlation_context.log_info(f"Graph extraction completed successfully")
        correlation_context.log_info(f"Results: {len(result.extracted_nodes)} nodes, {len(result.extracted_edges)} edges")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'execution_id': execution_id,
                'agent_type': 'graph_extraction_agent',
                's3_location': result.s3_location,
                'result': {
                    's3_location': result.s3_location,
                    'extraction_id': result.extraction_id,
                    'customer_id': result.customer_id,
                    'nodes_extracted': len(result.extracted_nodes),
                    'edges_extracted': len(result.extracted_edges),
                    'extraction_metadata': SensitiveDataSanitizer.sanitize_dict(result.extraction_metadata)
                },
                'success': True,
                'correlation_id': correlation_context.correlation_id
            })
        }
        
    except GraphExtractionError as e:
        error_category = ErrorCategorizer.categorize_error(e)
        error_info = ErrorCategorizer.get_error_info(error_category)
        sanitized_error = SensitiveDataSanitizer.sanitize_message(str(e))
        
        correlation_context.log_error(f"Graph extraction error ({error_category}): {sanitized_error}")
        
        status_code = 400 if error_category in ['VALIDATION_ERROR', 'PARSING_ERROR'] else 500
        
        return {
            'statusCode': status_code,
            'body': json.dumps({
                'execution_id': execution_id,
                'agent_type': 'graph_extraction_agent',
                'error': sanitized_error,
                'error_category': error_category,
                'error_info': error_info,
                'success': False,
                'correlation_id': correlation_context.correlation_id
            })
        }
    
    except Exception as e:
        error_category = ErrorCategorizer.categorize_error(e)
        sanitized_error = SensitiveDataSanitizer.sanitize_message(str(e))
        
        correlation_context.log_error(f"Unexpected error in graph extraction: {sanitized_error}")
        correlation_context.log_error(f"Stack trace: {traceback.format_exc()}")
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'execution_id': execution_id,
                'agent_type': 'graph_extraction_agent',
                'error': f"Internal error: {sanitized_error}",
                'error_category': error_category,
                'success': False,
                'correlation_id': correlation_context.correlation_id
            })
        }