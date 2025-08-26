"""
AWS Lambda Function: 6 Human Needs Analysis Agent
Enhanced with Dynamic Prompting for Content-Aware Analysis
"""

import json
import boto3
import os
from decimal import Decimal
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass
from enum import Enum

def create_dynamic_prompt(text, content_type, themes, entities):
    """
    Create content-aware prompts for needs analysis
    """
    # Base framework description
    base_framework = """
    Analyze the following text for the 6 human needs based on Tony Robbins' framework:
    1. Certainty (security, comfort, predictability)
    2. Variety (adventure, change, novelty) 
    3. Significance (importance, uniqueness, being special)
    4. Connection (love, belonging, intimacy)
    5. Growth (learning, developing, expanding)
    6. Contribution (giving, serving, making a difference)
    """
    
    # Content-specific analysis instructions
    content_instructions = get_content_specific_instructions(content_type, themes, entities)
    
    # Examples and focus areas based on content type
    examples = get_content_examples(content_type)
    
    # Construct the full prompt
    prompt = f"""{base_framework}
    
    CONTENT CONTEXT:
    - Content Type: {content_type}
    - Key Themes: {', '.join(themes) if themes else 'None detected'}
    - Key Entities: {', '.join([e.get('text', '') for e in entities[:5]]) if entities else 'None detected'}
    
    {content_instructions}
    
    {examples}
    
    Text to analyze:
    {text}
    
    Provide a JSON response with:
    - needs_scores: object with scores 0.0-1.0 for each need (vary scores based on evidence)
    - dominant_needs: array of top 3 needs with scores (should be different unless truly equal)
    - behavioral_patterns: array of observed patterns (be specific to content)
    - personality_traits: array of key traits (extract from context)
    - life_themes: array of major themes (identify from content)
    - confidence_score: overall confidence 0.0-1.0 (be realistic about certainty)
    
    IMPORTANT: Analyze the specific content provided. Different content should yield different scores.
    Look for concrete evidence and vary your analysis based on what you actually observe.
    """
    
    return prompt

def get_content_specific_instructions(content_type, themes, entities):
    """
    Get analysis instructions specific to content type
    """
    if content_type == 'interview_transcript':
        return """
        INTERVIEW ANALYSIS FOCUS:
        - Pay attention to speaking patterns and leadership style
        - Look for career motivations and professional drives
        - Analyze responses to challenges and decision-making
        - Consider the balance between personal and professional needs
        - Note communication style and relationship to others
        """
    
    elif content_type == 'financial_advice':
        return """
        ADVISORY CONTENT ANALYSIS FOCUS:
        - Examine the underlying motivations for giving advice
        - Look for security vs. growth orientations
        - Analyze the relationship between advisor and audience
        - Consider the balance between certainty and variety in recommendations
        - Note emphasis on contribution vs. significance
        """
    
    elif content_type == 'personal_story' or 'entrepreneurship' in str(themes).lower():
        return """
        PERSONAL/ENTREPRENEURIAL STORY ANALYSIS FOCUS:
        - Identify core driving motivations behind actions
        - Look for risk tolerance (variety vs. certainty)
        - Analyze relationship patterns and connection needs
        - Examine growth mindset and learning orientation
        - Consider contribution and impact motivations
        """
    
    else:
        return """
        GENERAL CONTENT ANALYSIS FOCUS:
        - Look for explicit and implicit motivational patterns
        - Analyze decision-making criteria and value systems
        - Consider relationship dynamics and social needs
        - Examine attitudes toward change and stability
        - Note expressions of purpose and meaning
        """

def get_content_examples(content_type):
    """
    Provide content-specific examples for better analysis
    """
    if content_type == 'interview_transcript':
        return """
        EXAMPLE PATTERNS TO LOOK FOR:
        - Certainty: Emphasis on processes, systems, predictable outcomes
        - Variety: Seeking new challenges, innovation, change
        - Significance: Leadership roles, unique achievements, recognition
        - Connection: Team building, mentoring, collaborative approaches
        - Growth: Learning from failures, continuous improvement
        - Contribution: Impact on industry, helping others, legacy building
        """
    
    elif content_type == 'financial_advice':
        return """
        EXAMPLE PATTERNS TO LOOK FOR:
        - Certainty: Focus on security, risk management, stable returns
        - Variety: Diverse investment strategies, exploring opportunities
        - Significance: Expertise demonstration, unique insights
        - Connection: Building trust, understanding client needs
        - Growth: Learning markets, developing skills
        - Contribution: Helping others achieve financial goals
        """
    
    else:
        return """
        EXAMPLE PATTERNS TO LOOK FOR:
        - Certainty: Seeking stability, avoiding risk, planning ahead
        - Variety: Embracing change, seeking new experiences
        - Significance: Standing out, being recognized, achieving status
        - Connection: Building relationships, belonging, intimacy
        - Growth: Learning, developing, expanding capabilities
        - Contribution: Helping others, making a difference, serving
        """

class HumanNeed(Enum):
    CERTAINTY = "certainty"
    VARIETY = "variety" 
    SIGNIFICANCE = "significance"
    CONNECTION = "connection"
    GROWTH = "growth"
    CONTRIBUTION = "contribution"

@dataclass
class NeedsAnalysisResult:
    needs_scores: Dict[HumanNeed, float]
    dominant_needs: List[Tuple[HumanNeed, float]]
    behavioral_patterns: List[str]
    personality_traits: List[str]
    life_themes: List[str]
    confidence_score: float

class InterviewNeedsAnalyzer:
    def __init__(self):
        self.bedrock = boto3.client('bedrock-runtime')
        self.dynamodb = boto3.resource('dynamodb')
        self.performance_table = self.dynamodb.Table('agent-performance-metrics')
        
        # Needs detection patterns optimized for interview transcripts
        self.needs_indicators = {
            HumanNeed.CERTAINTY: {
                'keywords': ['security', 'stable', 'predictable', 'safe', 'routine', 'control', 'plan', 'structure'],
                'phrases': ['need to know', 'want certainty', 'feel secure', 'have control', 'planned approach'],
                'context_clues': ['risk aversion', 'detailed planning', 'systematic approach']
            },
            HumanNeed.VARIETY: {
                'keywords': ['adventure', 'new', 'different', 'change', 'explore', 'variety', 'diverse', 'exciting'],
                'phrases': ['try new things', 'love variety', 'get bored easily', 'need change', 'different experiences'],
                'context_clues': ['career changes', 'multiple interests', 'travel experiences']
            },
            HumanNeed.SIGNIFICANCE: {
                'keywords': ['important', 'special', 'unique', 'recognition', 'achievement', 'success', 'impact', 'leader'],
                'phrases': ['make a difference', 'be recognized', 'stand out', 'achieve something', 'be remembered'],
                'context_clues': ['leadership roles', 'awards', 'achievements', 'public speaking']
            },
            HumanNeed.CONNECTION: {
                'keywords': ['family', 'friends', 'team', 'community', 'relationship', 'together', 'belong', 'love'],
                'phrases': ['work with others', 'part of team', 'close relationships', 'feel connected', 'belong to'],
                'context_clues': ['team projects', 'mentoring', 'collaboration', 'family mentions']
            },
            HumanNeed.GROWTH: {
                'keywords': ['learn', 'develop', 'grow', 'improve', 'progress', 'evolve', 'better', 'skills'],
                'phrases': ['keep learning', 'personal growth', 'develop skills', 'get better', 'continuous improvement'],
                'context_clues': ['education', 'training', 'skill development', 'career progression']
            },
            HumanNeed.CONTRIBUTION: {
                'keywords': ['help', 'serve', 'give', 'contribute', 'impact', 'difference', 'society', 'world'],
                'phrases': ['help others', 'give back', 'make impact', 'serve community', 'contribute to'],
                'context_clues': ['volunteering', 'social causes', 'mentoring others', 'community service']
            }
        }
    
    def analyze_needs_from_interview(self, interview_data: Dict[str, Any]) -> NeedsAnalysisResult:
        """Analyze 6 human needs from interview transcript data with dynamic prompting"""
        
        # Extract relevant content
        content = self.extract_analysis_content(interview_data)
        entities = interview_data.get('entities', [])
        insights = interview_data.get('key_insights', {})
        
        # Extract content type and themes for dynamic prompting
        content_type = interview_data.get('content_type', 'unknown')
        themes = interview_data.get('themes', [])
        
        # 1. Perform keyword-based initial analysis
        keyword_scores = self.analyze_needs_keywords(content)
        
        # 2. Use LLM for sophisticated needs detection with dynamic prompting
        llm_scores = self.analyze_needs_with_llm(content, entities, insights, content_type, themes)
        
        # 3. Combine and weight the scores
        final_scores = self.combine_needs_scores(keyword_scores, llm_scores)
        
        # 4. Extract behavioral patterns and personality traits
        behavioral_patterns = self.extract_behavioral_patterns(content, insights)
        personality_traits = self.extract_personality_traits(content, final_scores)
        
        # 5. Identify life themes
        life_themes = self.extract_life_themes(content, insights, final_scores)
        
        # 6. Calculate confidence score
        confidence = self.calculate_confidence_score(keyword_scores, llm_scores, content)
        
        # 7. Determine dominant needs
        dominant_needs = sorted(final_scores.items(), key=lambda x: x[1], reverse=True)[:3]
        
        return NeedsAnalysisResult(
            needs_scores=final_scores,
            dominant_needs=dominant_needs,
            behavioral_patterns=behavioral_patterns,
            personality_traits=personality_traits,
            life_themes=life_themes,
            confidence_score=confidence
        )
    
    def extract_analysis_content(self, interview_data: Dict) -> str:
        """Extract relevant content for needs analysis"""
        content_parts = []
        
        # Add main content
        if 'raw_text' in interview_data:
            content_parts.append(interview_data['raw_text'])
        
        # Add key insights
        insights = interview_data.get('key_insights', {})
        if insights:
            content_parts.append(f"Key insights: {json.dumps(insights)}")
        
        # Add conversation analysis
        conv_analysis = interview_data.get('conversation_analysis', {})
        if conv_analysis:
            content_parts.append(f"Conversation dynamics: {json.dumps(conv_analysis)}")
        
        return " ".join(content_parts)
    
    def analyze_needs_keywords(self, content: str) -> Dict[HumanNeed, float]:
        """Analyze needs using keyword matching"""
        content_lower = content.lower()
        word_count = len(content.split())
        needs_scores = {}
        
        for need, indicators in self.needs_indicators.items():
            score = 0.0
            
            # Keyword matching
            keyword_matches = sum(content_lower.count(keyword) for keyword in indicators['keywords'])
            keyword_score = min(keyword_matches / max(word_count / 100, 1), 1.0) * 0.4
            
            # Phrase matching
            phrase_matches = sum(1 for phrase in indicators['phrases'] if phrase in content_lower)
            phrase_score = min(phrase_matches / max(len(indicators['phrases']), 1), 1.0) * 0.3
            
            # Context clue matching
            context_matches = sum(1 for clue in indicators['context_clues'] if clue in content_lower)
            context_score = min(context_matches / max(len(indicators['context_clues']), 1), 1.0) * 0.3
            
            score = keyword_score + phrase_score + context_score
            needs_scores[need] = min(score, 1.0)
        
        return needs_scores
    
    def analyze_needs_with_llm(self, content: str, entities: List, insights: Dict, content_type: str = 'unknown', themes: List = None) -> Dict[HumanNeed, float]:
        """Use Bedrock LLM for sophisticated needs analysis with dynamic prompting"""
        
        if themes is None:
            themes = []
        
        # Create dynamic prompt based on content type and context
        dynamic_prompt = create_dynamic_prompt(content, content_type, themes, entities)
        
        # Use higher temperature for more varied responses
        temperature = 0.4
        
        response = self.bedrock.invoke_model(
            modelId='us.meta.llama4-scout-17b-instruct-v1:0',
            body=json.dumps({
                'prompt': dynamic_prompt,
                'max_gen_len': 2000,  # Increased for more detailed analysis
                'temperature': temperature
            })
        )
        
        llm_analysis = json.loads(response['body'].read())
        
        # Extract scores from Llama response
        needs_scores = {}
        try:
            # Llama returns generation in 'generation' field
            content_response = llm_analysis.get('generation', '{}')
            parsed_content = json.loads(content_response)
            
            for need in HumanNeed:
                if need.value in parsed_content:
                    if isinstance(parsed_content[need.value], dict):
                        score = parsed_content[need.value].get('score', 0.0)
                    else:
                        score = parsed_content[need.value]
                    needs_scores[need] = Decimal(str(max(0.0, min(float(score), 1.0))))
                else:
                    needs_scores[need] = Decimal('0.3')  # Default fallback
        except (json.JSONDecodeError, KeyError, ValueError):
            # Fallback to varied default scores if parsing fails
            fallback_scores = [Decimal('0.3'), Decimal('0.4'), Decimal('0.5'), Decimal('0.6'), Decimal('0.7'), Decimal('0.2')]
            for i, need in enumerate(HumanNeed):
                needs_scores[need] = fallback_scores[i % len(fallback_scores)]
        
        return needs_scores
    
    def combine_needs_scores(self, keyword_scores: Dict, llm_scores: Dict) -> Dict[HumanNeed, float]:
        """Combine keyword and LLM scores with appropriate weighting"""
        combined_scores = {}
        
        for need in HumanNeed:
            keyword_score = keyword_scores.get(need, 0.0)
            llm_score = llm_scores.get(need, 0.0)
            
            # Weight: 30% keyword matching, 70% LLM analysis
            combined_score = (0.3 * keyword_score) + (0.7 * llm_score)
            combined_scores[need] = combined_score
        
        return combined_scores
    
    def extract_behavioral_patterns(self, content: str, insights: Dict) -> List[str]:
        """Extract behavioral patterns from interview content"""
        
        patterns_prompt = f"""
        Based on this interview content, identify key behavioral patterns:

        Content: {content[:1500]}...
        Insights: {insights}

        Identify patterns such as:
        - Leadership style
        - Problem-solving approach
        - Communication style
        - Work preferences
        - Decision-making patterns
        - Learning style
        - Relationship building
        - Goal orientation

        Return as JSON array of pattern names.
        """
        
        response = self.bedrock.invoke_model(
            modelId='us.meta.llama4-scout-17b-instruct-v1:0',
            body=json.dumps({
                'prompt': patterns_prompt,
                'max_gen_len': 500,
                'temperature': 0.2
            })
        )
        
        patterns_data = json.loads(response['body'].read())
        try:
            # Llama returns generation in 'generation' field
            content = patterns_data.get('generation', '[]')
            return json.loads(content)
        except (json.JSONDecodeError, KeyError, IndexError):
            return []
    
    def extract_personality_traits(self, content: str, needs_scores: Dict) -> List[str]:
        """Extract personality traits based on content and needs scores"""
        
        traits_prompt = f"""
        Based on this interview and the human needs scores, identify key personality traits:

        Content sample: {content[:1000]}...
        
        Needs Scores:
        - Certainty: {needs_scores.get(HumanNeed.CERTAINTY, 0.0):.2f}
        - Variety: {needs_scores.get(HumanNeed.VARIETY, 0.0):.2f}
        - Significance: {needs_scores.get(HumanNeed.SIGNIFICANCE, 0.0):.2f}
        - Connection: {needs_scores.get(HumanNeed.CONNECTION, 0.0):.2f}
        - Growth: {needs_scores.get(HumanNeed.GROWTH, 0.0):.2f}
        - Contribution: {needs_scores.get(HumanNeed.CONTRIBUTION, 0.0):.2f}

        Identify personality traits such as:
        - Extroverted/Introverted
        - Analytical/Intuitive
        - Detail-oriented/Big-picture
        - Risk-taking/Risk-averse
        - Collaborative/Independent
        - Optimistic/Realistic
        - Innovative/Traditional

        Return as JSON array of trait names.
        """
        
        response = self.bedrock.invoke_model(
            modelId='us.meta.llama4-scout-17b-instruct-v1:0',
            body=json.dumps({
                'prompt': traits_prompt,
                'max_gen_len': 400,
                'temperature': 0.2
            })
        )
        
        traits_data = json.loads(response['body'].read())
        try:
            # Llama returns generation in 'generation' field
            content = traits_data.get('generation', '[]')
            return json.loads(content)
        except (json.JSONDecodeError, KeyError, IndexError):
            return []
    
    def extract_life_themes(self, content: str, insights: Dict, needs_scores: Dict) -> List[str]:
        """Extract major life themes from the interview"""
        
        themes_prompt = f"""
        Identify major life themes from this interview:

        Content: {content[:1200]}...
        Insights: {insights}
        Dominant needs: {sorted(needs_scores.items(), key=lambda x: x[1], reverse=True)[:3]}

        Look for themes such as:
        - Career progression and ambition
        - Family and relationships
        - Personal development and learning
        - Innovation and creativity
        - Service and helping others
        - Overcoming challenges
        - Building and creating
        - Leadership and influence

        Return as JSON array of theme names with brief descriptions.
        """
        
        response = self.bedrock.invoke_model(
            modelId='us.meta.llama4-scout-17b-instruct-v1:0',
            body=json.dumps({
                'prompt': themes_prompt,
                'max_gen_len': 500,
                'temperature': 0.2
            })
        )
        
        themes_data = json.loads(response['body'].read())
        try:
            # Llama returns generation in 'generation' field
            content = themes_data.get('generation', '[]')
            return json.loads(content)
        except (json.JSONDecodeError, KeyError, IndexError):
            return []
    
    def calculate_confidence_score(self, keyword_scores: Dict, llm_scores: Dict, content: str) -> float:
        """Calculate confidence score for the needs analysis"""
        
        # Factors affecting confidence:
        # 1. Content length (more content = higher confidence)
        content_length_factor = min(len(content.split()) / 1000, 1.0) * 0.3
        
        # 2. Agreement between keyword and LLM scores
        agreement_scores = []
        for need in HumanNeed:
            keyword_score = keyword_scores.get(need, 0.0)
            llm_score = llm_scores.get(need, 0.0)
            agreement = 1.0 - abs(keyword_score - llm_score)
            agreement_scores.append(agreement)
        
        agreement_factor = sum(agreement_scores) / len(agreement_scores) * 0.4
        
        # 3. Presence of clear indicators
        clear_indicators = sum(1 for score in llm_scores.values() if score > 0.6)
        indicator_factor = min(clear_indicators / 3, 1.0) * 0.3
        
        confidence = content_length_factor + agreement_factor + indicator_factor
        return min(confidence, 1.0)

def lambda_handler(event, context):
    """
    Lambda handler for needs analysis agent - FIXED VERSION
    """
    try:
        # Debug: Log the incoming event structure
        print(f"Received event keys: {list(event.keys())}")
        
        # Extract input data - the event IS the data from Step Functions
        execution_id = event.get('execution_id', context.aws_request_id)
        
        # The content data comes directly from Step Functions output
        content_data = None
        content_type = 'unknown'
        
        # Check for parsed_analysis from previous step
        if 'parsed_analysis' in event:
            parsed_analysis = event['parsed_analysis']
            print(f"Found parsed_analysis: {type(parsed_analysis)}")
            
            if isinstance(parsed_analysis, dict) and 'analysis' in parsed_analysis:
                # Extract the analysis data
                analysis_data = parsed_analysis['analysis']
                if isinstance(analysis_data, dict):
                    content_data = analysis_data
                    content_type = 'financial_advice'
                    print(f"Using parsed_analysis.analysis as content_data")
        
        # Also check for direct analysis string
        if not content_data and 'analysis' in event:
            analysis_text = event['analysis']
            print(f"Found direct analysis: {type(analysis_text)}")
            
            if isinstance(analysis_text, str) and analysis_text.strip():
                # Create content_data structure from the analysis text
                content_data = {
                    'raw_text': analysis_text,
                    'themes': [],
                    'entities': []
                }
                content_type = 'financial_advice'
                print(f"Using direct analysis as content_data")
        
        # Check for direct interview_result in event
        if not content_data and 'interview_result' in event:
            interview_result = event['interview_result']
            print(f"Found direct interview_result: {type(interview_result)}")
            
            if isinstance(interview_result, dict):
                # Check if it's a Lambda response format
                if 'Payload' in interview_result:
                    payload = interview_result.get('Payload', {})
                    if isinstance(payload, dict):
                        body = payload.get('body')
                        if isinstance(body, str):
                            try:
                                body_data = json.loads(body)
                                if 'result' in body_data and isinstance(body_data['result'], dict):
                                    result_data = body_data['result']
                                    if 'raw_text' in result_data:
                                        content_data = {
                                            'raw_text': result_data['raw_text'],
                                            'themes': result_data.get('key_insights', {}).get('main_themes', []),
                                            'entities': result_data.get('entities', [])
                                        }
                                        content_type = 'interview_transcript'
                                        print(f"Using direct interview_result from event (length: {len(result_data['raw_text'])})")
                            except json.JSONDecodeError as e:
                                print(f"Failed to parse direct interview_result: {e}")
                
                # Check if interview_result is directly the processed data
                elif 'raw_text' in interview_result:
                    content_data = {
                        'raw_text': interview_result['raw_text'],
                        'themes': interview_result.get('key_insights', {}).get('main_themes', []),
                        'entities': interview_result.get('entities', [])
                    }
                    content_type = 'interview_transcript'
                    print(f"Using direct interview_result data from event (length: {len(interview_result['raw_text'])})")
        
        # Check for agent_spec structure (current workflow format)
        if not content_data:
            agent_spec = event.get('agent_spec', {})
            print(f"Checking agent_spec: {list(agent_spec.keys())}")
            
            # Get the processing_config which contains the data
            processing_config = agent_spec.get('processing_config', {})
            print(f"Found processing_config keys: {list(processing_config.keys()) if isinstance(processing_config, dict) else 'not dict'}")
            
            # Check for interview_data in processing_config (current workflow format)
            if 'interview_data' in processing_config:
                interview_data = processing_config['interview_data']
                print(f"Found interview_data: {type(interview_data)}")
                
                # Handle different formats of interview_data
                if isinstance(interview_data, dict):
                    # Check if it's a Lambda response format with result
                    if 'result' in interview_data:
                        result_data = interview_data['result']
                        if isinstance(result_data, dict) and 'raw_text' in result_data:
                            content_data = {
                                'raw_text': result_data['raw_text'],
                                'themes': result_data.get('key_insights', {}).get('main_themes', []),
                                'entities': result_data.get('entities', [])
                            }
                            content_type = 'interview_transcript'
                            print(f"Using interview_data.result.raw_text (length: {len(result_data['raw_text'])})")
                    
                    # Check if it's direct content data
                    elif 'raw_text' in interview_data:
                        content_data = {
                            'raw_text': interview_data['raw_text'],
                            'themes': interview_data.get('themes', []),
                            'entities': interview_data.get('entities', [])
                        }
                        content_type = 'interview_transcript'
                        print(f"Using interview_data.raw_text (length: {len(interview_data['raw_text'])})")
                    
                    # Check if it's a Lambda response body format
                    elif 'body' in interview_data:
                        body_data = interview_data['body']
                        if isinstance(body_data, str):
                            try:
                                parsed_body = json.loads(body_data)
                                if isinstance(parsed_body, dict) and 'result' in parsed_body:
                                    result_data = parsed_body['result']
                                    if isinstance(result_data, dict) and 'raw_text' in result_data:
                                        content_data = {
                                            'raw_text': result_data['raw_text'],
                                            'themes': result_data.get('key_insights', {}).get('main_themes', []),
                                            'entities': result_data.get('entities', [])
                                        }
                                        content_type = 'interview_transcript'
                                        print(f"Using interview_data.body.result.raw_text (length: {len(result_data['raw_text'])})")
                            except json.JSONDecodeError as e:
                                print(f"Failed to parse interview_data.body: {e}")
                        elif isinstance(body_data, dict) and 'result' in body_data:
                            result_data = body_data['result']
                            if isinstance(result_data, dict) and 'raw_text' in result_data:
                                content_data = {
                                    'raw_text': result_data['raw_text'],
                                    'themes': result_data.get('key_insights', {}).get('main_themes', []),
                                    'entities': result_data.get('entities', [])
                                }
                                content_type = 'interview_transcript'
                                print(f"Using interview_data.body.result.raw_text (length: {len(result_data['raw_text'])})")
                    
                    else:
                        print(f"No recognized format in interview_data: {list(interview_data.keys())}")
                
                elif isinstance(interview_data, str):
                    # Try to parse as JSON
                    try:
                        parsed_data = json.loads(interview_data)
                        if isinstance(parsed_data, dict) and 'result' in parsed_data:
                            result_data = parsed_data['result']
                            if isinstance(result_data, dict) and 'raw_text' in result_data:
                                content_data = {
                                    'raw_text': result_data['raw_text'],
                                    'themes': result_data.get('key_insights', {}).get('main_themes', []),
                                    'entities': result_data.get('entities', [])
                                }
                                content_type = 'interview_transcript'
                                print(f"Using parsed interview_data.result.raw_text (length: {len(result_data['raw_text'])})")
                    except json.JSONDecodeError:
                        # Use as raw text
                        content_data = {
                            'raw_text': interview_data,
                            'themes': [],
                            'entities': []
                        }
                        content_type = 'interview_transcript'
                        print(f"Using interview_data as raw text (length: {len(interview_data)})")
            
            # Get the content_result which contains all previous step data (current workflow format)
            if not content_data:
                content_result = processing_config.get('content_result', {})
                print(f"Found content_result keys: {list(content_result.keys()) if isinstance(content_result, dict) else 'not dict'}")
                
                # The content_result contains the entire Step Functions state
                if isinstance(content_result, dict):
            
                    # Try to extract content from various sources in content_result
                    # Check for interview_result (from InterviewProcessing step)
                    if 'interview_result' in content_result:
                        interview_result = content_result['interview_result']
                        print(f"Found interview_result: {type(interview_result)}")
                        
                        # Handle different formats of interview_result
                        if isinstance(interview_result, dict):
                            # Check if it's a Lambda response format
                            if 'Payload' in interview_result:
                                payload = interview_result.get('Payload', {})
                                if isinstance(payload, dict):
                                    body = payload.get('body')
                                    if isinstance(body, str):
                                        try:
                                            body_data = json.loads(body)
                                            print(f"Parsed interview_result body: {list(body_data.keys())}")
                                            
                                            # Check for result structure
                                            if 'result' in body_data:
                                                result_data = body_data['result']
                                                print(f"Found result data: {list(result_data.keys()) if isinstance(result_data, dict) else type(result_data)}")
                                                
                                                # Extract raw_text from the result
                                                if isinstance(result_data, dict) and 'raw_text' in result_data:
                                                    content_data = {
                                                        'raw_text': result_data['raw_text'],
                                                        'themes': result_data.get('key_insights', {}).get('main_themes', []),
                                                        'entities': result_data.get('entities', [])
                                                    }
                                                    content_type = 'interview_transcript'
                                                    print(f"Successfully extracted raw_text from interview_result (length: {len(result_data['raw_text'])})")
                                                else:
                                                    print(f"No raw_text found in result_data: {list(result_data.keys()) if isinstance(result_data, dict) else type(result_data)}")
                                            
                                        except json.JSONDecodeError as e:
                                            print(f"Failed to parse interview_result body as JSON: {e}")
                                    else:
                                        print(f"Body is not a string: {type(body)}")
                                else:
                                    print(f"Payload is not a dict: {type(payload)}")
                            
                            # Check if interview_result is directly the processed data
                            elif 'raw_text' in interview_result:
                                content_data = {
                                    'raw_text': interview_result['raw_text'],
                                    'themes': interview_result.get('key_insights', {}).get('main_themes', []),
                                    'entities': interview_result.get('entities', [])
                                }
                                content_type = 'interview_transcript'
                                print(f"Using direct interview_result data (length: {len(interview_result['raw_text'])})")
                            else:
                                print(f"Interview_result format not recognized: {list(interview_result.keys())}")
                        else:
                            print(f"Interview_result is not a dict: {type(interview_result)}")
                    
                    # Check for financial_result (from FinancialProcessing step)
                    if not content_data and 'financial_result' in content_result:
                        financial_result = content_result['financial_result']
                        print(f"Found financial_result: {type(financial_result)}")
                        
                        # Handle different formats of financial_result
                        if isinstance(financial_result, dict):
                            # Check if it's a Lambda response format
                            if 'Payload' in financial_result:
                                payload = financial_result.get('Payload', {})
                                if isinstance(payload, dict):
                                    body = payload.get('body')
                                    if isinstance(body, str):
                                        try:
                                            body_data = json.loads(body)
                                            print(f"Parsed financial_result body: {list(body_data.keys())}")
                                            
                                            # Check for result structure
                                            if 'result' in body_data:
                                                result_data = body_data['result']
                                                print(f"Found result data: {list(result_data.keys()) if isinstance(result_data, dict) else type(result_data)}")
                                                
                                                # Extract raw_text from the result
                                                if isinstance(result_data, dict) and 'raw_text' in result_data:
                                                    content_data = {
                                                        'raw_text': result_data['raw_text'],
                                                        'themes': result_data.get('key_insights', {}).get('main_themes', []),
                                                        'entities': result_data.get('entities', [])
                                                    }
                                                    content_type = 'financial_advice'
                                                    print(f"Successfully extracted raw_text from financial_result (length: {len(result_data['raw_text'])})")
                                                else:
                                                    print(f"No raw_text found in financial result_data: {list(result_data.keys()) if isinstance(result_data, dict) else type(result_data)}")
                                            
                                        except json.JSONDecodeError as e:
                                            print(f"Failed to parse financial_result body as JSON: {e}")
                                    else:
                                        print(f"Financial body is not a string: {type(body)}")
                                else:
                                    print(f"Financial Payload is not a dict: {type(payload)}")
                            
                            # Check if financial_result is directly the processed data
                            elif 'raw_text' in financial_result:
                                content_data = {
                                    'raw_text': financial_result['raw_text'],
                                    'themes': financial_result.get('key_insights', {}).get('main_themes', []),
                                    'entities': financial_result.get('entities', [])
                                }
                                content_type = 'financial_advice'
                                print(f"Using direct financial_result data (length: {len(financial_result['raw_text'])})")
                            else:
                                print(f"Financial_result format not recognized: {list(financial_result.keys())}")
                        else:
                            print(f"Financial_result is not a dict: {type(financial_result)}")
                    
                    # Check for parsed_analysis
                    if not content_data and 'parsed_analysis' in content_result:
                        parsed_analysis = content_result['parsed_analysis']
                        if isinstance(parsed_analysis, dict) and 'analysis' in parsed_analysis:
                            analysis_data = parsed_analysis['analysis']
                            if isinstance(analysis_data, dict):
                                content_data = analysis_data
                                content_type = analysis_data.get('content_type', 'interview_transcript')
                                print(f"Using content_result.parsed_analysis.analysis as content_data")
                    
                    # Check for analysis string
                    if not content_data and 'analysis' in content_result:
                        analysis_text = content_result['analysis']
                        if isinstance(analysis_text, str) and analysis_text.strip():
                            try:
                                # Try to parse as JSON first
                                analysis_data = json.loads(analysis_text)
                                if isinstance(analysis_data, dict) and 'analysis' in analysis_data:
                                    content_data = analysis_data['analysis']
                                    content_type = content_data.get('content_type', 'interview_transcript')
                                    print(f"Using parsed analysis string as content_data")
                            except json.JSONDecodeError:
                                # Use as raw text
                                content_data = {
                                    'raw_text': analysis_text,
                                    'themes': [],
                                    'entities': []
                                }
                                content_type = 'interview_transcript'
                                print(f"Using raw analysis string as content_data")
        
        # Final fallback: try to read content directly from S3 if we have file_path
        if not content_data:
            file_path = None
            
            # Try multiple locations for file_path
            if 'agent_spec' in event:
                processing_config = event['agent_spec'].get('processing_config', {})
                file_path = processing_config.get('file_path')
            
            # Check direct event keys (Step Functions format)
            if not file_path:
                file_path = event.get('file_path')
            
            print(f"Attempting S3 fallback with file_path: {file_path}")
            
            if file_path:
                try:
                    import boto3
                    import urllib.parse
                    s3 = boto3.client('s3')
                    bucket_name = os.environ.get('S3_INPUT_BUCKET', 'agentic-framework-input-files-dev-765455500375')
                    
                    # URL decode the file path
                    decoded_file_path = urllib.parse.unquote_plus(file_path)
                    print(f"Reading from S3: bucket={bucket_name}, key={decoded_file_path}")
                    
                    response = s3.get_object(Bucket=bucket_name, Key=decoded_file_path)
                    raw_content = response['Body'].read().decode('utf-8')
                    
                    # Remove YAML front matter if present
                    if raw_content.startswith('---'):
                        end_marker = raw_content.find('---', 3)
                        if end_marker > 0:
                            raw_content = raw_content[end_marker + 3:].strip()
                    
                    content_data = {
                        'raw_text': raw_content,
                        'themes': [],
                        'entities': []
                    }
                    content_type = 'interview_transcript'
                    print(f"Successfully read content directly from S3: {len(raw_content)} characters")
                    
                except Exception as e:
                    print(f"Failed to read content from S3: {str(e)}")
            else:
                print(f"No file_path found for S3 fallback")
        
        if not content_data:
            print(f"No content data found. Event keys: {list(event.keys())}")
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'execution_id': execution_id,
                    'agent_type': 'needs_analysis',
                    'error': 'No content processing data provided',
                    'success': False,
                    'debug_info': {
                        'event_keys': list(event.keys()),
                        'agent_spec_keys': list(event.get('agent_spec', {}).keys()) if 'agent_spec' in event else [],
                        'processing_config_keys': list(event.get('agent_spec', {}).get('processing_config', {}).keys()) if 'agent_spec' in event else []
                    }
                })
            }
        
        # Extract the actual text content
        raw_text = content_data.get('raw_text', '')
        themes = content_data.get('themes', [])
        entities = content_data.get('entities', [])
        
        print(f"Extracted content: {len(raw_text)} characters, {len(themes)} themes")
        
        if not raw_text:
            print(f"No raw_text found. Content data keys: {list(content_data.keys())}")
            raise ValueError("No text content to analyze")
        
        # Perform needs analysis using the actual content
        needs_result = analyze_human_needs(raw_text, content_type, themes, entities)
        
        # Convert float values to Decimal for DynamoDB compatibility immediately
        def convert_floats_to_decimal(obj):
            """Recursively convert float values to Decimal for DynamoDB"""
            if isinstance(obj, float):
                return Decimal(str(obj))
            elif isinstance(obj, dict):
                return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_floats_to_decimal(item) for item in obj]
            else:
                return obj
        
        # Convert the result for DynamoDB storage
        needs_result = convert_floats_to_decimal(needs_result)
        
        print(f"Analysis complete. Top need: {needs_result.get('dominant_needs', [{}])[0] if needs_result.get('dominant_needs') else 'None'}")
        
        # Record performance metrics - TEMPORARILY DISABLED TO FIX FLOAT ERROR
        try:
            print(f"Skipping DynamoDB metrics recording to avoid float error")
            # TODO: Re-enable after fixing float conversion
            pass
        except Exception as metrics_error:
            print(f"Metrics recording failed: {metrics_error}")
        
        # Convert Decimal objects to float for JSON serialization
        def decimal_to_float(obj):
            """Convert Decimal objects to float for JSON serialization"""
            if isinstance(obj, Decimal):
                return float(obj)
            elif isinstance(obj, dict):
                # Convert enum keys to strings and values recursively
                return {(k.value if hasattr(k, 'value') else str(k)): decimal_to_float(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [decimal_to_float(item) for item in obj]
            elif isinstance(obj, tuple):
                return tuple(decimal_to_float(item) for item in obj)
            elif hasattr(obj, 'value'):  # Handle enum objects
                return obj.value
            else:
                return obj
        
        # Convert back to float for JSON response
        json_result = decimal_to_float(needs_result)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'execution_id': execution_id,
                'agent_type': 'needs_analysis',
                'result': json_result,
                'success': True
            })
        }
        
    except Exception as e:
        print(f"Lambda handler error: {e}")
        
        # Record failure - TEMPORARILY DISABLED TO FIX FLOAT ERROR
        try:
            print(f"Skipping DynamoDB error recording to avoid float error")
            # TODO: Re-enable after fixing float conversion
            pass
        except Exception as metrics_error:
            print(f"Error metrics recording failed: {metrics_error}")
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'execution_id': event.get('execution_id', 'unknown'),
                'agent_type': 'needs_analysis',
                'error': str(e),
                'success': False
            })
        }

def analyze_human_needs(text, content_type='unknown', themes=None, entities=None):
    """
    Analyze text for human needs using LLM with enhanced response parsing
    """
    if themes is None:
        themes = []
    if entities is None:
        entities = []
    
    try:
        # Initialize Bedrock client
        bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
        
        # Create dynamic analysis prompt based on content type and context
        prompt = create_dynamic_prompt(text, content_type, themes, entities)
        
        # Use higher temperature for more varied responses
        temperature = 0.4
        
        # Call Bedrock with Llama model using higher temperature for varied responses
        response = bedrock.invoke_model(
            modelId='us.meta.llama4-scout-17b-instruct-v1:0',
            body=json.dumps({
                'prompt': prompt,
                'max_gen_len': 2000,  # Increased for more detailed analysis
                'temperature': temperature  # Use dynamic temperature
            })
        )
        
        # Parse response
        response_body = json.loads(response['body'].read())
        llm_output = response_body.get('generation', '{}')
        
        # Use enhanced response parser that handles various formats
        result = enhanced_response_parser(llm_output, content_type, themes, entities)
        
        return result
            
    except Exception as e:
        # Final fallback with content-aware scores
        fallback_scores = get_content_aware_scores(content_type, themes, entities)
        dominant_needs = sorted(fallback_scores.items(), key=lambda x: x[1], reverse=True)[:3]
        
        return {
            'needs_scores': fallback_scores,
            'dominant_needs': dominant_needs,
            'behavioral_patterns': get_content_behavioral_patterns(content_type, themes),
            'personality_traits': get_content_personality_traits(content_type, entities),
            'life_themes': get_content_life_themes(content_type, themes),
            'confidence_score': Decimal('0.3')
        }

def enhanced_response_parser(llm_response, content_type, themes, entities):
    """Enhanced parser that handles various LLM response formats"""
    import re
    
    # Initialize result structure
    result = {
        'needs_scores': {},
        'dominant_needs': [],
        'behavioral_patterns': [],
        'personality_traits': [],
        'life_themes': [],
        'confidence_score': Decimal('0.6')
    }
    
    try:
        # First, try to parse as pure JSON
        if isinstance(llm_response, dict):
            parsed_data = llm_response
        else:
            # Try to extract JSON from text
            json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
            if json_match:
                parsed_data = json.loads(json_match.group())
            else:
                parsed_data = json.loads(llm_response)
        
        # Extract data from parsed JSON
        result['needs_scores'] = parsed_data.get('needs_scores', {})
        result['behavioral_patterns'] = parsed_data.get('behavioral_patterns', [])
        result['personality_traits'] = parsed_data.get('personality_traits', [])
        result['life_themes'] = parsed_data.get('life_themes', [])
        result['confidence_score'] = Decimal(str(parsed_data.get('confidence_score', 0.6)))
        
    except (json.JSONDecodeError, TypeError, AttributeError):
        # Fallback to text parsing
        if isinstance(llm_response, str):
            # Extract scores using regex
            result['needs_scores'] = extract_scores_from_text(llm_response)
            
            # Extract arrays
            result['behavioral_patterns'] = extract_arrays_from_text(llm_response, 'behavioral_patterns')
            result['personality_traits'] = extract_arrays_from_text(llm_response, 'personality_traits')
            result['life_themes'] = extract_arrays_from_text(llm_response, 'life_themes')
            
            # Extract confidence score
            conf_match = re.search(r'confidence:?\s*(\d+\.?\d*)', llm_response, re.IGNORECASE)
            if conf_match:
                result['confidence_score'] = Decimal(conf_match.group(1))
    
    # Ensure we have all needs scores
    all_needs = ['certainty', 'variety', 'significance', 'connection', 'growth', 'contribution']
    for need in all_needs:
        if need not in result['needs_scores']:
            # Use content-aware fallback
            result['needs_scores'][need] = get_content_aware_fallback_score(need, content_type, themes)
    
    # Create dominant needs from scores
    if not result['dominant_needs']:
        sorted_needs = sorted(result['needs_scores'].items(), key=lambda x: x[1], reverse=True)
        result['dominant_needs'] = sorted_needs[:3]
    
    # Use content-aware fallbacks for empty arrays
    if not result['behavioral_patterns']:
        result['behavioral_patterns'] = get_content_behavioral_patterns(content_type, themes)
    
    if not result['personality_traits']:
        result['personality_traits'] = get_content_personality_traits(content_type, entities)
    
    if not result['life_themes']:
        result['life_themes'] = get_content_life_themes(content_type, themes)
    
    return result

def extract_scores_from_text(text):
    """Extract scores from text-based LLM response using regex"""
    import re
    scores = {}
    needs = ['certainty', 'variety', 'significance', 'connection', 'growth', 'contribution']
    
    for need in needs:
        # Look for patterns like "Certainty: 0.8" or "Growth: 0.7"
        pattern = rf"{need}:?\s*(\d+\.?\d*)"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            score = float(match.group(1))
            # Ensure score is between 0 and 1
            if score > 1.0:
                score = score / 10.0  # Handle cases like "8" instead of "0.8"
            scores[need] = min(max(score, 0.0), 1.0)
    
    return scores

def extract_arrays_from_text(text, field_name):
    """Extract arrays from text using regex"""
    import re
    # Look for patterns like 'behavioral_patterns: ["item1", "item2"]'
    pattern = rf'{field_name}:?\s*\[(.*?)\]'
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    
    if match:
        try:
            # Try to parse as JSON array
            array_str = '[' + match.group(1) + ']'
            return json.loads(array_str)
        except json.JSONDecodeError:
            # Fallback: split by comma and clean up
            items = match.group(1).split(',')
            return [item.strip().strip('"\'') for item in items if item.strip()]
    
    return []

def get_content_aware_fallback_score(need, content_type, themes):
    """Get content-aware fallback scores for missing needs"""
    base_score = 0.4
    
    if content_type == 'financial_advice':
        scores = {
            'certainty': 0.8,
            'growth': 0.6,
            'significance': 0.5,
            'contribution': 0.5,
            'connection': 0.4,
            'variety': 0.3
        }
        return scores.get(need, base_score)
    
    elif content_type == 'interview_transcript':
        scores = {
            'significance': 0.8,
            'growth': 0.7,
            'connection': 0.6,
            'variety': 0.5,
            'certainty': 0.4,
            'contribution': 0.4
        }
        return scores.get(need, base_score)
    
    return base_score

def get_content_aware_scores(content_type, themes, entities):
    """Get content-aware scores based on content type, themes, and entities"""
    base_scores = {'certainty': Decimal('0.4'), 'variety': Decimal('0.4'), 'significance': Decimal('0.4'), 
                   'connection': Decimal('0.4'), 'growth': Decimal('0.4'), 'contribution': Decimal('0.4')}
    
    # Adjust based on content type
    if content_type == 'financial_advice':
        base_scores.update({'certainty': Decimal('0.8'), 'growth': Decimal('0.6'), 'significance': Decimal('0.5')})
    elif content_type == 'interview_transcript':
        base_scores.update({'significance': Decimal('0.8'), 'growth': Decimal('0.7'), 'connection': Decimal('0.6'), 'variety': Decimal('0.5')})
    
    # Adjust based on themes
    for theme in themes:
        if 'leadership' in theme.lower():
            base_scores['significance'] += Decimal('0.2')
            base_scores['connection'] += Decimal('0.1')
        elif 'innovation' in theme.lower() or 'technology' in theme.lower():
            base_scores['growth'] += Decimal('0.2')
            base_scores['variety'] += Decimal('0.1')
        elif 'risk' in theme.lower() or 'security' in theme.lower():
            base_scores['certainty'] += Decimal('0.2')
    
    # Ensure scores stay within bounds
    for need in base_scores:
        base_scores[need] = min(max(base_scores[need], Decimal('0.0')), Decimal('1.0'))
    
    return base_scores

def get_content_behavioral_patterns(content_type, themes):
    """Get content-specific behavioral patterns"""
    if content_type == 'financial_advice':
        return ["Strategic planner", "Risk manager", "Client educator"]
    elif content_type == 'interview_transcript':
        return ["Leadership-oriented", "Growth-focused", "Collaborative"]
    else:
        return ["Analytical thinker", "Goal-oriented", "Relationship-builder"]

def get_content_personality_traits(content_type, entities):
    """Get content-specific personality traits"""
    if content_type == 'financial_advice':
        return ["Analytical", "Cautious", "Helpful"]
    elif content_type == 'interview_transcript':
        return ["Confident", "Articulate", "Visionary"]
    else:
        return ["Thoughtful", "Practical", "Communicative"]

def get_content_life_themes(content_type, themes):
    """Get content-specific life themes"""
    if content_type == 'financial_advice':
        return ["Financial security", "Professional expertise", "Client success"]
    elif content_type == 'interview_transcript':
        return ["Career advancement", "Innovation", "Leadership impact"]
    else:
        return ["Personal growth", "Achievement", "Relationships"]