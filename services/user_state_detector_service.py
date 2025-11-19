"""User State Detector Service - 사용자 상태 감지"""
import os
from typing import Dict, List
from langchain_google_vertexai import ChatVertexAI
from config import Config


class UserStateDetectorService:
    """User State Detector - 사용자 저항, 감정, 주제 변경 등 감지"""
    
    def __init__(self):
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = Config.GOOGLE_APPLICATION_CREDENTIALS
        
        self.llm = ChatVertexAI(
            model_name=Config.VERTEX_AI_MODEL,
            project=Config.PROJECT_ID,
            location=Config.LOCATION,
            temperature=0.5,
            max_output_tokens=300,
            model_kwargs={"thinking_budget": 0}
        )
    
    def get_system_prompt(self) -> str:
        """User State Detector 시스템 프롬프트"""
        return """당신은 사용자의 상태를 감지하는 전문가입니다. 대화 내용을 분석하여 다음을 감지하세요:

1. **저항 (Resistance)**: 사용자가 상담에 저항하거나 회피하는 행동
2. **감정 변화 (Emotion Change)**: 긍정적/부정적 감정 변화
3. **주제 변경 (Topic Change)**: 대화 주제가 바뀌었는지
4. **빙빙 도는 대화 (Circular Conversation)**: 같은 주제를 반복하는지

**응답 형식:**
RESISTANCE_DETECTED: [True|False]
EMOTION_CHANGE: [positive|negative|neutral|None]
TOPIC_CHANGE: [True|False]
CIRCULAR_CONVERSATION: [True|False]
USER_STATE_SUMMARY: [상태 요약]"""
    
    def detect_state(self, conversation_history: List[Dict]) -> Dict:
        """
        사용자 상태 감지
        
        Args:
            conversation_history: 대화 기록
            
        Returns:
            {
                "resistance_detected": bool,
                "emotion_change": "positive" | "negative" | "neutral" | None,
                "topic_change": bool,
                "circular_conversation": bool,
                "user_state_summary": str
            }
        """
        # 최근 대화 요약
        recent_messages = conversation_history[-10:] if len(conversation_history) > 10 else conversation_history
        conversation_context = "\n".join([
            f"{msg.get('role')}: {msg.get('content', '')[:200]}"
            for msg in recent_messages
        ])
        
        prompt = f"""다음은 최근 대화 내용입니다.

{conversation_context}

위 대화를 분석하여 사용자의 상태를 감지하세요.

{self.get_system_prompt()}"""
        
        messages = [
            ('system', self.get_system_prompt()),
            ('user', prompt)
        ]
        
        try:
            response = self.llm.invoke(messages)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # 응답 파싱
            result = {
                "resistance_detected": False,
                "emotion_change": None,
                "topic_change": False,
                "circular_conversation": False,
                "user_state_summary": ""
            }
            
            for line in response_text.split('\n'):
                if 'RESISTANCE_DETECTED:' in line.upper():
                    value = line.split(':', 1)[1].strip().lower()
                    result["resistance_detected"] = value == 'true'
                elif 'EMOTION_CHANGE:' in line.upper():
                    value = line.split(':', 1)[1].strip().lower()
                    if value in ['positive', 'negative', 'neutral']:
                        result["emotion_change"] = value
                elif 'TOPIC_CHANGE:' in line.upper():
                    value = line.split(':', 1)[1].strip().lower()
                    result["topic_change"] = value == 'true'
                elif 'CIRCULAR_CONVERSATION:' in line.upper():
                    value = line.split(':', 1)[1].strip().lower()
                    result["circular_conversation"] = value == 'true'
                elif 'USER_STATE_SUMMARY:' in line.upper():
                    result["user_state_summary"] = line.split(':', 1)[1].strip()
            
            return result
        
        except Exception as e:
            print(f"User State Detector 오류: {str(e)}")
            return {
                "resistance_detected": False,
                "emotion_change": None,
                "topic_change": False,
                "circular_conversation": False,
                "user_state_summary": "감지 오류"
            }

