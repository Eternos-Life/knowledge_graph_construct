import boto3
import json
import re
import os
import urllib.parse
from typing import Dict, List, Any

class FileAnalyzer:
    def __init__(self):
        self.s3 = boto3.client('s3')
    
    def analyze_file(self, file_path: str, customer_folder: str) -> Dict[str, Any]:
        """Analyze file to determine processing requirements"""
        
        # URL decode the file path to handle special characters
        decoded_file_path = urllib.parse.unquote_plus(file_path)
        
        file_extension = decoded_file_path.split('.')[-1].lower() if '.' in decoded_file_path else 'unknown'
        
        try:
            bucket_name = os.environ.get('S3_INPUT_BUCKET', 'agentic-framework-input-files-dev-765455500375')
            # Try with the decoded path first
            try:
                response = self.s3.get_object(Bucket=bucket_name, Key=decoded_file_path)
            except:
                # If that fails, try with the original path
                response = self.s3.get_object(Bucket=bucket_name, Key=file_path)
            content = response['Body'].read().decode('utf-8')
        except Exception as e:
            return {
                'error': f'Failed to read file: {str(e)}',
                'file_path': file_path,
                'decoded_path': decoded_file_path
            }
        
        metadata = self.extract_metadata_from_content(content)
        complexity = self.analyze_content_complexity(content)
        required_agents = self.determine_required_agents(content, metadata)
        
        return {
            'file_path': file_path,
            'decoded_path': decoded_file_path,
            'file_type': file_extension,
            'content_type': metadata.get('content_type', 'interview_transcript'),
            'complexity_score': complexity,
            'required_agents': required_agents,
            'metadata': metadata,
            'content_analysis': {
                'content_type': metadata.get('content_type', 'interview_transcript'),
                'word_count': len(content.split()),
                'character_count': len(content),
                'language': metadata.get('language', 'english')
            },
            'requirements': {
                'processing_depth': 'detailed' if complexity > 0.7 else 'standard',
                'estimated_time': complexity * 60,
                'priority': 'high' if complexity > 0.8 else 'normal'
            }
        }
    
    def extract_metadata_from_content(self, content: str) -> Dict[str, Any]:
        """Extract metadata from file content header"""
        metadata = {}
        
        if content.startswith('---'):
            try:
                end_marker = content.find('---', 3)
                if end_marker > 0:
                    metadata_text = content[3:end_marker].strip()
                    metadata = json.loads(metadata_text)
            except:
                pass
        
        metadata.setdefault('content_type', 'interview_transcript')
        metadata.setdefault('language', 'english')
        metadata.setdefault('domain', 'general')
        
        return metadata
    
    def analyze_content_complexity(self, content: str) -> float:
        """Analyze content complexity (0.0 to 1.0)"""
        
        word_count = len(content.split())
        sentence_count = len(re.split(r'[.!?]+', content))
        paragraph_count = len(content.split('\n\n'))
        
        speaker_pattern = r'^([A-Za-z\s]+):\s*'
        speakers = set(re.findall(speaker_pattern, content, re.MULTILINE))
        speaker_count = len(speakers)
        
        word_complexity = min(word_count / 2000, 1.0) * 0.3
        structure_complexity = min(speaker_count / 5, 1.0) * 0.3
        length_complexity = min(paragraph_count / 20, 1.0) * 0.2
        
        technical_keywords = ['technology', 'software', 'engineering', 'development', 'system', 'algorithm']
        technical_score = sum(1 for keyword in technical_keywords if keyword in content.lower()) / len(technical_keywords)
        technical_complexity = technical_score * 0.2
        
        total_complexity = word_complexity + structure_complexity + length_complexity + technical_complexity
        return min(total_complexity, 1.0)
    
    def determine_required_agents(self, content: str, metadata: Dict) -> List[str]:
        """Determine which agents are required for processing"""
        
        agents = ['interview_processing']
        
        if len(content.split()) > 50:
            agents.append('nlp_processing')
        
        if metadata.get('content_type') == 'interview_transcript':
            agents.append('needs_analysis')
        
        agents.append('hypergraph_builder')
        
        return agents

def lambda_handler(event, context):
    """AWS Lambda handler"""
    
    analyzer = FileAnalyzer()
    
    try:
        file_path = event['file_path']
        customer_folder = event['customer_folder']
        
        result = analyzer.analyze_file(file_path, customer_folder)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'analysis': result,
                'success': True
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'success': False
            })
        }
