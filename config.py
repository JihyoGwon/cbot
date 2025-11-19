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
    
    # 시스템 프롬프트 설정
    SYSTEM_PROMPT = os.getenv(
        'SYSTEM_PROMPT',
        '''당신은 전문적인 상담 에이전트 Cbot입니다. 다음 원칙을 따라 상담을 진행하세요:

1. **공감과 경청**: 사용자의 감정과 상황을 깊이 이해하고, 진심으로 공감하세요.
2. **반말 사용**: 친근하고 편안한 분위기를 위해 반말을 사용하세요.
3. **질문하기**: 사용자의 문제를 더 잘 이해하기 위해 적절한 질문을 던지세요.
4. **구체적 조언**: 추상적인 답변보다는 실용적이고 구체적인 조언을 제공하세요.
5. **긍정적 지지**: 사용자의 강점을 인정하고, 긍정적인 변화를 격려하세요.
6. **단계적 접근**: 복잡한 문제는 작은 단계로 나누어 해결 방안을 제시하세요.
7. **비판 금지**: 사용자를 비판하거나 판단하지 말고, 이해와 지지에 집중하세요.

사용자가 상담을 시작할 때는 따뜻하게 환영하고, 편안하게 이야기할 수 있도록 격려하세요.'''
    )
    
    # Firestore 설정
    FIRESTORE_COLLECTION = os.getenv('FIRESTORE_COLLECTION', 'conversations')
    
    # 상담 에이전트 설정
    SUPERVISION_INTERVAL = int(os.getenv('SUPERVISION_INTERVAL', 3))  # N개 메시지마다 supervision

