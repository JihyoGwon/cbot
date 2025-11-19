"""Supervisor LLM 서비스 - 상담 품질 모니터링 및 피드백"""
import os
from typing import List, Dict, Optional
from langchain_google_vertexai import ChatVertexAI
from config import Config


class SupervisorService:
    """Supervisor LLM - 메인 상담사의 응답 품질 평가 및 피드백"""
    
    def __init__(self):
        """Supervisor 초기화"""
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = Config.GOOGLE_APPLICATION_CREDENTIALS
        
        self.llm = ChatVertexAI(
            model_name=Config.VERTEX_AI_MODEL,
            project=Config.PROJECT_ID,
            location=Config.LOCATION,
            temperature=0.5,  # 평가는 객관적이어야 함
        )
    
    def get_system_prompt(self) -> str:
        """Supervisor 시스템 프롬프트"""
        return """당신은 전문 상담 수퍼바이저입니다. 메인 상담사의 응답을 평가하고 피드백을 제공하세요.

평가 기준:
1. **공감 수준**: 사용자의 감정을 얼마나 잘 이해하고 공감했는가?
2. **적절한 질문**: 상황에 맞는 질문을 던졌는가?
3. **비판/판단 회피**: 사용자를 비판하거나 판단하지 않았는가?
4. **구체적 조언**: 추상적이지 않고 실용적인 조언을 제공했는가?
5. **반말 사용**: 친근하고 편안한 반말을 사용했는가?
6. **Task 준수**: 현재 task의 목표를 달성하려고 노력했는가?

피드백은 건설적이고 구체적으로 제공하세요."""
    
    def evaluate_response(self, user_message: str, counselor_response: str,
                         current_task: Optional[Dict], conversation_history: List[Dict]) -> Dict:
        """
        상담사 응답 평가
        
        Args:
            user_message: 사용자 메시지
            counselor_response: 상담사 응답
            current_task: 현재 실행 중인 task
            conversation_history: 대화 기록
            
        Returns:
            평가 결과 및 피드백
        """
        try:
            # 최근 대화 맥락
            recent_context = "\n".join([
                f"{msg.get('role')}: {msg.get('content', '')[:100]}"
                for msg in conversation_history[-4:]
            ])
            
            task_info = ""
            if current_task:
                task_info = f"\n현재 task: {current_task.get('title')} - {current_task.get('description')}"
            
            prompt = f"""다음은 상담 대화입니다.

대화 맥락:
{recent_context}
{task_info}

사용자: {user_message}
상담사: {counselor_response}

상담사의 응답을 평가하고 피드백을 제공하세요.

다음 형식으로 응답하세요:
SCORE: [1-10점]
STRENGTHS: [잘한 점들]
IMPROVEMENTS: [개선할 점들]
FEEDBACK: [구체적인 피드백]"""

            messages = [
                ('system', self.get_system_prompt()),
                ('user', prompt)
            ]
            
            response = self.llm.invoke(messages)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # 응답 파싱
            score = 7  # 기본값
            strengths = ""
            improvements = ""
            feedback = ""
            
            current_section = None
            for line in response_text.split('\n'):
                line = line.strip()
                if 'SCORE:' in line:
                    try:
                        score = int(line.split('SCORE:')[1].strip().split()[0])
                    except:
                        pass
                elif 'STRENGTHS:' in line:
                    current_section = 'strengths'
                    strengths = line.split('STRENGTHS:')[1].strip()
                elif 'IMPROVEMENTS:' in line:
                    current_section = 'improvements'
                    improvements = line.split('IMPROVEMENTS:')[1].strip()
                elif 'FEEDBACK:' in line:
                    current_section = 'feedback'
                    feedback = line.split('FEEDBACK:')[1].strip()
                elif current_section and line:
                    if current_section == 'strengths':
                        strengths += " " + line
                    elif current_section == 'improvements':
                        improvements += " " + line
                    elif current_section == 'feedback':
                        feedback += " " + line
            
            return {
                "score": score,
                "strengths": strengths.strip(),
                "improvements": improvements.strip(),
                "feedback": feedback.strip() or response_text,
                "needs_improvement": score < 7
            }
            
        except Exception as e:
            print(f"Supervision 평가 오류: {str(e)}")
            return {
                "score": 7,
                "strengths": "",
                "improvements": "",
                "feedback": f"평가 중 오류 발생: {str(e)}",
                "needs_improvement": False
            }

