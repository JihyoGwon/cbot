"""Vertex AI LLM 서비스 모듈"""
import os
from typing import List, Dict, Optional
from langchain_google_vertexai import ChatVertexAI
from config import Config


class LLMService:
    """Vertex AI를 사용한 LLM 서비스"""
    
    def __init__(self):
        """LLM 서비스 초기화"""
        if Config.GOOGLE_APPLICATION_CREDENTIALS and os.path.exists(Config.GOOGLE_APPLICATION_CREDENTIALS):
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = Config.GOOGLE_APPLICATION_CREDENTIALS
        
        self.llm = ChatVertexAI(
            model_name=Config.VERTEX_AI_MODEL,
            project=Config.PROJECT_ID,
            location=Config.LOCATION,
            temperature=0.8,  # 상담에 맞게 약간 높임 (더 자연스러운 대화)
        )
    
    def chat(self, message: str, conversation_history: Optional[List[Dict]] = None) -> str:
        """
        LLM과 대화하기
        
        Args:
            message: 사용자 메시지
            conversation_history: 이전 대화 기록 (선택사항)
            
        Returns:
            LLM 응답
        """
        try:
            # 메시지 리스트 초기화 (시스템 프롬프트로 시작)
            messages = []
            
            # 시스템 프롬프트 추가 (Gemini는 system 역할을 지원)
            # 기본 상담 프롬프트 사용 (간단한 LLM 서비스용)
            basic_prompt = """당신은 전문적인 상담 에이전트입니다. 사용자의 감정과 상황을 깊이 이해하고, 진심으로 공감하세요. 반말을 사용하고, 비판하지 말고 이해와 지지에 집중하세요."""
            messages.append(('system', basic_prompt))
            
            # 대화 기록이 있으면 포함
            if conversation_history:
                for msg in conversation_history:
                    if msg.get('role') == 'user':
                        messages.append(('user', msg.get('content', '')))
                    elif msg.get('role') == 'assistant':
                        messages.append(('assistant', msg.get('content', '')))
            
            # 현재 메시지 추가
            messages.append(('user', message))
            
            # LLM 호출
            response = self.llm.invoke(messages)
            
            return response.content if hasattr(response, 'content') else str(response)
            
        except Exception as e:
            raise Exception(f"LLM 호출 중 오류 발생: {str(e)}")

