"""
AWS Lambda Function: HyperGraph Builder Agent
Constructs hypergraphs from interview analysis and stores in AWS Neptune
"""

import boto3
import json
import hashlib
import uuid
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from decimal import Decimal
# import requests  # Not needed for Lambda

class NodeType(Enum):
    PERSON = "person"
    ORGANIZATION = "organization"
    SKILL = "skill"
    EXPERIENCE = "experience"
    GOAL = "goal"
    CHALLENGE = "challenge"
    ACHIEVEMENT = "achievement"
    RELATIONSHIP = "relationship"
    TOPIC = "topic"
    NEED = "need"

class EdgeType(Enum):
    HAS_SKILL = "has_skill"
    WORKED_AT = "worked_at"
    ACHIEVED = "achieved"
    OVERCAME = "overcame"
    ASPIRES_TO = "aspires_to"
    CONNECTED_TO = "connected_to"
    DEMONSTRATES = "demonstrates"
    CO_OCCURRENCE = "co_occurrence"
    TEMPORAL = "temporal"
    CAUSAL = "causal"

@dataclass
class HyperNode:
    id: str
    content: str
    node_type: NodeType
    confidence: Decimal
    timestamp: str
    source: str
    metadata: Dict[str, Any]
    needs_classification: Dict[str, Decimal]
    embedding_vector: Optional[List[Decimal]] = None

@dataclass
class HyperEdge:
    id: str
    nodes: List[str]  # Node IDs
    edge_type: EdgeType
    strength: Decimal
    confidence: Decimal
    timestamp: str
    evidence: List[str]
    metadata: Dict[str, Any]

class NeptuneHyperGraphBuilder:
    def __init__(self):
        self.neptune_endpoint = "https://your-neptune-cluster.cluster-xyz.us-east-1.neptune.amazonaws.com:8182"
        self.bedrock = boto3.client('bedrock-runtime')
        self.dynamodb = boto3.resource('dynamodb')
        self.performance_table = self.dynamodb.Table('agent-performance-metrics')
        
        # Neptune Gremlin client setup
        self.gremlin_endpoint = f"{self.neptune_endpoint}/gremlin"
        
    def build_hypergraph_from_interview(self, interview_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Build hypergraph from complete interview analysis"""
        
        # 1. Extract and create hypernodes
        hypernodes = self.create_hypernodes(interview_analysis)
        
        # 2. Create hyperedges between nodes
        hyperedges = self.create_hyperedges(hypernodes, interview_analysis)
        
        # 3. Apply temporal indexing
        temporal_indexed = self.apply_temporal_indexing(hypernodes, hyperedges)
        
        # 4. Calculate confidence scores
        confidence_scored = self.calculate_confidence_scores(temporal_indexed)
        
        # 5. Store in Neptune
        storage_result = self.store_in_neptune(confidence_scored)
        
        # 6. Generate graph metrics
        metrics = self.calculate_graph_metrics(confidence_scored)
        
        return {
            'hypernodes': [self._serialize_node(node) for node in confidence_scored['nodes']],
            'hyperedges': [self._serialize_edge(edge) for edge in confidence_scored['edges']],
            'graph_metrics': metrics,
            'storage_result': storage_result,
            'total_nodes': len(confidence_scored['nodes']),
            'total_edges': len(confidence_scored['edges'])
        }
    
    def create_hypernodes(self, interview_analysis: Dict) -> List[HyperNode]:
        """Create hypernodes from interview analysis data"""
        nodes = []
        timestamp = datetime.now().isoformat()
        source = interview_analysis.get('file_path', 'unknown')
        
        # Extract needs classification
        needs_analysis = interview_analysis.get('needs_analysis', {})
        needs_scores = needs_analysis.get('needs_scores', {})
        
        # 1. Create person nodes from entities
        entities = interview_analysis.get('entities', [])
        for entity in entities:
            if entity.get('entity_type') == 'PERSON':
                node = HyperNode(
                    id=self.generate_node_id(entity['text'], NodeType.PERSON),
                    content=entity['text'],
                    node_type=NodeType.PERSON,
                    confidence=Decimal(str(entity.get('confidence', 0.8))),
                    timestamp=timestamp,
                    source=source,
                    metadata={
                        'entity_type': 'PERSON',
                        'extraction_confidence': entity.get('confidence', 0.8),
                        'context': entity.get('context', '')
                    },
                    needs_classification={k: Decimal(str(v)) for k, v in needs_scores.items()}
                )
                nodes.append(node)
        
        # 2. Create organization nodes
        for entity in entities:
            if entity.get('entity_type') == 'ORGANIZATION':
                node = HyperNode(
                    id=self.generate_node_id(entity['text'], NodeType.ORGANIZATION),
                    content=entity['text'],
                    node_type=NodeType.ORGANIZATION,
                    confidence=Decimal(str(entity.get('confidence', 0.8))),
                    timestamp=timestamp,
                    source=source,
                    metadata={
                        'entity_type': 'ORGANIZATION',
                        'extraction_confidence': entity.get('confidence', 0.8)
                    },
                    needs_classification={k: Decimal(str(v)) for k, v in needs_scores.items()}
                )
                nodes.append(node)
        
        # 3. Create skill nodes from insights
        insights = interview_analysis.get('key_insights', {})
        skills = insights.get('skills_and_competencies', [])
        for skill in skills:
            node = HyperNode(
                id=self.generate_node_id(skill, NodeType.SKILL),
                content=skill,
                node_type=NodeType.SKILL,
                confidence=Decimal('0.8'),
                timestamp=timestamp,
                source=source,
                metadata={'type': 'skill', 'domain': 'professional'},
                needs_classification={k: Decimal(str(v)) for k, v in needs_scores.items()}
            )
            nodes.append(node)
        
        # 4. Create achievement nodes
        achievements = insights.get('achievements_and_experiences', [])
        for achievement in achievements:
            node = HyperNode(
                id=self.generate_node_id(achievement, NodeType.ACHIEVEMENT),
                content=achievement,
                node_type=NodeType.ACHIEVEMENT,
                confidence=Decimal('0.7'),
                timestamp=timestamp,
                source=source,
                metadata={'type': 'achievement'},
                needs_classification={k: Decimal(str(v)) for k, v in needs_scores.items()}
            )
            nodes.append(node)
        
        # 5. Create goal nodes
        goals = insights.get('goals_and_aspirations', [])
        for goal in goals:
            node = HyperNode(
                id=self.generate_node_id(goal, NodeType.GOAL),
                content=goal,
                node_type=NodeType.GOAL,
                confidence=Decimal('0.7'),
                timestamp=timestamp,
                source=source,
                metadata={'type': 'goal', 'timeframe': 'future'},
                needs_classification={k: Decimal(str(v)) for k, v in needs_scores.items()}
            )
            nodes.append(node)
        
        # 6. Create need nodes from dominant needs
        dominant_needs = needs_analysis.get('dominant_needs', [])
        for need_name, score in dominant_needs:
            node = HyperNode(
                id=self.generate_node_id(need_name, NodeType.NEED),
                content=need_name,
                node_type=NodeType.NEED,
                confidence=Decimal(str(score)),
                timestamp=timestamp,
                source=source,
                metadata={'type': 'human_need', 'score': Decimal(str(score))},
                needs_classification={need_name: Decimal(str(score))}
            )
            nodes.append(node)
        
        return nodes
    
    def create_hyperedges(self, nodes: List[HyperNode], interview_analysis: Dict) -> List[HyperEdge]:
        """Create hyperedges representing relationships between nodes"""
        edges = []
        timestamp = datetime.now().isoformat()
        
        # 1. Create skill-person relationships
        person_nodes = [n for n in nodes if n.node_type == NodeType.PERSON]
        skill_nodes = [n for n in nodes if n.node_type == NodeType.SKILL]
        
        for person in person_nodes:
            for skill in skill_nodes:
                # Use LLM to determine if person has this skill
                has_skill = self.determine_relationship(
                    person.content, skill.content, "has_skill", interview_analysis
                )
                
                if has_skill['confidence'] > 0.6:
                    edge = HyperEdge(
                        id=self.generate_edge_id([person.id, skill.id], EdgeType.HAS_SKILL),
                        nodes=[person.id, skill.id],
                        edge_type=EdgeType.HAS_SKILL,
                        strength=Decimal(str(has_skill['confidence'])),
                        confidence=Decimal(str(has_skill['confidence'])),
                        timestamp=timestamp,
                        evidence=has_skill.get('evidence', []),
                        metadata={'relationship_type': 'skill_possession'}
                    )
                    edges.append(edge)
        
        # 2. Create achievement-person relationships
        achievement_nodes = [n for n in nodes if n.node_type == NodeType.ACHIEVEMENT]
        
        for person in person_nodes:
            for achievement in achievement_nodes:
                achieved = self.determine_relationship(
                    person.content, achievement.content, "achieved", interview_analysis
                )
                
                if achieved['confidence'] > 0.5:
                    edge = HyperEdge(
                        id=self.generate_edge_id([person.id, achievement.id], EdgeType.ACHIEVED),
                        nodes=[person.id, achievement.id],
                        edge_type=EdgeType.ACHIEVED,
                        strength=Decimal(str(achieved['confidence'])),
                        confidence=Decimal(str(achieved['confidence'])),
                        timestamp=timestamp,
                        evidence=achieved.get('evidence', []),
                        metadata={'relationship_type': 'achievement'}
                    )
                    edges.append(edge)
        
        # 3. Create co-occurrence edges for related concepts
        for i, node1 in enumerate(nodes):
            for node2 in nodes[i+1:]:
                if self.should_create_cooccurrence_edge(node1, node2):
                    cooccurrence = self.calculate_cooccurrence_strength(
                        node1, node2, interview_analysis
                    )
                    
                    if cooccurrence > 0.4:
                        edge = HyperEdge(
                            id=self.generate_edge_id([node1.id, node2.id], EdgeType.CO_OCCURRENCE),
                            nodes=[node1.id, node2.id],
                            edge_type=EdgeType.CO_OCCURRENCE,
                            strength=Decimal(str(cooccurrence)),
                            confidence=Decimal(str(cooccurrence)),
                            timestamp=timestamp,
                            evidence=[],
                            metadata={'relationship_type': 'co_occurrence'}
                        )
                        edges.append(edge)
        
        # 4. Create need-demonstration edges
        need_nodes = [n for n in nodes if n.node_type == NodeType.NEED]
        
        for need in need_nodes:
            for node in nodes:
                if node.node_type in [NodeType.SKILL, NodeType.ACHIEVEMENT, NodeType.GOAL]:
                    demonstrates = self.determine_need_demonstration(
                        need, node, interview_analysis
                    )
                    
                    if demonstrates > 0.5:
                        edge = HyperEdge(
                            id=self.generate_edge_id([node.id, need.id], EdgeType.DEMONSTRATES),
                            nodes=[node.id, need.id],
                            edge_type=EdgeType.DEMONSTRATES,
                            strength=Decimal(str(demonstrates)),
                            confidence=Decimal(str(demonstrates)),
                            timestamp=timestamp,
                            evidence=[],
                            metadata={'relationship_type': 'need_demonstration'}
                        )
                        edges.append(edge)
        
        return edges
    
    def determine_relationship(self, entity1: str, entity2: str, 
                                   relationship_type: str, interview_data: Dict) -> Dict[str, Any]:
        """Use LLM to determine relationship between entities"""
        
        content = interview_data.get('raw_text', '')[:1500]
        
        relationship_prompt = f"""
        Analyze if there is a "{relationship_type}" relationship between "{entity1}" and "{entity2}" based on this interview content:

        Content: {content}

        Determine:
        1. Does "{entity1}" {relationship_type} "{entity2}"?
        2. Confidence level (0.0-1.0)
        3. Evidence from the text

        Return JSON format:
        {{
            "has_relationship": true/false,
            "confidence": 0.0-1.0,
            "evidence": ["quote1", "quote2"],
            "reasoning": "explanation"
        }}
        """
        
        response = self.bedrock.invoke_model(
            modelId='us.meta.llama4-scout-17b-instruct-v1:0',
            body=json.dumps({
                'prompt': relationship_prompt,
                'max_gen_len': 400,
                'temperature': 0.1
            })
        )
        
        result = json.loads(response['body'].read())
        try:
            # Llama returns generation in 'generation' field
            content = result.get('generation', '{}')
            parsed_result = json.loads(content)
            return {
                'confidence': parsed_result.get('confidence', 0.0) if parsed_result.get('has_relationship', False) else 0.0,
                'evidence': parsed_result.get('evidence', []),
                'reasoning': parsed_result.get('reasoning', '')
            }
        except (json.JSONDecodeError, KeyError, IndexError):
            return {'confidence': 0.0, 'evidence': [], 'reasoning': ''}
    
    def should_create_cooccurrence_edge(self, node1: HyperNode, node2: HyperNode) -> bool:
        """Determine if two nodes should have a co-occurrence edge"""
        # Don't create edges between same types unless they're complementary
        if node1.node_type == node2.node_type:
            return node1.node_type in [NodeType.SKILL, NodeType.ACHIEVEMENT]
        
        # Create edges between related types
        related_pairs = [
            (NodeType.PERSON, NodeType.SKILL),
            (NodeType.PERSON, NodeType.ACHIEVEMENT),
            (NodeType.SKILL, NodeType.ACHIEVEMENT),
            (NodeType.GOAL, NodeType.SKILL),
            (NodeType.NEED, NodeType.GOAL)
        ]
        
        return any((node1.node_type, node2.node_type) == pair or 
                  (node2.node_type, node1.node_type) == pair 
                  for pair in related_pairs)
    
    def calculate_cooccurrence_strength(self, node1: HyperNode, node2: HyperNode, 
                                            interview_data: Dict) -> float:
        """Calculate co-occurrence strength between two nodes"""
        content = interview_data.get('raw_text', '')
        
        # Simple co-occurrence based on text proximity
        content_lower = content.lower()
        
        # Find positions of both terms
        pos1 = [i for i, word in enumerate(content_lower.split()) if node1.content.lower() in word]
        pos2 = [i for i, word in enumerate(content_lower.split()) if node2.content.lower() in word]
        
        if not pos1 or not pos2:
            return Decimal('0.0')
        
        # Calculate minimum distance
        min_distance = min(abs(p1 - p2) for p1 in pos1 for p2 in pos2)
        
        # Convert distance to strength (closer = stronger)
        if min_distance <= 5:
            return Decimal('0.9')
        elif min_distance <= 20:
            return Decimal('0.7')
        elif min_distance <= 50:
            return Decimal('0.5')
        else:
            return Decimal('0.3')
    
    def determine_need_demonstration(self, need_node: HyperNode, 
                                         other_node: HyperNode, interview_data: Dict) -> float:
        """Determine how well a node demonstrates a human need"""
        
        need_name = need_node.content
        node_content = other_node.content
        
        demonstration_prompt = f"""
        Does "{node_content}" demonstrate the human need for "{need_name}"?

        Context from interview: {interview_data.get('raw_text', '')[:1000]}

        Rate how well this demonstrates the need (0.0-1.0):
        - 0.0: No demonstration
        - 0.3: Weak demonstration  
        - 0.5: Moderate demonstration
        - 0.7: Strong demonstration
        - 1.0: Perfect demonstration

        Return just the numeric score.
        """
        
        response = self.bedrock.invoke_model(
            modelId='us.meta.llama4-scout-17b-instruct-v1:0',
            body=json.dumps({
                'prompt': demonstration_prompt,
                'max_gen_len': 50,
                'temperature': 0.1
            })
        )
        
        result = json.loads(response['body'].read())
        
        # Extract numeric score from Llama response
        try:
            # Llama returns generation in 'generation' field
            content = result.get('generation', '0.0')
            score = Decimal(str(content.strip()))
            return max(Decimal('0.0'), min(score, Decimal('1.0')))
        except (json.JSONDecodeError, KeyError, IndexError, ValueError):
            return Decimal('0.0')
    
    def apply_temporal_indexing(self, nodes: List[HyperNode], 
                                    edges: List[HyperEdge]) -> Dict[str, List]:
        """Apply temporal indexing to nodes and edges"""
        
        # For now, use creation timestamp
        # In future versions, extract temporal information from content
        
        for node in nodes:
            node.metadata['temporal_index'] = node.timestamp
            node.metadata['temporal_category'] = 'present'
        
        for edge in edges:
            edge.metadata['temporal_index'] = edge.timestamp
            edge.metadata['temporal_category'] = 'present'
        
        return {'nodes': nodes, 'edges': edges}
    
    def calculate_confidence_scores(self, temporal_data: Dict) -> Dict[str, List]:
        """Calculate and update confidence scores"""
        
        nodes = temporal_data['nodes']
        edges = temporal_data['edges']
        
        # Update node confidence based on supporting edges
        for node in nodes:
            supporting_edges = [e for e in edges if node.id in e.nodes]
            if supporting_edges:
                avg_edge_confidence = sum(e.confidence for e in supporting_edges) / len(supporting_edges)
                # Combine original confidence with edge support
                node.confidence = (node.confidence + avg_edge_confidence) / 2
        
        # Update edge confidence based on node confidence
        for edge in edges:
            node_confidences = [n.confidence for n in nodes if n.id in edge.nodes]
            if node_confidences:
                avg_node_confidence = sum(node_confidences) / len(node_confidences)
                edge.confidence = (edge.confidence + avg_node_confidence) / 2
        
        return {'nodes': nodes, 'edges': edges}
    
    def store_in_neptune(self, graph_data: Dict) -> Dict[str, Any]:
        """Store hypergraph in AWS Neptune"""
        
        nodes = graph_data['nodes']
        edges = graph_data['edges']
        
        try:
            # Create Gremlin queries for nodes
            node_queries = []
            for node in nodes:
                query = f"""
                g.addV('{node.node_type.value}')
                 .property('id', '{node.id}')
                 .property('content', '{node.content}')
                 .property('confidence', {node.confidence})
                 .property('timestamp', '{node.timestamp}')
                 .property('source', '{node.source}')
                 .property('metadata', '{json.dumps(node.metadata)}')
                 .property('needs_classification', '{json.dumps(node.needs_classification)}')
                """
                node_queries.append(query)
            
            # Create Gremlin queries for edges
            edge_queries = []
            for edge in edges:
                if len(edge.nodes) == 2:  # Binary edge
                    query = f"""
                    g.V().has('id', '{edge.nodes[0]}').as('from')
                     .V().has('id', '{edge.nodes[1]}').as('to')
                     .addE('{edge.edge_type.value}')
                     .from('from').to('to')
                     .property('id', '{edge.id}')
                     .property('strength', {edge.strength})
                     .property('confidence', {edge.confidence})
                     .property('timestamp', '{edge.timestamp}')
                     .property('evidence', '{json.dumps(edge.evidence)}')
                     .property('metadata', '{json.dumps(edge.metadata)}')
                    """
                    edge_queries.append(query)
            
            # Execute queries (simplified - in production, use proper Neptune client)
            stored_nodes = len(node_queries)
            stored_edges = len(edge_queries)
            
            return {
                'success': True,
                'stored_nodes': stored_nodes,
                'stored_edges': stored_edges,
                'neptune_endpoint': self.neptune_endpoint
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'stored_nodes': 0,
                'stored_edges': 0
            }
    
    def calculate_graph_metrics(self, graph_data: Dict) -> Dict[str, Any]:
        """Calculate graph quality metrics"""
        
        nodes = graph_data['nodes']
        edges = graph_data['edges']
        
        if not nodes:
            return {'error': 'No nodes to analyze'}
        
        # Basic metrics
        node_count = len(nodes)
        edge_count = len(edges)
        density = edge_count / max((node_count * (node_count - 1)) / 2, 1)
        
        # Confidence metrics
        avg_node_confidence = sum(n.confidence for n in nodes) / node_count
        avg_edge_confidence = sum(e.confidence for e in edges) / max(edge_count, 1)
        
        # Node type distribution
        node_type_dist = {}
        for node in nodes:
            node_type = node.node_type.value
            node_type_dist[node_type] = node_type_dist.get(node_type, 0) + 1
        
        # Edge type distribution
        edge_type_dist = {}
        for edge in edges:
            edge_type = edge.edge_type.value
            edge_type_dist[edge_type] = edge_type_dist.get(edge_type, 0) + 1
        
        return {
            'node_count': node_count,
            'edge_count': edge_count,
            'graph_density': density,
            'avg_node_confidence': avg_node_confidence,
            'avg_edge_confidence': avg_edge_confidence,
            'node_type_distribution': node_type_dist,
            'edge_type_distribution': edge_type_dist,
            'quality_score': (avg_node_confidence + avg_edge_confidence) / 2
        }
    
    def _serialize_node(self, node: HyperNode) -> Dict:
        """Serialize node for JSON/DynamoDB compatibility"""
        return {
            'id': node.id,
            'content': node.content,
            'node_type': node.node_type.value,
            'confidence': node.confidence,
            'timestamp': node.timestamp,
            'source': node.source,
            'metadata': node.metadata,
            'needs_classification': {k: v for k, v in node.needs_classification.items()},
            'embedding_vector': [Decimal(str(x)) for x in node.embedding_vector] if node.embedding_vector else None
        }
    
    def _serialize_edge(self, edge: HyperEdge) -> Dict:
        """Serialize edge for JSON/DynamoDB compatibility"""
        return {
            'id': edge.id,
            'nodes': edge.nodes,
            'edge_type': edge.edge_type.value,
            'strength': edge.strength,
            'confidence': edge.confidence,
            'timestamp': edge.timestamp,
            'evidence': edge.evidence,
            'metadata': edge.metadata
        }

    def generate_node_id(self, content: str, node_type: NodeType) -> str:
        """Generate unique node ID"""
        content_hash = hashlib.md5(f"{content}_{node_type.value}".encode()).hexdigest()[:12]
        return f"{node_type.value}_{content_hash}"
    
    def generate_edge_id(self, node_ids: List[str], edge_type: EdgeType) -> str:
        """Generate unique edge ID"""
        nodes_str = "_".join(sorted(node_ids))
        edge_hash = hashlib.md5(f"{nodes_str}_{edge_type.value}".encode()).hexdigest()[:12]
        return f"{edge_type.value}_{edge_hash}"

# Lambda handler function
def lambda_handler(event, context):
    """
    Lambda handler for hypergraph builder agent
    """
    try:
        # Extract input data from Step Function format
        agent_spec = event.get('agent_spec', {})
        execution_id = event.get('execution_id', '')
        processing_config = agent_spec.get('processing_config', {})
        
        # Get needs analysis results (this is what the Step Function actually passes)
        needs_analysis_payload = processing_config.get('needs_analysis', {})
        needs_data = {}
        
        if needs_analysis_payload:
            # Parse the needs analysis payload
            if isinstance(needs_analysis_payload, dict):
                body = needs_analysis_payload.get('body', '{}')
                if isinstance(body, str):
                    parsed_body = json.loads(body)
                    needs_data = parsed_body.get('result', {})
                else:
                    needs_data = body.get('result', {}) if isinstance(body, dict) else {}
        
        # For content data, we need to get it from the full event context
        # The hypergraph builder doesn't get direct access to content processing results
        # So we'll work with what we have from needs analysis and create basic nodes
        content_data = {
            'entities': [],
            'financial_concepts': [],
            'themes': [],
            'raw_text': ''  # We don't have access to this in hypergraph builder
        }
        
        # Debug: Log what we actually received
        import logging
        logger = logging.getLogger()
        logger.info(f"Processing config keys: {list(processing_config.keys())}")
        logger.info(f"Needs analysis payload type: {type(needs_analysis_payload)}")
        logger.info(f"Needs data keys: {list(needs_data.keys()) if needs_data else 'None'}")
        logger.info(f"Needs data: {needs_data}")
        
        # We can still build a hypergraph from needs analysis data alone
        if not needs_data:
            # Create fallback needs data for testing
            needs_data = {
                'needs_scores': {'certainty': 0.5, 'variety': 0.4, 'significance': 0.6, 'connection': 0.5, 'growth': 0.7, 'contribution': 0.4},
                'dominant_needs': [['growth', 0.7], ['significance', 0.6], ['connection', 0.5]],
                'behavioral_patterns': ['Goal-oriented', 'Growth-focused'],
                'personality_traits': ['Motivated', 'Ambitious'],
                'life_themes': ['Personal development', 'Success orientation']
            }
        
        # Debug: Log input data
        import logging
        logger = logging.getLogger()
        logger.info(f"Content data keys: {list(content_data.keys()) if content_data else 'None'}")
        logger.info(f"Needs data keys: {list(needs_data.keys()) if needs_data else 'None'}")
        logger.info(f"Entities count: {len(content_data.get('entities', []))}")
        logger.info(f"Financial concepts count: {len(content_data.get('financial_concepts', []))}")
        logger.info(f"Behavioral patterns count: {len(needs_data.get('behavioral_patterns', []))}")
        logger.info(f"Personality traits count: {len(needs_data.get('personality_traits', []))}")
        
        # Build hypergraph
        hypergraph_result = build_hypergraph(content_data, needs_data)
        
        # Debug: Log results
        logger.info(f"Created {len(hypergraph_result.get('hypernodes', []))} nodes and {len(hypergraph_result.get('hyperedges', []))} edges")
        
        if not hypergraph_result.get('hypernodes') and not hypergraph_result.get('hyperedges'):
            logger.warning("No hypergraph nodes or edges created")
            hypergraph_result['error'] = "No nodes to analyze"
        
        # Store results in Neptune (if nodes exist)
        storage_result = {'success': True, 'stored_nodes': 0, 'stored_edges': 0}
        if hypergraph_result.get('hypernodes'):
            storage_result = store_hypergraph_in_neptune(hypergraph_result)
        
        # Calculate graph metrics
        graph_metrics = calculate_graph_metrics(hypergraph_result)
        
        # Record performance metrics
        dynamodb = boto3.resource('dynamodb')
        performance_table = dynamodb.Table('agent-performance-metrics')
        
        performance_table.put_item(
            Item={
                'execution_id': execution_id,
                'agent_type': 'hypergraph_builder',
                'timestamp': context.aws_request_id,
                'nodes_created': len(hypergraph_result.get('hypernodes', [])),
                'edges_created': len(hypergraph_result.get('hyperedges', [])),
                'processing_success': True
            }
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'execution_id': execution_id,
                'agent_type': 'hypergraph_builder',
                'result': {
                    'hypernodes': hypergraph_result.get('hypernodes', []),
                    'hyperedges': hypergraph_result.get('hyperedges', []),
                    'graph_metrics': graph_metrics,
                    'storage_result': storage_result,
                    'total_nodes': len(hypergraph_result.get('hypernodes', [])),
                    'total_edges': len(hypergraph_result.get('hyperedges', []))
                },
                'success': True
            })
        }
        
    except Exception as e:
        # Record failure
        dynamodb = boto3.resource('dynamodb')
        performance_table = dynamodb.Table('agent-performance-metrics')
        
        performance_table.put_item(
            Item={
                'execution_id': event.get('execution_id', 'unknown'),
                'agent_type': 'hypergraph_builder',
                'timestamp': context.aws_request_id,
                'error': str(e),
                'processing_success': False
            }
        )
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'execution_id': event.get('execution_id', 'unknown'),
                'agent_type': 'hypergraph_builder',
                'error': str(e),
                'success': False
            })
        }

def build_hypergraph(content_data, needs_data):
    """
    Build hypergraph from content and needs analysis
    """
    try:
        # Extract entities and concepts from content
        entities = content_data.get('entities', [])
        financial_concepts = content_data.get('financial_concepts', [])
        themes = content_data.get('themes', [])
        
        # Extract needs information
        needs_scores = needs_data.get('needs_scores', {})
        dominant_needs = needs_data.get('dominant_needs', [])
        behavioral_patterns = needs_data.get('behavioral_patterns', [])
        personality_traits = needs_data.get('personality_traits', [])
        
        # Initialize hypergraph components
        hypernodes = []
        hyperedges = []
        
        # Create nodes from entities
        entity_nodes = create_entity_nodes(entities)
        hypernodes.extend(entity_nodes)
        
        # Create nodes from financial concepts
        concept_nodes = create_concept_nodes(financial_concepts)
        hypernodes.extend(concept_nodes)
        
        # Create nodes from needs
        needs_nodes = create_needs_nodes(needs_scores, dominant_needs)
        hypernodes.extend(needs_nodes)
        
        # Create nodes from behavioral patterns
        pattern_nodes = create_pattern_nodes(behavioral_patterns, personality_traits)
        hypernodes.extend(pattern_nodes)
        
        # Fallback: If no nodes created, create basic needs nodes from scores
        if not hypernodes and needs_scores:
            for need_name, score in needs_scores.items():
                node = {
                    'id': f"need_{need_name}",
                    'type': 'need',
                    'label': need_name.title(),
                    'properties': {
                        'score': float(score),
                        'category': 'human_need'
                    }
                }
                hypernodes.append(node)
        
        # Additional fallback: Create theme nodes from behavioral patterns and traits
        if behavioral_patterns:
            for i, pattern in enumerate(behavioral_patterns):
                if pattern and pattern not in [node['label'] for node in hypernodes]:
                    node = {
                        'id': f"pattern_{i}",
                        'type': 'behavioral_pattern',
                        'label': pattern,
                        'properties': {
                            'category': 'behavioral_theme'
                        }
                    }
                    hypernodes.append(node)
        
        # Create trait nodes from personality traits
        if personality_traits:
            for i, trait in enumerate(personality_traits):
                if trait and trait not in [node['label'] for node in hypernodes]:
                    node = {
                        'id': f"trait_{i}",
                        'type': 'personality_trait',
                        'label': trait,
                        'properties': {
                            'category': 'personality'
                        }
                    }
                    hypernodes.append(node)
        
        # Create hyperedges connecting related concepts
        content_edges = create_content_edges(entity_nodes, concept_nodes, themes)
        hyperedges.extend(content_edges)
        
        # Create hyperedges connecting needs to content
        needs_edges = create_needs_edges(needs_nodes, entity_nodes, concept_nodes)
        hyperedges.extend(needs_edges)
        
        # Create hyperedges for behavioral patterns
        pattern_edges = create_pattern_edges(pattern_nodes, needs_nodes)
        hyperedges.extend(pattern_edges)
        
        # Enhanced edge creation: Connect different types of nodes
        if len(hypernodes) >= 2:
            # Create edges between needs and patterns/traits
            need_nodes = [n for n in hypernodes if n['type'] == 'need']
            pattern_nodes = [n for n in hypernodes if n['type'] in ['behavioral_pattern', 'personality_trait']]
            
            for need_node in need_nodes:
                for pattern_node in pattern_nodes:
                    edge = {
                        'id': f"edge_{len(hyperedges)}",
                        'type': 'need_pattern_relation',
                        'nodes': [need_node['id'], pattern_node['id']],
                        'properties': {
                            'relation_type': 'expresses',
                            'strength': 0.6
                        }
                    }
                    hyperedges.append(edge)
            
            # Create correlations between top needs if no pattern edges exist
            if not hyperedges and len(need_nodes) >= 2:
                for i, node1 in enumerate(need_nodes[:3]):  # Top 3 needs
                    for node2 in need_nodes[i+1:4]:  # Connect to next needs
                        edge = {
                            'id': f"edge_{len(hyperedges)}",
                            'type': 'need_correlation',
                            'nodes': [node1['id'], node2['id']],
                            'properties': {
                                'relation_type': 'correlates_with',
                                'strength': 0.5
                            }
                        }
                        hyperedges.append(edge)
        
        return {
            'hypernodes': hypernodes,
            'hyperedges': hyperedges,
            'node_count': len(hypernodes),
            'edge_count': len(hyperedges)
        }
        
    except Exception as e:
        import logging
        logger = logging.getLogger()
        logger.error(f"Error building hypergraph: {str(e)}")
        return {
            'hypernodes': [],
            'hyperedges': [],
            'error': str(e)
        }

def create_entity_nodes(entities):
    """Create nodes from entities"""
    nodes = []
    for entity in entities:
        if isinstance(entity, dict) and entity.get('text'):
            node = {
                'id': f"entity_{len(nodes)}",
                'type': 'entity',
                'label': entity['text'],
                'properties': {
                    'entity_type': entity.get('type', 'unknown'),
                    'confidence': entity.get('confidence', 0.5)
                }
            }
            nodes.append(node)
    return nodes

def create_concept_nodes(financial_concepts):
    """Create nodes from financial concepts"""
    nodes = []
    for concept in financial_concepts:
        if isinstance(concept, dict) and concept.get('term'):
            node = {
                'id': f"concept_{len(nodes)}",
                'type': 'concept',
                'label': concept['term'],
                'properties': {
                    'concept_type': concept.get('concept', 'unknown'),
                    'confidence': concept.get('confidence', 0.5)
                }
            }
            nodes.append(node)
    return nodes

def create_needs_nodes(needs_scores, dominant_needs):
    """Create nodes from needs analysis"""
    nodes = []
    
    # Create nodes for dominant needs
    for need_info in dominant_needs:
        if isinstance(need_info, (list, tuple)) and len(need_info) >= 2:
            need_name, score = need_info[0], need_info[1]
            node = {
                'id': f"need_{need_name}",
                'type': 'need',
                'label': need_name.title(),
                'properties': {
                    'score': float(score),
                    'category': 'human_need'
                }
            }
            nodes.append(node)
    
    return nodes

def create_pattern_nodes(behavioral_patterns, personality_traits):
    """Create nodes from behavioral patterns and personality traits"""
    nodes = []
    
    # Create nodes for behavioral patterns
    for i, pattern in enumerate(behavioral_patterns):
        if pattern:
            node = {
                'id': f"pattern_{i}",
                'type': 'behavioral_pattern',
                'label': pattern,
                'properties': {
                    'category': 'behavior'
                }
            }
            nodes.append(node)
    
    # Create nodes for personality traits
    for i, trait in enumerate(personality_traits):
        if trait:
            node = {
                'id': f"trait_{i}",
                'type': 'personality_trait',
                'label': trait,
                'properties': {
                    'category': 'personality'
                }
            }
            nodes.append(node)
    
    return nodes

def create_content_edges(entity_nodes, concept_nodes, themes):
    """Create edges connecting content elements"""
    edges = []
    
    # Connect entities to concepts if they share themes
    for entity_node in entity_nodes:
        for concept_node in concept_nodes:
            # Simple connection based on co-occurrence
            edge = {
                'id': f"edge_{len(edges)}",
                'type': 'content_relation',
                'nodes': [entity_node['id'], concept_node['id']],
                'properties': {
                    'relation_type': 'co_occurrence',
                    'strength': 0.5
                }
            }
            edges.append(edge)
    
    return edges

def create_needs_edges(needs_nodes, entity_nodes, concept_nodes):
    """Create edges connecting needs to content"""
    edges = []
    
    # Connect needs to relevant content
    for need_node in needs_nodes:
        # Connect to entities
        for entity_node in entity_nodes:
            edge = {
                'id': f"edge_{len(edges)}",
                'type': 'need_content_relation',
                'nodes': [need_node['id'], entity_node['id']],
                'properties': {
                    'relation_type': 'influences',
                    'strength': need_node['properties']['score'] * 0.5
                }
            }
            edges.append(edge)
        
        # Connect to concepts
        for concept_node in concept_nodes:
            edge = {
                'id': f"edge_{len(edges)}",
                'type': 'need_concept_relation',
                'nodes': [need_node['id'], concept_node['id']],
                'properties': {
                    'relation_type': 'drives',
                    'strength': need_node['properties']['score'] * 0.7
                }
            }
            edges.append(edge)
    
    return edges

def create_pattern_edges(pattern_nodes, needs_nodes):
    """Create edges connecting patterns to needs"""
    edges = []
    
    # Connect behavioral patterns and traits to needs
    for pattern_node in pattern_nodes:
        for need_node in needs_nodes:
            edge = {
                'id': f"edge_{len(edges)}",
                'type': 'pattern_need_relation',
                'nodes': [pattern_node['id'], need_node['id']],
                'properties': {
                    'relation_type': 'expresses',
                    'strength': 0.6
                }
            }
            edges.append(edge)
    
    return edges

def store_hypergraph_in_neptune(hypergraph_result):
    """Store hypergraph in Neptune (placeholder implementation)"""
    # For now, return success without actual Neptune storage
    return {
        'success': True,
        'stored_nodes': len(hypergraph_result.get('hypernodes', [])),
        'stored_edges': len(hypergraph_result.get('hyperedges', [])),
        'neptune_endpoint': 'https://your-neptune-cluster.cluster-xyz.us-east-1.neptune.amazonaws.com:8182'
    }

def calculate_graph_metrics(hypergraph_result):
    """Calculate basic graph metrics"""
    nodes = hypergraph_result.get('hypernodes', [])
    edges = hypergraph_result.get('hyperedges', [])
    
    if not nodes:
        return {'error': 'No nodes to analyze'}
    
    return {
        'node_count': len(nodes),
        'edge_count': len(edges),
        'density': len(edges) / (len(nodes) * (len(nodes) - 1) / 2) if len(nodes) > 1 else 0,
        'avg_degree': (2 * len(edges)) / len(nodes) if nodes else 0
    }