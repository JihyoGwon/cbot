"""설정 관리 모듈"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """애플리케이션 설정"""
    
    # Flask 설정
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Google Cloud 설정
    GOOGLE_APPLICATION_CREDENTIALS = os.getenv(
        'GOOGLE_APPLICATION_CREDENTIALS', 
        'vertex-ai-cbot-key.json'
    )
    PROJECT_ID = os.getenv('PROJECT_ID', '')
    LOCATION = os.getenv('LOCATION', 'us-central1')
    
    # Vertex AI 설정
    VERTEX_AI_MODEL = os.getenv('VERTEX_AI_MODEL', 'gemini-2.5-flash')
    
    # Firestore 설정
    FIRESTORE_COLLECTION = os.getenv('FIRESTORE_COLLECTION', 'conversations')
    
    # 상담 에이전트 설정
    SUPERVISION_INTERVAL = int(os.getenv('SUPERVISION_INTERVAL', 3))  # N개 메시지마다 supervision
    TASK_UPDATE_INTERVAL = int(os.getenv('TASK_UPDATE_INTERVAL', 3))  # N개 메시지마다 task 업데이트

