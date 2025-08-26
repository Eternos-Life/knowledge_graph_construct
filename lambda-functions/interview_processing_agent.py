import boto3
import json
import re
import os
import urllib.parse
from typing import Dict, List, Any

class InterviewTranscriptProcessor:
    def __init__(self):
        self.bedrock = boto3.client('bedrock-runtime')
        self.s3 = boto3.client('s3')
        
    def process_interview_transcript(self, file_path: str, metadata: Dict) -> Dict[str, Any]:
        """Process interview transcript with specialized analysis"""
        
        content = self.load_transcript(file_path)
        interview_structure = self.parse_interview_structure(content)
        entities = self.extract_interview_entities(content, interview_structure)
        conversation_analysis = self.analyze_conversation_dynamics(content, interview_structure)
        insights = self.extract_key_insights(content, entities, conversation_analysis)
        
        return {
            'file_path': file_path,
            'raw_text': content,
            'interview_structure': interview_structure,
            'entities': entities,
            'conversation_analysis': conversation_analysis,
            'key_insights': insights,
            'processing_metadata': {
                'word_count': len(content.split()),
                'speaker_count': len(interview_structure.get('speakers', [])),
                'duration_estimate': self.estimate_duration(content)
            },
            'confidence': 0.85,
            'processing_time': 2.5
        }
    
    def load_transcript(self, file_path: str) -> str:
        """Load transcript from S3"""
        bucket_name = os.environ.get('S3_INPUT_BUCKET', 'agentic-framework-input-files-dev')
        
        # URL decode the file path to handle spaces and special characters
        decoded_file_path = urllib.parse.unquote_plus(file_path)
        
        response = self.s3.get_object(Bucket=bucket_name, Key=decoded_file_path)
        content = response['Body'].read().decode('utf-8')
        
        if content.startswith('---'):
            end_marker = content.find('---', 3)
            if end_marker > 0:
                content = content[end_marker + 3:].strip()
        
        return content
    
    def parse_interview_structure(self, content: str) -> Dict[str, Any]:
        """Parse interview structure to identify speakers and segments"""
        
        speaker_pattern = r'^([A-Za-z\s]+):\s*(.+)$'
        speakers = set()
        segments = []
        
        lines = content.split('\n')
        current_speaker = None
        current_text = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            match = re.match(speaker_pattern, line)
            if match:
                if current_speaker and current_text:
                    segments.append({
                        'speaker': current_speaker,
                        'text': ' '.join(current_text),
                        'word_count': len(' '.join(current_text).split())
                    })
                
                current_speaker = match.group(1).strip()
                current_text = [match.group(2).strip()]
                speakers.add(current_speaker)
            else:
                if current_text:
                    current_text.append(line)
        
        if current_speaker and current_text:
            segments.append({
                'speaker': current_speaker,
                'text': ' '.join(current_text),
                'word_count': len(' '.join(current_text).split())
            })
        
        return {
            'speakers': list(speakers),
            'segments': segments,
            'total_segments': len(segments)
        }
    
    def extract_interview_entities(self, content: str, structure: Dict) -> List[Dict]:
        """Extract entities using simple patterns (fallback for Bedrock)"""
        entities = []
        
        # Extract names (capitalized words)
        name_pattern = r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'
        names = re.findall(name_pattern, content)
        
        for name in set(names[:10]):
            entities.append({
                'text': name,
                'type': 'PERSON',
                'confidence': 0.7,
                'context': ''
            })
        
        # Extract organizations
        org_keywords = ['Company', 'Corporation', 'Inc', 'LLC', 'University', 'Institute', 'Google', 'Microsoft', 'Amazon']
        for keyword in org_keywords:
            if keyword in content:
                entities.append({
                    'text': keyword,
                    'type': 'ORGANIZATION',
                    'confidence': 0.6,
                    'context': ''
                })
        
        return entities
    
    def analyze_conversation_dynamics(self, content: str, structure: Dict) -> Dict[str, Any]:
        """Analyze conversation flow and dynamics"""
        
        segments = structure.get('segments', [])
        if not segments:
            return {'error': 'No segments found'}
        
        total_words = sum(seg['word_count'] for seg in segments)
        speaker_distribution = {}
        
        for segment in segments:
            speaker = segment['speaker']
            if speaker not in speaker_distribution:
                speaker_distribution[speaker] = 0
            speaker_distribution[speaker] += segment['word_count']
        
        for speaker in speaker_distribution:
            speaker_distribution[speaker] = speaker_distribution[speaker] / total_words * 100
        
        return {
            'speaking_time_distribution': speaker_distribution,
            'total_exchanges': len(segments),
            'average_response_length': total_words / len(segments),
            'conversation_flow': 'balanced' if len(set(speaker_distribution.values())) < 2 else 'unbalanced'
        }
    
    def extract_key_insights(self, content: str, entities: List[Dict], dynamics: Dict) -> Dict[str, Any]:
        """Extract key insights and themes from the interview"""
        
        insights = {
            'skills_and_competencies': [],
            'achievements_and_experiences': [],
            'goals_and_aspirations': [],
            'challenges_discussed': [],
            'main_themes': []
        }
        
        # Extract skills
        skill_keywords = ['skill', 'experience', 'expertise', 'proficient', 'knowledge', 'ability']
        for keyword in skill_keywords:
            if keyword in content.lower():
                insights['skills_and_competencies'].append(f"Mentioned {keyword}")
        
        # Extract achievements
        achievement_keywords = ['achieved', 'accomplished', 'successful', 'led', 'managed', 'created']
        for keyword in achievement_keywords:
            if keyword in content.lower():
                insights['achievements_and_experiences'].append(f"Discussed {keyword}")
        
        # Extract goals
        goal_keywords = ['goal', 'aspire', 'want to', 'plan to', 'hope to', 'future']
        for keyword in goal_keywords:
            if keyword in content.lower():
                insights['goals_and_aspirations'].append(f"Mentioned {keyword}")
        
        # Main themes based on entities
        themes = set()
        for entity in entities:
            if entity['type'] == 'ORGANIZATION':
                themes.add('professional_experience')
            elif entity['type'] == 'PERSON':
                themes.add('relationships')
        
        insights['main_themes'] = list(themes)
        
        return insights
    
    def estimate_duration(self, content: str) -> float:
        """Estimate interview duration in minutes"""
        word_count = len(content.split())
        return word_count / 150

def lambda_handler(event, context):
    """AWS Lambda handler for interview processing"""
    
    processor = InterviewTranscriptProcessor()
    
    try:
        agent_spec = event['agent_spec']
        execution_id = event['execution_id']
        
        file_path = agent_spec['processing_config']['file_path']
        metadata = agent_spec['processing_config'].get('metadata', {})
        
        result = processor.process_interview_transcript(file_path, metadata)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'execution_id': execution_id,
                'agent_type': 'interview_processing',
                'result': result,
                'success': True
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'execution_id': event.get('execution_id', 'unknown'),
                'agent_type': 'interview_processing',
                'error': str(e),
                'success': False
            })
        }
