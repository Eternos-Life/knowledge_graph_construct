"""
Enhanced Hypergraph Builder Agent V2 - Cleaner Entity and Relationship Extraction
Focuses on extracting high-quality entities and relationships from file analysis and needs analysis
"""

import boto3
import json
import os
import re
import hashlib
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

class NodeType(Enum):
    PERSON = "person"
    ORGANIZATION = "organization"
    CONCEPT = "concept"
    SKILL = "skill"
    NEED = "need"
    BEHAVIORAL_PATTERN = "behavioral_pattern"
    PERSONALITY_TRAIT = "personality_trait"
    FINANCIAL_INSTRUMENT = "financial_instrument"
    BUSINESS_CONCEPT = "business_concept"
    TOPIC = "topic"

class EdgeType(Enum):
    DEMONSTRATES = "demonstrates"
    RELATES_TO = "relates_to"
    INFLUENCES = "influences"
    REQUIRES = "requires"
    ENABLES = "enables"
    PART_OF = "part_of"
    SIMILAR_TO = "similar_to"
    WORKS_WITH = "works_with"
    SPECIALIZES_IN = "specializes_in"
    # Interview-specific relationships
    INTERVIEWS = "interviews"
    DISCUSSES = "discusses"
    AFFILIATED_WITH = "affiliated_with"
    USES = "uses"

@dataclass
class CleanEntity:
    """Clean, well-structured entity with proper classification"""
    text: str
    entity_type: NodeType
    confidence: float
    context: str
    source: str  # 'file_analysis' or 'needs_analysis'
    properties: Dict[str, Any]
    domain_relevance: float = 0.8

@dataclass
class CleanRelationship:
    """Clean, meaningful relationship between entities"""
    source_entity: str
    target_entity: str
    relationship_type: EdgeType
    confidence: float
    evidence: List[str]
    reasoning: str
    source: str  # Where this relationship was detected

@dataclass
class EnhancedHyperNode:
    id: str
    content: str
    node_type: NodeType
    confidence: Decimal
    timestamp: str
    source: str
    metadata: Dict[str, Any]
    needs_classification: Dict[str, Decimal]
    domain_specific_properties: Dict[str, Any]

@dataclass
class EnhancedHyperEdge:
    id: str
    source_node_id: str
    target_node_id: str
    edge_type: EdgeType
    confidence: Decimal
    timestamp: str
    metadata: Dict[str, Any]
    evidence: List[str]
    reasoning: str

class CleanEntityExtractor:
    """Extracts clean, well-classified entities from analysis data"""
    
    def __init__(self, bedrock_client):
        self.bedrock = bedrock_client
    
    def extract_entities_from_file_analysis(self, file_analysis: Dict) -> List[CleanEntity]:
        """Extract clean entities from file analysis output"""
        entities = []
        
        # Check if this is an interview format (dialog-based)
        file_path = file_analysis.get('file_path', '')
        is_interview = self._is_interview_format(file_analysis, file_path)
        
        if is_interview:
            # Interview-specific entity extraction
            interview_entities = self._extract_interview_entities(file_analysis)
            entities.extend(interview_entities)
        else:
            # Standard single-person analysis
            # 1. Extract person entities (customer name, mentioned people)
            person_entities = self._extract_person_entities(file_analysis)
            entities.extend(person_entities)
            
            # 2. Extract skill entities from insights
            skill_entities = self._extract_skill_entities(file_analysis)
            entities.extend(skill_entities)
            
            # 3. Extract concept entities from themes and insights
            concept_entities = self._extract_concept_entities(file_analysis)
            entities.extend(concept_entities)
            
            # 4. Extract organization entities
            org_entities = self._extract_organization_entities(file_analysis)
            entities.extend(org_entities)
        
        # 5. Use LLM for additional entity extraction from raw text (both formats)
        llm_entities = self._extract_entities_with_llm(file_analysis)
        entities.extend(llm_entities)
        
        return self._deduplicate_entities(entities)
    
    def extract_entities_from_needs_analysis(self, needs_analysis: Dict) -> List[CleanEntity]:
        """Extract clean entities from needs analysis output"""
        entities = []
        
        # 1. Extract behavioral pattern entities
        behavioral_entities = self._extract_behavioral_pattern_entities(needs_analysis)
        entities.extend(behavioral_entities)
        
        # 2. Extract personality trait entities
        trait_entities = self._extract_personality_trait_entities(needs_analysis)
        entities.extend(trait_entities)
        
        # 3. Extract need entities (only significant ones)
        need_entities = self._extract_need_entities(needs_analysis)
        entities.extend(need_entities)
        
        # 4. Extract life theme entities
        theme_entities = self._extract_life_theme_entities(needs_analysis)
        entities.extend(theme_entities)
        
        return self._deduplicate_entities(entities)
    
    def _extract_person_entities(self, file_analysis: Dict) -> List[CleanEntity]:
        """Extract person entities with high confidence"""
        entities = []
        
        # Customer name from metadata
        customer_name = file_analysis.get('customer_name', '')
        if customer_name and len(customer_name.split()) <= 3:  # Reasonable name length
            entities.append(CleanEntity(
                text=customer_name,
                entity_type=NodeType.PERSON,
                confidence=0.95,
                context="Primary customer/subject",
                source="file_analysis",
                properties={"role": "customer", "primary": True},
                domain_relevance=1.0
            ))
        
        # Extract people from entities if available
        existing_entities = file_analysis.get('entities', [])
        for entity in existing_entities:
            if entity.get('type') == 'PERSON' and entity.get('confidence', 0) > 0.7:
                entities.append(CleanEntity(
                    text=entity['text'],
                    entity_type=NodeType.PERSON,
                    confidence=entity['confidence'],
                    context=entity.get('context', 'Mentioned person'),
                    source="file_analysis",
                    properties={"role": "mentioned"},
                    domain_relevance=0.7
                ))
        
        return entities
    
    def _extract_skill_entities(self, file_analysis: Dict) -> List[CleanEntity]:
        """Extract skill entities from insights"""
        entities = []
        insights = file_analysis.get('key_insights', {})
        
        skills = insights.get('skills_and_competencies', [])
        for skill in skills[:5]:  # Limit to top 5 skills
            if isinstance(skill, str) and len(skill.strip()) > 0:
                # Clean up skill text
                clean_skill = self._clean_entity_text(skill)
                if clean_skill:
                    entities.append(CleanEntity(
                        text=clean_skill,
                        entity_type=NodeType.SKILL,
                        confidence=0.8,
                        context="Professional competency",
                        source="file_analysis",
                        properties={"category": "professional", "domain": "expertise"},
                        domain_relevance=0.9
                    ))
        
        return entities
    
    def _extract_concept_entities(self, file_analysis: Dict) -> List[CleanEntity]:
        """Extract concept entities from themes and insights"""
        entities = []
        insights = file_analysis.get('key_insights', {})
        
        # Extract from main themes
        themes = insights.get('main_themes', [])
        for theme in themes[:3]:  # Limit to top 3 themes
            if isinstance(theme, str) and len(theme.strip()) > 0:
                clean_theme = self._clean_entity_text(theme)
                if clean_theme:
                    entities.append(CleanEntity(
                        text=clean_theme,
                        entity_type=NodeType.CONCEPT,
                        confidence=0.7,
                        context="Main discussion theme",
                        source="file_analysis",
                        properties={"category": "theme", "domain": "content"},
                        domain_relevance=0.8
                    ))
        
        # Extract from goals and aspirations
        goals = insights.get('goals_and_aspirations', [])
        for goal in goals[:3]:  # Limit to top 3 goals
            if isinstance(goal, str) and len(goal.strip()) > 0:
                clean_goal = self._clean_entity_text(goal)
                if clean_goal:
                    entities.append(CleanEntity(
                        text=clean_goal,
                        entity_type=NodeType.CONCEPT,
                        confidence=0.6,
                        context="Future aspiration or goal",
                        source="file_analysis",
                        properties={"category": "goal", "temporal": "future"},
                        domain_relevance=0.7
                    ))
        
        return entities
    
    def _is_interview_format(self, file_analysis: Dict, file_path: str) -> bool:
        """Determine if this is an interview format file"""
        # Check file path indicators
        interview_indicators = ['interview', 'transcript', 'dialog', 'conversation']
        file_path_lower = file_path.lower()
        
        if any(indicator in file_path_lower for indicator in interview_indicators):
            return True
        
        # Check content indicators (if raw text available)
        raw_text = file_analysis.get('raw_text', '')
        if raw_text:
            # Look for dialog patterns
            dialog_patterns = ['interviewer:', 'interviewee:', 'q:', 'a:', 'host:', 'guest:']
            text_lower = raw_text.lower()
            if any(pattern in text_lower for pattern in dialog_patterns):
                return True
        
        return False
    
    def _extract_interview_entities(self, file_analysis: Dict) -> List[CleanEntity]:
        """Extract entities specifically from interview/dialog format"""
        entities = []
        
        # 1. Extract interview participants
        participant_entities = self._extract_interview_participants(file_analysis)
        entities.extend(participant_entities)
        
        # 2. Extract discussed topics
        topic_entities = self._extract_interview_topics(file_analysis)
        entities.extend(topic_entities)
        
        # 3. Extract mentioned organizations/companies
        org_entities = self._extract_interview_organizations(file_analysis)
        entities.extend(org_entities)
        
        # 4. Extract mentioned people (beyond participants)
        mentioned_people = self._extract_mentioned_people(file_analysis)
        entities.extend(mentioned_people)
        
        # 5. Extract technologies/products discussed
        tech_entities = self._extract_interview_technologies(file_analysis)
        entities.extend(tech_entities)
        
        return entities
    
    def _extract_interview_participants(self, file_analysis: Dict) -> List[CleanEntity]:
        """Extract interviewer and interviewee entities"""
        entities = []
        
        # Primary participant (customer/interviewee)
        customer_name = file_analysis.get('customer_name', '')
        if customer_name:
            entities.append(CleanEntity(
                text=customer_name,
                entity_type=NodeType.PERSON,
                confidence=0.95,
                context="Interview participant (interviewee)",
                source="file_analysis",
                properties={"role": "interviewee", "primary": True},
                domain_relevance=1.0
            ))
        
        # Look for interviewer mentions in existing entities
        existing_entities = file_analysis.get('entities', [])
        for entity in existing_entities:
            if entity.get('type') == 'PERSON' and entity.get('confidence', 0) > 0.7:
                person_name = entity['text']
                if person_name != customer_name:  # Not the main customer
                    # Determine role based on context
                    context = entity.get('context', '').lower()
                    role = "interviewer" if any(word in context for word in ['host', 'interviewer', 'anchor']) else "mentioned_person"
                    
                    entities.append(CleanEntity(
                        text=person_name,
                        entity_type=NodeType.PERSON,
                        confidence=entity['confidence'],
                        context=f"Interview participant ({role})",
                        source="file_analysis",
                        properties={"role": role},
                        domain_relevance=0.8
                    ))
        
        return entities
    
    def _extract_interview_topics(self, file_analysis: Dict) -> List[CleanEntity]:
        """Extract topics discussed in the interview"""
        entities = []
        
        # Extract from key insights
        insights = file_analysis.get('key_insights', {})
        
        # Main themes become topic entities
        themes = insights.get('main_themes', [])
        for theme in themes[:5]:  # More topics for interviews
            if isinstance(theme, str) and len(theme.strip()) > 0:
                clean_theme = self._clean_entity_text(theme)
                if clean_theme:
                    entities.append(CleanEntity(
                        text=clean_theme,
                        entity_type=NodeType.CONCEPT,
                        confidence=0.8,
                        context="Interview discussion topic",
                        source="file_analysis",
                        properties={"category": "topic", "format": "interview"},
                        domain_relevance=0.9
                    ))
        
        return entities
    
    def _extract_interview_organizations(self, file_analysis: Dict) -> List[CleanEntity]:
        """Extract organizations mentioned in interview"""
        entities = []
        existing_entities = file_analysis.get('entities', [])
        
        for entity in existing_entities:
            if entity.get('type') == 'ORGANIZATION' and entity.get('confidence', 0) > 0.6:
                entities.append(CleanEntity(
                    text=entity['text'],
                    entity_type=NodeType.ORGANIZATION,
                    confidence=entity['confidence'],
                    context="Organization discussed in interview",
                    source="file_analysis",
                    properties={"role": "discussed_organization", "format": "interview"},
                    domain_relevance=0.8
                ))
        
        return entities
    
    def _extract_mentioned_people(self, file_analysis: Dict) -> List[CleanEntity]:
        """Extract people mentioned in interview (beyond participants)"""
        entities = []
        existing_entities = file_analysis.get('entities', [])
        customer_name = file_analysis.get('customer_name', '')
        
        for entity in existing_entities:
            if (entity.get('type') == 'PERSON' and 
                entity.get('confidence', 0) > 0.6 and 
                entity['text'] != customer_name):
                
                entities.append(CleanEntity(
                    text=entity['text'],
                    entity_type=NodeType.PERSON,
                    confidence=entity['confidence'],
                    context="Person mentioned in interview",
                    source="file_analysis",
                    properties={"role": "mentioned_person", "format": "interview"},
                    domain_relevance=0.7
                ))
        
        return entities
    
    def _extract_interview_technologies(self, file_analysis: Dict) -> List[CleanEntity]:
        """Extract technologies/products discussed in interview"""
        entities = []
        existing_entities = file_analysis.get('entities', [])
        
        # Look for technology-related entities
        tech_types = ['TECHNOLOGY', 'PRODUCT', 'SOFTWARE', 'PLATFORM']
        for entity in existing_entities:
            if (entity.get('type') in tech_types and 
                entity.get('confidence', 0) > 0.6):
                
                entities.append(CleanEntity(
                    text=entity['text'],
                    entity_type=NodeType.CONCEPT,
                    confidence=entity['confidence'],
                    context="Technology/product discussed in interview",
                    source="file_analysis",
                    properties={"category": "technology", "format": "interview"},
                    domain_relevance=0.8
                ))
        
        return entities
    
    def _extract_organization_entities(self, file_analysis: Dict) -> List[CleanEntity]:
        """Extract organization entities"""
        entities = []
        existing_entities = file_analysis.get('entities', [])
        
        for entity in existing_entities:
            if entity.get('type') == 'ORGANIZATION' and entity.get('confidence', 0) > 0.6:
                entities.append(CleanEntity(
                    text=entity['text'],
                    entity_type=NodeType.ORGANIZATION,
                    confidence=entity['confidence'],
                    context=entity.get('context', 'Mentioned organization'),
                    source="file_analysis",
                    properties={"role": "organization"},
                    domain_relevance=0.8
                ))
        
        return entities
    
    def _extract_entities_with_llm(self, file_analysis: Dict) -> List[CleanEntity]:
        """Use LLM to extract additional high-quality entities"""
        entities = []
        
        # Get raw text sample
        raw_text = file_analysis.get('raw_text', '')
        if not raw_text:
            return entities
        
        # Use first 1000 characters for entity extraction
        text_sample = raw_text[:1000]
        
        entity_prompt = f"""
        Extract high-quality entities from this text. Focus on:
        - FINANCIAL_INSTRUMENT: Specific financial products, investment types
        - BUSINESS_CONCEPT: Business strategies, methodologies, frameworks
        - TOPIC: Specific subject areas or domains discussed
        
        Text: {text_sample}
        
        Return only clear, specific entities. Avoid generic terms.
        
        JSON format:
        {{
            "entities": [
                {{
                    "text": "specific entity name",
                    "type": "FINANCIAL_INSTRUMENT|BUSINESS_CONCEPT|TOPIC",
                    "confidence": 0.0-1.0,
                    "context": "why this entity is important"
                }}
            ]
        }}
        """
        
        try:
            response = self.bedrock.invoke_model(
                modelId='us.meta.llama4-scout-17b-instruct-v1:0',
                body=json.dumps({
                    'prompt': entity_prompt,
                    'max_gen_len': 800,
                    'temperature': 0.1
                })
            )
            
            result = json.loads(response['body'].read())
            llm_response = result.get('generation', '{}')
            
            try:
                entities_data = json.loads(llm_response)
                for entity_data in entities_data.get('entities', []):
                    entity_type_str = entity_data.get('type', '')
                    if entity_type_str in ['FINANCIAL_INSTRUMENT', 'BUSINESS_CONCEPT', 'TOPIC']:
                        node_type = NodeType.FINANCIAL_INSTRUMENT if entity_type_str == 'FINANCIAL_INSTRUMENT' else \
                                   NodeType.BUSINESS_CONCEPT if entity_type_str == 'BUSINESS_CONCEPT' else \
                                   NodeType.TOPIC
                        
                        entities.append(CleanEntity(
                            text=entity_data['text'],
                            entity_type=node_type,
                            confidence=entity_data.get('confidence', 0.7),
                            context=entity_data.get('context', ''),
                            source="file_analysis",
                            properties={"extraction_method": "llm"},
                            domain_relevance=0.8
                        ))
            except json.JSONDecodeError:
                pass
                
        except Exception as e:
            print(f"LLM entity extraction failed: {str(e)}")
        
        return entities
    
    def _extract_behavioral_pattern_entities(self, needs_analysis: Dict) -> List[CleanEntity]:
        """Extract behavioral pattern entities from needs analysis"""
        entities = []
        
        behavioral_patterns = needs_analysis.get('behavioral_patterns', [])
        for pattern in behavioral_patterns[:5]:  # Limit to top 5 patterns
            if isinstance(pattern, str) and len(pattern.strip()) > 0:
                clean_pattern = self._clean_entity_text(pattern)
                if clean_pattern:
                    entities.append(CleanEntity(
                        text=clean_pattern,
                        entity_type=NodeType.BEHAVIORAL_PATTERN,
                        confidence=0.8,
                        context="Observed behavioral pattern",
                        source="needs_analysis",
                        properties={"category": "behavior", "source": "needs_analysis"},
                        domain_relevance=0.9
                    ))
        
        return entities
    
    def _extract_personality_trait_entities(self, needs_analysis: Dict) -> List[CleanEntity]:
        """Extract personality trait entities from needs analysis"""
        entities = []
        
        personality_traits = needs_analysis.get('personality_traits', [])
        for trait in personality_traits[:5]:  # Limit to top 5 traits
            if isinstance(trait, str) and len(trait.strip()) > 0:
                clean_trait = self._clean_entity_text(trait)
                if clean_trait:
                    entities.append(CleanEntity(
                        text=clean_trait,
                        entity_type=NodeType.PERSONALITY_TRAIT,
                        confidence=0.8,
                        context="Identified personality trait",
                        source="needs_analysis",
                        properties={"category": "personality", "source": "needs_analysis"},
                        domain_relevance=0.9
                    ))
        
        return entities
    
    def _extract_need_entities(self, needs_analysis: Dict) -> List[CleanEntity]:
        """Extract significant human need entities"""
        entities = []
        
        needs_scores = needs_analysis.get('needs_scores', {})
        for need_name, score in needs_scores.items():
            if float(score) > 0.4:  # Only include significant needs
                entities.append(CleanEntity(
                    text=need_name.title(),
                    entity_type=NodeType.NEED,
                    confidence=float(score),
                    context=f"Human need with score {score}",
                    source="needs_analysis",
                    properties={"category": "human_need", "score": float(score)},
                    domain_relevance=1.0
                ))
        
        return entities
    
    def _extract_life_theme_entities(self, needs_analysis: Dict) -> List[CleanEntity]:
        """Extract life theme entities"""
        entities = []
        
        life_themes = needs_analysis.get('life_themes', [])
        for theme in life_themes[:3]:  # Limit to top 3 themes
            if isinstance(theme, str) and len(theme.strip()) > 0:
                clean_theme = self._clean_entity_text(theme)
                if clean_theme:
                    entities.append(CleanEntity(
                        text=clean_theme,
                        entity_type=NodeType.CONCEPT,
                        confidence=0.7,
                        context="Major life theme",
                        source="needs_analysis",
                        properties={"category": "life_theme", "source": "needs_analysis"},
                        domain_relevance=0.8
                    ))
        
        return entities
    
    def _clean_entity_text(self, text: str) -> str:
        """Clean and normalize entity text"""
        if not isinstance(text, str):
            return ""
        
        # Remove extra whitespace and clean up
        cleaned = re.sub(r'\s+', ' ', text.strip())
        
        # Remove common prefixes that don't add value
        prefixes_to_remove = ['Mentioned ', 'Discussed ', 'Has ', 'Shows ']
        for prefix in prefixes_to_remove:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):]
        
        # Capitalize properly
        if len(cleaned) > 0:
            cleaned = cleaned[0].upper() + cleaned[1:]
        
        return cleaned if len(cleaned) > 2 else ""  # Minimum length check
    
    def _deduplicate_entities(self, entities: List[CleanEntity]) -> List[CleanEntity]:
        """Remove duplicate entities, keeping the highest confidence version"""
        entity_map = {}
        
        for entity in entities:
            key = (entity.text.lower(), entity.entity_type)
            if key not in entity_map or entity.confidence > entity_map[key].confidence:
                entity_map[key] = entity
        
        return list(entity_map.values())

class CleanRelationshipExtractor:
    """Extracts clean, meaningful relationships between entities"""
    
    def __init__(self, bedrock_client):
        self.bedrock = bedrock_client
    
    def extract_relationships(self, entities: List[CleanEntity], 
                            file_analysis: Dict, needs_analysis: Dict) -> List[CleanRelationship]:
        """Extract clean relationships between entities"""
        relationships = []
        
        # Check if this is interview format
        file_path = file_analysis.get('file_path', '')
        is_interview = self._is_interview_format(file_analysis, file_path)
        
        print(f"[DEBUG] Relationship extraction - File path: {file_path}")
        print(f"[DEBUG] Relationship extraction - Is interview: {is_interview}")
        print(f"[DEBUG] Relationship extraction - Entity count: {len(entities)}")
        
        if is_interview:
            # Interview-specific relationships
            print(f"[DEBUG] Using interview-specific relationship extraction")
            interview_rels = self._extract_interview_relationships(entities, file_analysis, needs_analysis)
            print(f"[DEBUG] Interview relationships found: {len(interview_rels)}")
            relationships.extend(interview_rels)
        else:
            # Standard relationships
            # 1. Person-Skill relationships
            person_skill_rels = self._extract_person_skill_relationships(entities)
            relationships.extend(person_skill_rels)
            
            # 2. Person-Need relationships
            person_need_rels = self._extract_person_need_relationships(entities, needs_analysis)
            relationships.extend(person_need_rels)
            
            # 3. Need-Behavioral Pattern relationships
            need_behavior_rels = self._extract_need_behavior_relationships(entities, needs_analysis)
            relationships.extend(need_behavior_rels)
            
            # 4. Skill-Concept relationships
            skill_concept_rels = self._extract_skill_concept_relationships(entities, file_analysis)
            relationships.extend(skill_concept_rels)
        
        # 5. LLM-powered semantic relationships (both formats)
        semantic_rels = self._extract_semantic_relationships_with_llm(entities, file_analysis)
        relationships.extend(semantic_rels)
        
        return self._deduplicate_relationships(relationships)
    
    def _is_interview_format(self, file_analysis: Dict, file_path: str) -> bool:
        """Determine if this is an interview format file (duplicate for relationship extractor)"""
        interview_indicators = ['interview', 'transcript', 'dialog', 'conversation']
        return any(indicator in file_path.lower() for indicator in interview_indicators)
    
    def _extract_interview_relationships(self, entities: List[CleanEntity], 
                                       file_analysis: Dict, needs_analysis: Dict) -> List[CleanRelationship]:
        """Extract relationships specific to interview format"""
        relationships = []
        
        # 1. Participant relationships (interviewer-interviewee)
        participant_rels = self._extract_participant_relationships(entities)
        relationships.extend(participant_rels)
        
        # 2. Person-Topic relationships (who discussed what)
        person_topic_rels = self._extract_person_topic_relationships(entities, file_analysis)
        relationships.extend(person_topic_rels)
        
        # 3. Person-Organization relationships (affiliations mentioned)
        person_org_rels = self._extract_person_organization_relationships(entities)
        relationships.extend(person_org_rels)
        
        # 4. Topic-Organization relationships (what topics relate to which orgs)
        topic_org_rels = self._extract_topic_organization_relationships(entities)
        relationships.extend(topic_org_rels)
        
        # 5. Person-Need relationships (from needs analysis)
        person_need_rels = self._extract_person_need_relationships(entities, needs_analysis)
        relationships.extend(person_need_rels)
        
        # 6. Person-Technology relationships (who mentioned what tech)
        person_tech_rels = self._extract_person_technology_relationships(entities)
        relationships.extend(person_tech_rels)
        
        return relationships
    
    def _extract_participant_relationships(self, entities: List[CleanEntity]) -> List[CleanRelationship]:
        """Extract relationships between interview participants"""
        relationships = []
        
        persons = [e for e in entities if e.entity_type == NodeType.PERSON]
        interviewer = None
        interviewee = None
        
        # Identify roles
        for person in persons:
            role = person.properties.get('role', '')
            if role == 'interviewer':
                interviewer = person
            elif role == 'interviewee' or person.properties.get('primary', False):
                interviewee = person
        
        # Create interview relationship
        if interviewer and interviewee:
            relationships.append(CleanRelationship(
                source_entity=interviewer.text,
                target_entity=interviewee.text,
                relationship_type=EdgeType.INTERVIEWS,
                confidence=0.95,
                evidence=[f"{interviewer.text} conducts interview with {interviewee.text}"],
                reasoning="Interview participant relationship",
                source="interview_analysis"
            ))
        
        return relationships
    
    def _extract_person_topic_relationships(self, entities: List[CleanEntity], 
                                          file_analysis: Dict) -> List[CleanRelationship]:
        """Extract relationships between people and topics they discussed"""
        relationships = []
        
        persons = [e for e in entities if e.entity_type == NodeType.PERSON]
        topics = [e for e in entities if e.entity_type == NodeType.CONCEPT and 
                 e.properties.get('category') == 'topic']
        
        # Primary participant (interviewee) discusses all main topics
        primary_person = next((p for p in persons if p.properties.get('primary', False)), None)
        
        if primary_person:
            for topic in topics:
                relationships.append(CleanRelationship(
                    source_entity=primary_person.text,
                    target_entity=topic.text,
                    relationship_type=EdgeType.DISCUSSES,
                    confidence=0.8,
                    evidence=[f"{primary_person.text} discusses {topic.text} in interview"],
                    reasoning=f"Interview participant discusses topic",
                    source="interview_analysis"
                ))
        
        return relationships
    
    def _extract_person_organization_relationships(self, entities: List[CleanEntity]) -> List[CleanRelationship]:
        """Extract relationships between people and organizations mentioned"""
        relationships = []
        
        persons = [e for e in entities if e.entity_type == NodeType.PERSON]
        organizations = [e for e in entities if e.entity_type == NodeType.ORGANIZATION]
        
        # Primary person likely has affiliation with mentioned organizations
        primary_person = next((p for p in persons if p.properties.get('primary', False)), None)
        
        if primary_person:
            for org in organizations:
                relationships.append(CleanRelationship(
                    source_entity=primary_person.text,
                    target_entity=org.text,
                    relationship_type=EdgeType.AFFILIATED_WITH,
                    confidence=0.7,
                    evidence=[f"{primary_person.text} mentions {org.text} in interview"],
                    reasoning="Organization mentioned by interview participant",
                    source="interview_analysis"
                ))
        
        return relationships
    
    def _extract_topic_organization_relationships(self, entities: List[CleanEntity]) -> List[CleanRelationship]:
        """Extract relationships between topics and organizations"""
        relationships = []
        
        topics = [e for e in entities if e.entity_type == NodeType.CONCEPT and 
                 e.properties.get('category') == 'topic']
        organizations = [e for e in entities if e.entity_type == NodeType.ORGANIZATION]
        
        # Topics are related to organizations mentioned in same context
        for topic in topics:
            for org in organizations:
                relationships.append(CleanRelationship(
                    source_entity=topic.text,
                    target_entity=org.text,
                    relationship_type=EdgeType.RELATES_TO,
                    confidence=0.6,
                    evidence=[f"{topic.text} discussed in context of {org.text}"],
                    reasoning="Topic and organization discussed in same interview context",
                    source="interview_analysis"
                ))
        
        return relationships
    
    def _extract_person_technology_relationships(self, entities: List[CleanEntity]) -> List[CleanRelationship]:
        """Extract relationships between people and technologies mentioned"""
        relationships = []
        
        persons = [e for e in entities if e.entity_type == NodeType.PERSON]
        technologies = [e for e in entities if e.entity_type == NodeType.CONCEPT and 
                       e.properties.get('category') == 'technology']
        
        # Primary person discusses technologies
        primary_person = next((p for p in persons if p.properties.get('primary', False)), None)
        
        if primary_person:
            for tech in technologies:
                relationships.append(CleanRelationship(
                    source_entity=primary_person.text,
                    target_entity=tech.text,
                    relationship_type=EdgeType.USES,
                    confidence=0.7,
                    evidence=[f"{primary_person.text} discusses {tech.text} in interview"],
                    reasoning="Technology discussed by interview participant",
                    source="interview_analysis"
                ))
        
        return relationships
    
    def _extract_person_skill_relationships(self, entities: List[CleanEntity]) -> List[CleanRelationship]:
        """Extract relationships between people and their skills"""
        relationships = []
        
        persons = [e for e in entities if e.entity_type == NodeType.PERSON]
        skills = [e for e in entities if e.entity_type == NodeType.SKILL]
        
        for person in persons:
            for skill in skills:
                # High confidence relationship for primary customer
                if person.properties.get('primary', False):
                    relationships.append(CleanRelationship(
                        source_entity=person.text,
                        target_entity=skill.text,
                        relationship_type=EdgeType.SPECIALIZES_IN,
                        confidence=0.8,
                        evidence=[f"{person.text} demonstrates {skill.text}"],
                        reasoning=f"Primary customer {person.text} shows expertise in {skill.text}",
                        source="file_analysis"
                    ))
        
        return relationships
    
    def _extract_person_need_relationships(self, entities: List[CleanEntity], 
                                         needs_analysis: Dict) -> List[CleanRelationship]:
        """Extract relationships between people and their dominant needs"""
        relationships = []
        
        persons = [e for e in entities if e.entity_type == NodeType.PERSON]
        needs = [e for e in entities if e.entity_type == NodeType.NEED]
        
        # Get dominant needs from analysis
        dominant_needs = needs_analysis.get('dominant_needs', [])
        
        for person in persons:
            if person.properties.get('primary', False):  # Only for primary customer
                for need in needs:
                    # Check if this is a dominant need
                    need_score = 0.0
                    for dom_need in dominant_needs:
                        if isinstance(dom_need, (list, tuple)) and len(dom_need) >= 2:
                            need_name, score = dom_need[0], dom_need[1]
                            if need_name.lower() in need.text.lower():
                                need_score = float(score)
                                break
                    
                    if need_score > 0.5:  # Only strong needs
                        relationships.append(CleanRelationship(
                            source_entity=person.text,
                            target_entity=need.text,
                            relationship_type=EdgeType.DEMONSTRATES,
                            confidence=need_score,
                            evidence=[f"{person.text} shows strong {need.text} need (score: {need_score:.2f})"],
                            reasoning=f"Needs analysis indicates {person.text} has high {need.text} need",
                            source="needs_analysis"
                        ))
        
        return relationships
    
    def _extract_need_behavior_relationships(self, entities: List[CleanEntity], 
                                           needs_analysis: Dict) -> List[CleanRelationship]:
        """Extract relationships between needs and behavioral patterns"""
        relationships = []
        
        needs = [e for e in entities if e.entity_type == NodeType.NEED]
        behaviors = [e for e in entities if e.entity_type == NodeType.BEHAVIORAL_PATTERN]
        
        for need in needs:
            for behavior in behaviors:
                # Use LLM to determine if need influences behavior
                relationship_strength = self._analyze_need_behavior_relationship(need, behavior, needs_analysis)
                
                if relationship_strength > 0.6:
                    relationships.append(CleanRelationship(
                        source_entity=need.text,
                        target_entity=behavior.text,
                        relationship_type=EdgeType.INFLUENCES,
                        confidence=relationship_strength,
                        evidence=[f"{need.text} need drives {behavior.text} behavior"],
                        reasoning=f"Psychological need {need.text} manifests as {behavior.text} pattern",
                        source="needs_analysis"
                    ))
        
        return relationships
    
    def _extract_skill_concept_relationships(self, entities: List[CleanEntity], 
                                           file_analysis: Dict) -> List[CleanRelationship]:
        """Extract relationships between skills and concepts"""
        relationships = []
        
        skills = [e for e in entities if e.entity_type == NodeType.SKILL]
        concepts = [e for e in entities if e.entity_type == NodeType.CONCEPT]
        
        for skill in skills:
            for concept in concepts:
                # Check if skill relates to concept based on domain
                if self._skills_relate_to_concept(skill, concept, file_analysis):
                    relationships.append(CleanRelationship(
                        source_entity=skill.text,
                        target_entity=concept.text,
                        relationship_type=EdgeType.RELATES_TO,
                        confidence=0.7,
                        evidence=[f"{skill.text} skill applies to {concept.text}"],
                        reasoning=f"Professional skill {skill.text} is relevant to {concept.text}",
                        source="file_analysis"
                    ))
        
        return relationships
    
    def _extract_semantic_relationships_with_llm(self, entities: List[CleanEntity], 
                                               file_analysis: Dict) -> List[CleanRelationship]:
        """Use LLM to find semantic relationships between entities"""
        relationships = []
        
        # Only analyze relationships between different entity types to avoid noise
        entity_pairs = []
        for i, entity1 in enumerate(entities):
            for entity2 in entities[i+1:]:
                if entity1.entity_type != entity2.entity_type:  # Different types only
                    entity_pairs.append((entity1, entity2))
        
        # Limit to most promising pairs (max 10)
        entity_pairs = entity_pairs[:10]
        
        for entity1, entity2 in entity_pairs:
            relationship = self._analyze_semantic_relationship(entity1, entity2, file_analysis)
            if relationship and relationship.confidence > 0.6:
                relationships.append(relationship)
        
        return relationships
    
    def _analyze_need_behavior_relationship(self, need: CleanEntity, behavior: CleanEntity, 
                                          needs_analysis: Dict) -> float:
        """Analyze if a need influences a behavioral pattern"""
        
        # Simple heuristic based on need type and behavior
        need_behavior_mappings = {
            'certainty': ['strategic', 'planner', 'risk', 'manager', 'cautious', 'analytical'],
            'variety': ['innovative', 'creative', 'explorer', 'adventurous'],
            'significance': ['leader', 'achiever', 'competitive', 'ambitious'],
            'connection': ['collaborative', 'team', 'social', 'helper'],
            'growth': ['learner', 'developer', 'improver', 'student'],
            'contribution': ['helper', 'mentor', 'teacher', 'giver']
        }
        
        need_name = need.text.lower()
        behavior_text = behavior.text.lower()
        
        for need_key, behavior_keywords in need_behavior_mappings.items():
            if need_key in need_name:
                for keyword in behavior_keywords:
                    if keyword in behavior_text:
                        return 0.8  # High confidence for matching patterns
        
        return 0.3  # Low confidence for non-matching patterns
    
    def _skills_relate_to_concept(self, skill: CleanEntity, concept: CleanEntity, 
                                file_analysis: Dict) -> bool:
        """Check if a skill relates to a concept"""
        
        # Simple domain matching
        skill_text = skill.text.lower()
        concept_text = concept.text.lower()
        
        # Financial domain relationships
        financial_skills = ['financial', 'investment', 'insurance', 'planning', 'advisory']
        financial_concepts = ['financial', 'investment', 'insurance', 'planning', 'advisory', 'wealth']
        
        skill_is_financial = any(fs in skill_text for fs in financial_skills)
        concept_is_financial = any(fc in concept_text for fc in financial_concepts)
        
        return skill_is_financial and concept_is_financial
    
    def _analyze_semantic_relationship(self, entity1: CleanEntity, entity2: CleanEntity, 
                                     file_analysis: Dict) -> Optional[CleanRelationship]:
        """Use LLM to analyze semantic relationship between two entities"""
        
        # Get context from file analysis
        raw_text = file_analysis.get('raw_text', '')[:800]  # Limit context
        
        relationship_prompt = f"""
        Analyze if there's a meaningful relationship between "{entity1.text}" and "{entity2.text}".
        
        Entity 1: {entity1.text} (Type: {entity1.entity_type.value})
        Entity 2: {entity2.text} (Type: {entity2.entity_type.value})
        
        Context: {raw_text}
        
        Determine:
        1. Is there a clear relationship? (yes/no)
        2. What type of relationship? (RELATES_TO, ENABLES, REQUIRES, WORKS_WITH)
        3. Confidence level (0.0-1.0)
        4. Brief evidence
        
        JSON format:
        {{
            "has_relationship": true/false,
            "relationship_type": "RELATES_TO|ENABLES|REQUIRES|WORKS_WITH",
            "confidence": 0.0-1.0,
            "evidence": "brief evidence",
            "reasoning": "why they are related"
        }}
        """
        
        try:
            response = self.bedrock.invoke_model(
                modelId='us.meta.llama4-scout-17b-instruct-v1:0',
                body=json.dumps({
                    'prompt': relationship_prompt,
                    'max_gen_len': 300,
                    'temperature': 0.1
                })
            )
            
            result = json.loads(response['body'].read())
            llm_response = result.get('generation', '{}')
            
            try:
                relationship_data = json.loads(llm_response)
                
                if relationship_data.get('has_relationship', False) and relationship_data.get('confidence', 0) > 0.6:
                    edge_type_str = relationship_data.get('relationship_type', 'RELATES_TO')
                    edge_type = EdgeType.RELATES_TO  # Default
                    
                    if edge_type_str == 'ENABLES':
                        edge_type = EdgeType.ENABLES
                    elif edge_type_str == 'REQUIRES':
                        edge_type = EdgeType.REQUIRES
                    elif edge_type_str == 'WORKS_WITH':
                        edge_type = EdgeType.WORKS_WITH
                    
                    return CleanRelationship(
                        source_entity=entity1.text,
                        target_entity=entity2.text,
                        relationship_type=edge_type,
                        confidence=relationship_data.get('confidence', 0.7),
                        evidence=[relationship_data.get('evidence', '')],
                        reasoning=relationship_data.get('reasoning', ''),
                        source="llm_semantic"
                    )
            except json.JSONDecodeError:
                pass
                
        except Exception as e:
            print(f"LLM relationship analysis failed: {str(e)}")
        
        return None
    
    def _deduplicate_relationships(self, relationships: List[CleanRelationship]) -> List[CleanRelationship]:
        """Remove duplicate relationships, keeping the highest confidence version"""
        relationship_map = {}
        
        for rel in relationships:
            key = (rel.source_entity.lower(), rel.target_entity.lower(), rel.relationship_type)
            if key not in relationship_map or rel.confidence > relationship_map[key].confidence:
                relationship_map[key] = rel
        
        return list(relationship_map.values())

class EnhancedHypergraphBuilderV2:
    """Enhanced Hypergraph Builder V2 with clean entity and relationship extraction"""
    
    def __init__(self):
        self.bedrock = boto3.client('bedrock-runtime')
        self.entity_extractor = CleanEntityExtractor(self.bedrock)
        self.relationship_extractor = CleanRelationshipExtractor(self.bedrock)
    
    def build_enhanced_hypergraph(self, analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build enhanced hypergraph with clean entities and relationships"""
        
        # Extract file analysis and needs analysis
        # For AWS format, data is in agent_spec.processing_config
        processing_config = analysis_data.get('processing_config', analysis_data)
        
        file_analysis = self._extract_file_analysis(processing_config)
        needs_analysis = self._extract_needs_analysis(processing_config)
        
        # Add customer info to analysis data for entity extraction
        analysis_data.update({
            'customer_name': processing_config.get('customer_name'),
            'customer_folder': processing_config.get('customer_folder'),
            'file_path': processing_config.get('file_path')
        })
        
        # 1. Extract clean entities from both sources
        file_entities = self.entity_extractor.extract_entities_from_file_analysis(file_analysis)
        needs_entities = self.entity_extractor.extract_entities_from_needs_analysis(needs_analysis)
        
        all_entities = file_entities + needs_entities
        
        # If we have very few entities, create some basic ones from available data
        if len(all_entities) < 3:
            # Add customer as person entity if we have the name
            customer_name = analysis_data.get('customer_name') or file_analysis.get('customer_name')
            if customer_name:
                customer_entity = CleanEntity(
                    text=customer_name,
                    entity_type=NodeType.PERSON,
                    confidence=0.9,
                    context="Primary customer",
                    source="metadata",
                    properties={"role": "customer", "primary": True},
                    domain_relevance=1.0
                )
                all_entities.append(customer_entity)
        
        # 2. Extract clean relationships
        relationships = self.relationship_extractor.extract_relationships(
            all_entities, file_analysis, needs_analysis
        )
        
        # 3. Create enhanced hypernodes
        hypernodes = self._create_enhanced_hypernodes(all_entities, analysis_data)
        
        # 4. Create enhanced hyperedges
        hyperedges = self._create_enhanced_hyperedges(relationships, hypernodes)
        
        # 5. Calculate metrics and insights
        metrics = self._calculate_graph_metrics(hypernodes, hyperedges)
        insights = self._generate_graph_insights(hypernodes, hyperedges, analysis_data)
        
        return {
            'hypernodes': [self._serialize_node(node) for node in hypernodes],
            'hyperedges': [self._serialize_edge(edge) for edge in hyperedges],
            'graph_metrics': metrics,
            'graph_insights': insights,
            'total_nodes': len(hypernodes),
            'total_edges': len(hyperedges),
            'processing_metadata': {
                'llm_entity_classification': True,
                'semantic_relationships': True,
                'domain_specific_analysis': True,
                'psychological_need_mapping': True,
                'clean_entity_extraction': True,
                'clean_relationship_extraction': True
            }
        }
    
    def _extract_file_analysis(self, analysis_data: Dict) -> Dict:
        """Extract file analysis data from the input"""
        # Handle both direct call and processing_config wrapper
        processing_config = analysis_data.get('processing_config', analysis_data)
        
        # Try different possible locations for file analysis data
        if 'file_analysis' in processing_config:
            return processing_config['file_analysis']
        elif 'interview_result' in processing_config:
            return processing_config['interview_result']
        elif 'raw_text' in processing_config:
            return processing_config
        else:
            # For AWS format, we might not have direct file analysis
            # Create a minimal structure with available data from processing_config
            return {
                'customer_name': processing_config.get('customer_name', ''),
                'file_path': processing_config.get('file_path', ''),
                'entities': [],  # Will be empty, but V2 can handle this
                'key_insights': {
                    'skills_and_competencies': [],
                    'main_themes': [],
                    'goals_and_aspirations': []
                }
            }
    
    def _extract_needs_analysis(self, analysis_data: Dict) -> Dict:
        """Extract needs analysis data from the input"""
        # Handle both direct call and processing_config wrapper
        processing_config = analysis_data.get('processing_config', analysis_data)
        
        if 'needs_analysis' in processing_config:
            needs_data = processing_config['needs_analysis']
            
            # Handle AWS format: {statusCode: 200, body: "JSON string"}
            if isinstance(needs_data, dict) and 'body' in needs_data:
                try:
                    body_str = needs_data['body']
                    if isinstance(body_str, str):
                        parsed_body = json.loads(body_str)
                        if 'result' in parsed_body:
                            return parsed_body['result']
                        else:
                            return parsed_body
                    else:
                        return needs_data
                except json.JSONDecodeError:
                    print(f"Failed to parse needs_analysis body: {needs_data.get('body', '')[:100]}...")
                    return {}
            else:
                # Direct format
                return needs_data
        else:
            return {}
    
    def _create_enhanced_hypernodes(self, entities: List[CleanEntity], 
                                  analysis_data: Dict) -> List[EnhancedHyperNode]:
        """Create enhanced hypernodes from clean entities"""
        nodes = []
        timestamp = datetime.now().isoformat()
        source = analysis_data.get('file_path', 'unknown')
        
        for entity in entities:
            node_id = self._generate_node_id(entity.text, entity.entity_type)
            
            node = EnhancedHyperNode(
                id=node_id,
                content=entity.text,
                node_type=entity.entity_type,
                confidence=Decimal(str(entity.confidence)),
                timestamp=timestamp,
                source=source,
                metadata={
                    'extraction_source': entity.source,
                    'context': entity.context,
                    'domain_relevance': entity.domain_relevance
                },
                needs_classification={},  # Will be populated if relevant
                domain_specific_properties=entity.properties
            )
            nodes.append(node)
        
        return nodes
    
    def _create_enhanced_hyperedges(self, relationships: List[CleanRelationship], 
                                  hypernodes: List[EnhancedHyperNode]) -> List[EnhancedHyperEdge]:
        """Create enhanced hyperedges from clean relationships"""
        edges = []
        timestamp = datetime.now().isoformat()
        
        # Create node lookup
        node_lookup = {node.content.lower(): node.id for node in hypernodes}
        
        for rel in relationships:
            source_id = node_lookup.get(rel.source_entity.lower())
            target_id = node_lookup.get(rel.target_entity.lower())
            
            if source_id and target_id:
                edge_id = f"edge_{source_id}_{target_id}_{rel.relationship_type.value}"
                
                edge = EnhancedHyperEdge(
                    id=edge_id,
                    source_node_id=source_id,
                    target_node_id=target_id,
                    edge_type=rel.relationship_type,
                    confidence=Decimal(str(rel.confidence)),
                    timestamp=timestamp,
                    metadata={
                        'extraction_source': rel.source,
                        'relationship_strength': rel.confidence
                    },
                    evidence=rel.evidence,
                    reasoning=rel.reasoning
                )
                edges.append(edge)
        
        return edges
    
    def _generate_node_id(self, content: str, node_type: NodeType) -> str:
        """Generate unique node ID"""
        content_hash = hashlib.md5(content.lower().encode()).hexdigest()[:8]
        return f"{node_type.value}_{content_hash}"
    
    def _calculate_graph_metrics(self, nodes: List[EnhancedHyperNode], 
                               edges: List[EnhancedHyperEdge]) -> Dict[str, Any]:
        """Calculate graph metrics"""
        node_types = {}
        edge_types = {}
        
        for node in nodes:
            node_type = node.node_type.value
            node_types[node_type] = node_types.get(node_type, 0) + 1
        
        for edge in edges:
            edge_type = edge.edge_type.value
            edge_types[edge_type] = edge_types.get(edge_type, 0) + 1
        
        return {
            'total_nodes': len(nodes),
            'total_edges': len(edges),
            'node_type_distribution': node_types,
            'edge_type_distribution': edge_types,
            'average_confidence': float(sum(node.confidence for node in nodes) / len(nodes)) if nodes else 0.0,
            'relationship_diversity': len(edge_types)
        }
    
    def _generate_graph_insights(self, nodes: List[EnhancedHyperNode], 
                               edges: List[EnhancedHyperEdge], analysis_data: Dict) -> Dict[str, Any]:
        """Generate insights about the graph"""
        
        # Identify central entities (most connected)
        node_connections = {}
        for edge in edges:
            node_connections[edge.source_node_id] = node_connections.get(edge.source_node_id, 0) + 1
            node_connections[edge.target_node_id] = node_connections.get(edge.target_node_id, 0) + 1
        
        # Find most connected nodes
        most_connected = sorted(node_connections.items(), key=lambda x: x[1], reverse=True)[:3]
        
        # Get node content for most connected
        node_lookup = {node.id: node.content for node in nodes}
        central_entities = [node_lookup.get(node_id, 'Unknown') for node_id, _ in most_connected]
        
        return {
            'central_entities': central_entities,
            'graph_density': len(edges) / (len(nodes) * (len(nodes) - 1)) if len(nodes) > 1 else 0.0,
            'most_common_relationship': max(edge.edge_type.value for edge in edges) if edges else 'none',
            'entity_diversity': len(set(node.node_type.value for node in nodes)),
            'quality_score': self._calculate_quality_score(nodes, edges)
        }
    
    def _calculate_quality_score(self, nodes: List[EnhancedHyperNode], 
                               edges: List[EnhancedHyperEdge]) -> float:
        """Calculate overall graph quality score"""
        if not nodes:
            return 0.0
        
        # Factors for quality:
        # 1. Average node confidence
        avg_node_confidence = float(sum(node.confidence for node in nodes) / len(nodes))
        
        # 2. Average edge confidence
        avg_edge_confidence = float(sum(edge.confidence for edge in edges) / len(edges)) if edges else 0.0
        
        # 3. Entity type diversity
        entity_types = len(set(node.node_type.value for node in nodes))
        diversity_score = min(entity_types / 6.0, 1.0)  # Normalize to max 6 types
        
        # 4. Relationship diversity
        relationship_types = len(set(edge.edge_type.value for edge in edges)) if edges else 0
        rel_diversity_score = min(relationship_types / 5.0, 1.0)  # Normalize to max 5 types
        
        # Weighted average
        quality_score = (
            0.3 * avg_node_confidence +
            0.3 * avg_edge_confidence +
            0.2 * diversity_score +
            0.2 * rel_diversity_score
        )
        
        return quality_score
    
    def _serialize_node(self, node: EnhancedHyperNode) -> Dict[str, Any]:
        """Serialize node for JSON output"""
        return {
            'id': node.id,
            'content': node.content,
            'node_type': node.node_type.value,
            'confidence': float(node.confidence),
            'timestamp': node.timestamp,
            'source': node.source,
            'metadata': node.metadata,
            'needs_classification': {k: float(v) for k, v in node.needs_classification.items()},
            'domain_specific_properties': node.domain_specific_properties
        }
    
    def _serialize_edge(self, edge: EnhancedHyperEdge) -> Dict[str, Any]:
        """Serialize edge for JSON output"""
        return {
            'id': edge.id,
            'source_node_id': edge.source_node_id,
            'target_node_id': edge.target_node_id,
            'edge_type': edge.edge_type.value,
            'confidence': float(edge.confidence),
            'timestamp': edge.timestamp,
            'metadata': edge.metadata,
            'evidence': edge.evidence,
            'reasoning': edge.reasoning
        }

def lambda_handler(event, context):
    """AWS Lambda handler for enhanced hypergraph builder V2"""
    
    builder = EnhancedHypergraphBuilderV2()
    
    try:
        execution_id = event.get('execution_id', context.aws_request_id)
        
        # Debug: Log the incoming event structure
        print(f"[DEBUG] Event keys: {list(event.keys())}")
        if 'agent_spec' in event:
            print(f"[DEBUG] Agent spec keys: {list(event['agent_spec'].keys())}")
            if 'processing_config' in event['agent_spec']:
                config = event['agent_spec']['processing_config']
                print(f"[DEBUG] Processing config keys: {list(config.keys())}")
                print(f"[DEBUG] Customer name: {config.get('customer_name', 'Not found')}")
                print(f"[DEBUG] Has needs_analysis: {'needs_analysis' in config}")
        
        # Extract analysis data from event (AWS format)
        analysis_data = {}
        
        # Check for agent_spec structure (AWS Step Functions format)
        if 'agent_spec' in event:
            agent_spec = event['agent_spec']
            processing_config = agent_spec.get('processing_config', {})
            
            # Set the processing_config as the main analysis_data
            analysis_data = {
                'processing_config': processing_config,
                'customer_name': processing_config.get('customer_name'),
                'customer_folder': processing_config.get('customer_folder'),
                'file_path': processing_config.get('file_path')
            }
        else:
            # Fallback for other formats
            analysis_data = event
        
        print(f"[DEBUG] Analysis data keys: {list(analysis_data.keys())}")
        
        # Debug: Check if interview format is detected
        file_path = processing_config.get('file_path', '')
        print(f"[DEBUG] File path: {file_path}")
        print(f"[DEBUG] Is interview format: {'interview' in file_path.lower() or 'transcript' in file_path.lower()}")
        
        # Build enhanced hypergraph
        result = builder.build_enhanced_hypergraph(analysis_data)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'execution_id': execution_id,
                'agent_type': 'enhanced_hypergraph_builder_v2',
                'result': result,
                'success': True
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'execution_id': event.get('execution_id', 'unknown'),
                'agent_type': 'enhanced_hypergraph_builder_v2',
                'error': str(e),
                'success': False
            })
        }