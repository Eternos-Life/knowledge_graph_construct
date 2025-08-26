"""
AWS Lambda Function: NLP Processing Agent
Performs comprehensive NLP analysis on interview transcripts
"""

import boto3
import json
import re
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
import hashlib

@dataclass
class EntityExtraction:
    text: str
    entity_type: str
    confidence: float
    start_pos: int
    end_pos: int
    context: str

@dataclass
class ConversationAnalysis:
    speaker_turns: int
    avg_response_length: float
    sentiment_distribution: Dict[str, float]
    engagement_score: float
    communication_style: str

@dataclass
class NLPResult:
    entities: List[EntityExtraction]
    key_insights: Dict[str, List[str]]
    conversation_analysis: ConversationAnalysis
    confidence: float
    processing_time: float
    entity_quality_score: float

class InterviewNLPProcessor:
    def __init__(self):
        self.bedrock = boto3.client('bedrock-runtime')
        self.dynamodb = boto3.resource('dynamodb')
        self.performance_table = self.dynamodb.Table('agent-performance-metrics')
        
        # Entity patterns for interview content
        self.entity_patterns = {
            'PERSON': [
                r'\b[A-Z][a-z]+ [A-Z][a-z]+\b',  # First Last names
                r'\b(?:Mr|Mrs|Ms|Dr|Prof)\.? [A-Z][a-z]+\b',  # Titles with names
            ],
            'ORGANIZATION': [
                r'\b[A-Z][a-zA-Z]+ (?:Inc|Corp|LLC|Ltd|Company|Corporation)\b',
                r'\b(?:Google|Microsoft|Apple|Amazon|Meta|Tesla|Netflix)\b',
                r'\bUniversity of [A-Z][a-z]+\b',
            ],
            'SKILL': [
                r'\b(?:Python|JavaScript|Java|C\+\+|React|Angular|Vue|Node\.js)\b',
                r'\b(?:machine learning|artificial intelligence|data science)\b',
                r'\b(?:leadership|management|communication|teamwork)\b',
            ],
            'LOCATION': [
                r'\b[A-Z][a-z]+, [A-Z]{2}\b',  # City, State
                r'\b(?:New York|Los Angeles|Chicago|Houston|Phoenix|Philadelphia)\b',
            ],
            'DATE': [
                r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2}, \d{4}\b',
                r'\b\d{1,2}/\d{1,2}/\d{4}\b',
                r'\b\d{4}-\d{2}-\d{2}\b',
            ]
        }
    
    def process_interview_nlp(self, interview_data: Dict[str, Any]) -> NLPResult:
        """Perform comprehensive NLP processing on interview data"""
        
        start_time = datetime.now()
        
        # Extract raw text
        raw_text = interview_data.get('raw_text', '')
        file_path = interview_data.get('file_path', '')
        
        # 1. Entity extraction
        entities = self.extract_entities(raw_text)
        
        # 2. Generate key insights using LLM
        key_insights = self.generate_key_insights(raw_text, entities)
        
        # 3. Conversation analysis
        conversation_analysis = self.analyze_conversation_dynamics(raw_text)
        
        # 4. Calculate quality scores
        entity_quality_score = self.calculate_entity_quality(entities, raw_text)
        confidence = self.calculate_overall_confidence(entities, key_insights, conversation_analysis)
        
        # 5. Calculate processing time
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return NLPResult(
            entities=entities,
            key_insights=key_insights,
            conversation_analysis=conversation_analysis,
            confidence=confidence,
            processing_time=processing_time,
            entity_quality_score=entity_quality_score
        )
    
    def extract_entities(self, text: str) -> List[EntityExtraction]:
        """Extract entities using pattern matching and context analysis"""
        entities = []
        
        for entity_type, patterns in self.entity_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                
                for match in matches:
                    # Extract context around the match
                    start = max(0, match.start() - 50)
                    end = min(len(text), match.end() + 50)
                    context = text[start:end].strip()
                    
                    # Calculate confidence based on pattern specificity
                    confidence = self.calculate_entity_confidence(match.group(), entity_type, context)
                    
                    entity = EntityExtraction(
                        text=match.group(),
                        entity_type=entity_type,
                        confidence=confidence,
                        start_pos=match.start(),
                        end_pos=match.end(),
                        context=context
                    )
                    entities.append(entity)
        
        # Remove duplicates and low-confidence entities
        entities = self.deduplicate_entities(entities)
        return [e for e in entities if e.confidence > 0.5]
    
    def calculate_entity_confidence(self, text: str, entity_type: str, context: str) -> float:
        """Calculate confidence score for extracted entity"""
        base_confidence = 0.7
        
        # Boost confidence based on context clues
        context_lower = context.lower()
        
        if entity_type == 'PERSON':
            if any(word in context_lower for word in ['worked with', 'colleague', 'manager', 'team member']):
                base_confidence += 0.2
        elif entity_type == 'ORGANIZATION':
            if any(word in context_lower for word in ['worked at', 'company', 'employer', 'organization']):
                base_confidence += 0.2
        elif entity_type == 'SKILL':
            if any(word in context_lower for word in ['experience with', 'skilled in', 'proficient', 'expertise']):
                base_confidence += 0.2
        
        return min(base_confidence, 1.0)
    
    def deduplicate_entities(self, entities: List[EntityExtraction]) -> List[EntityExtraction]:
        """Remove duplicate entities, keeping the highest confidence ones"""
        seen = {}
        
        for entity in entities:
            key = (entity.text.lower(), entity.entity_type)
            
            if key not in seen or entity.confidence > seen[key].confidence:
                seen[key] = entity
        
        return list(seen.values())
    
    def generate_key_insights(self, text: str, entities: List[EntityExtraction]) -> Dict[str, List[str]]:
        """Generate key insights using LLM analysis"""
        
        # Prepare entity summary for LLM
        entity_summary = {}
        for entity in entities:
            if entity.entity_type not in entity_summary:
                entity_summary[entity.entity_type] = []
            entity_summary[entity.entity_type].append(entity.text)
        
        insights_prompt = f"""
        Analyze this interview transcript and extract key insights in the following categories:

        Interview Text: {text[:2000]}...
        
        Extracted Entities: {entity_summary}

        Please provide insights in these categories:
        1. Skills and Competencies
        2. Professional Experience
        3. Achievements and Accomplishments
        4. Goals and Aspirations
        5. Challenges and Problem-Solving
        6. Leadership and Teamwork
        7. Learning and Development

        Return as JSON format:
        {{
            "skills_and_competencies": ["skill1", "skill2", ...],
            "professional_experience": ["experience1", "experience2", ...],
            "achievements_and_experiences": ["achievement1", "achievement2", ...],
            "goals_and_aspirations": ["goal1", "goal2", ...],
            "challenges_and_problem_solving": ["challenge1", "challenge2", ...],
            "leadership_and_teamwork": ["leadership1", "leadership2", ...],
            "learning_and_development": ["learning1", "learning2", ...]
        }}
        """
        
        try:
            response = self.bedrock.invoke_model(
                modelId='us.meta.llama4-scout-17b-instruct-v1:0',
                body=json.dumps({
                    'prompt': insights_prompt,
                    'max_gen_len': 1000,
                    'temperature': 0.2
                })
            )
            
            llm_result = json.loads(response['body'].read())
            
            # Parse the Llama response
            try:
                # Llama returns generation in 'generation' field
                content = llm_result.get('generation', '{}')
                insights = json.loads(content)
                return insights
            except (json.JSONDecodeError, KeyError, IndexError):
                # Fallback to pattern-based extraction
                return self.extract_insights_fallback(text, entities)
                
        except Exception as e:
            print(f"LLM insights generation failed: {e}")
            return self.extract_insights_fallback(text, entities)
    
    def extract_insights_fallback(self, text: str, entities: List[EntityExtraction]) -> Dict[str, List[str]]:
        """Fallback method for extracting insights using pattern matching"""
        
        insights = {
            "skills_and_competencies": [],
            "professional_experience": [],
            "achievements_and_experiences": [],
            "goals_and_aspirations": [],
            "challenges_and_problem_solving": [],
            "leadership_and_teamwork": [],
            "learning_and_development": []
        }
        
        # Extract skills from entities
        skill_entities = [e.text for e in entities if e.entity_type == 'SKILL']
        insights["skills_and_competencies"] = skill_entities
        
        # Extract organizations as experience
        org_entities = [e.text for e in entities if e.entity_type == 'ORGANIZATION']
        insights["professional_experience"] = [f"Experience at {org}" for org in org_entities]
        
        # Pattern-based extraction for other categories
        text_lower = text.lower()
        
        # Goals and aspirations
        goal_patterns = [
            r'(?:want to|hope to|plan to|aspire to|goal is to|looking to) ([^.!?]+)',
            r'(?:future|next|upcoming) ([^.!?]*(?:project|role|position|opportunity)[^.!?]*)',
        ]
        
        for pattern in goal_patterns:
            matches = re.findall(pattern, text_lower)
            insights["goals_and_aspirations"].extend(matches[:3])
        
        # Achievements
        achievement_patterns = [
            r'(?:achieved|accomplished|completed|delivered|built|created|led) ([^.!?]+)',
            r'(?:successful|successfully) ([^.!?]+)',
        ]
        
        for pattern in achievement_patterns:
            matches = re.findall(pattern, text_lower)
            insights["achievements_and_experiences"].extend(matches[:3])
        
        return insights
    
    def analyze_conversation_dynamics(self, text: str) -> ConversationAnalysis:
        """Analyze conversation flow and dynamics"""
        
        # Simple conversation analysis
        lines = text.split('\n')
        non_empty_lines = [line.strip() for line in lines if line.strip()]
        
        # Estimate speaker turns (simple heuristic)
        speaker_turns = len([line for line in non_empty_lines if ':' in line or line.endswith('?')])
        
        # Calculate average response length
        avg_response_length = sum(len(line.split()) for line in non_empty_lines) / max(len(non_empty_lines), 1)
        
        # Simple sentiment analysis
        positive_words = ['good', 'great', 'excellent', 'amazing', 'wonderful', 'fantastic', 'love', 'enjoy']
        negative_words = ['bad', 'terrible', 'awful', 'hate', 'dislike', 'difficult', 'challenging', 'problem']
        
        text_lower = text.lower()
        positive_count = sum(text_lower.count(word) for word in positive_words)
        negative_count = sum(text_lower.count(word) for word in negative_words)
        total_sentiment_words = positive_count + negative_count
        
        if total_sentiment_words > 0:
            sentiment_distribution = {
                'positive': positive_count / total_sentiment_words,
                'negative': negative_count / total_sentiment_words,
                'neutral': 1 - (positive_count + negative_count) / total_sentiment_words
            }
        else:
            sentiment_distribution = {'positive': 0.5, 'negative': 0.1, 'neutral': 0.4}
        
        # Calculate engagement score
        engagement_score = min(avg_response_length / 20, 1.0) * sentiment_distribution['positive']
        
        # Determine communication style
        question_count = text.count('?')
        exclamation_count = text.count('!')
        
        if question_count > exclamation_count * 2:
            communication_style = 'inquisitive'
        elif exclamation_count > question_count:
            communication_style = 'enthusiastic'
        elif avg_response_length > 30:
            communication_style = 'detailed'
        else:
            communication_style = 'concise'
        
        return ConversationAnalysis(
            speaker_turns=speaker_turns,
            avg_response_length=avg_response_length,
            sentiment_distribution=sentiment_distribution,
            engagement_score=engagement_score,
            communication_style=communication_style
        )
    
    def calculate_entity_quality(self, entities: List[EntityExtraction], text: str) -> float:
        """Calculate quality score for entity extraction"""
        if not entities:
            return 0.0
        
        # Factors for quality assessment
        avg_confidence = sum(e.confidence for e in entities) / len(entities)
        entity_diversity = len(set(e.entity_type for e in entities)) / len(self.entity_patterns)
        coverage_ratio = len(entities) / max(len(text.split()) / 50, 1)  # Entities per 50 words
        
        quality_score = (avg_confidence * 0.5) + (entity_diversity * 0.3) + (min(coverage_ratio, 1.0) * 0.2)
        return min(quality_score, 1.0)
    
    def calculate_overall_confidence(self, entities: List[EntityExtraction], 
                                   insights: Dict[str, List[str]], 
                                   conversation: ConversationAnalysis) -> float:
        """Calculate overall confidence in NLP processing results"""
        
        # Entity confidence component
        entity_conf = sum(e.confidence for e in entities) / max(len(entities), 1) if entities else 0.0
        
        # Insights richness component
        total_insights = sum(len(insight_list) for insight_list in insights.values())
        insights_conf = min(total_insights / 10, 1.0)  # Normalize to 0-1
        
        # Conversation analysis confidence
        conv_conf = min(conversation.engagement_score + 0.3, 1.0)
        
        # Weighted combination
        overall_confidence = (entity_conf * 0.4) + (insights_conf * 0.4) + (conv_conf * 0.2)
        return min(overall_confidence, 1.0)

# Lambda handler function
def lambda_handler(event, context):
    """AWS Lambda handler for NLP processing"""
    
    processor = InterviewNLPProcessor()
    
    try:
        # Extract input data
        agent_spec = event['agent_spec']
        execution_id = event['execution_id']
        
        # Get interview data from previous processing stage
        processing_config = agent_spec['processing_config']
        interview_data = processing_config.get('interview_data', {})
        
        # Perform NLP processing
        nlp_result = processor.process_interview_nlp(interview_data)
        
        # Record performance metrics
        from decimal import Decimal
        processor.performance_table.put_item(
            Item={
                'execution_id': execution_id,
                'agent_type': 'nlp_processing',
                'timestamp': context.aws_request_id,
                'confidence': Decimal(str(nlp_result.confidence)),
                'processing_time': Decimal(str(nlp_result.processing_time)),
                'entity_quality_score': Decimal(str(nlp_result.entity_quality_score)),
                'entities_extracted': len(nlp_result.entities),
                'processing_success': True
            }
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'execution_id': execution_id,
                'agent_type': 'nlp_processing',
                'result': {
                    'entities': [
                        {
                            'text': e.text,
                            'entity_type': e.entity_type,
                            'confidence': e.confidence,
                            'context': e.context
                        } for e in nlp_result.entities
                    ],
                    'insights': nlp_result.key_insights,
                    'conversation_analysis': {
                        'speaker_turns': nlp_result.conversation_analysis.speaker_turns,
                        'avg_response_length': nlp_result.conversation_analysis.avg_response_length,
                        'sentiment_distribution': nlp_result.conversation_analysis.sentiment_distribution,
                        'engagement_score': nlp_result.conversation_analysis.engagement_score,
                        'communication_style': nlp_result.conversation_analysis.communication_style
                    },
                    'confidence': nlp_result.confidence,
                    'processing_time': nlp_result.processing_time,
                    'entity_quality_score': nlp_result.entity_quality_score
                },
                'success': True
            })
        }
        
    except Exception as e:
        # Record failure
        processor.performance_table.put_item(
            Item={
                'execution_id': event.get('execution_id', 'unknown'),
                'agent_type': 'nlp_processing',
                'timestamp': context.aws_request_id,
                'error': str(e),
                'processing_success': False
            }
        )
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'execution_id': event.get('execution_id', 'unknown'),
                'agent_type': 'nlp_processing',
                'error': str(e),
                'success': False
            })
        }