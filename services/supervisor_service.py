"""Supervisor LLM 서비스 - 상담 품질 모니터링 및 피드백"""
import os
from typing import List, Dict, Optional
from langchain_google_vertexai import ChatVertexAI
from config import Config


class SupervisorService:
    """Supervisor LLM - 메인 상담사의 응답 품질 평가 및 피드백"""
    
    def __init__(self):
        """Supervisor 초기화"""
        if Config.GOOGLE_APPLICATION_CREDENTIALS and os.path.exists(Config.GOOGLE_APPLICATION_CREDENTIALS):
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = Config.GOOGLE_APPLICATION_CREDENTIALS
        
        self.llm = ChatVertexAI(
            model_name=Config.VERTEX_AI_MODEL,
            project=Config.PROJECT_ID,
            location=Config.LOCATION,
            temperature=0.3,  # 평가는 더 엄격하고 객관적으로
            max_output_tokens=400,  # 충분한 피드백을 위해
            model_kwargs={"thinking_budget": 0}  # Think budget을 0으로 설정하여 빠른 응답
        )
    
    def get_system_prompt(self) -> str:
        """Supervisor 시스템 프롬프트"""
        return """당신은 엄격하고 객관적인 상담 수퍼바이저입니다. 메인 상담사의 응답을 비판적으로 평가하고 구체적인 피드백을 제공하세요.

**중요: 긍정적인 피드백만 하지 마세요. 문제점을 찾아서 지적하세요.**

평가 기준 (각 항목을 엄격하게 평가):
1. **공감 수준**: 사용자의 감정을 정확히 파악하고 공감했는가? (표면적 공감이 아닌 깊은 이해)
2. **적절한 질문**: 상황에 맞는 질문을 던졌는가? (불필요한 질문이나 너무 많은 질문은 감점)
3. **비판/판단 회피**: 사용자를 비판하거나 판단하지 않았는가? (은연중의 판단도 지적)
4. **반말 사용**: 친근하고 편안한 반말을 사용했는가? (존댓말 사용 시 감점)
5. **Task 준수**: 현재 task의 목표를 달성하려고 노력했는가? (task를 무시하거나 벗어났다면 감점)
6. **정보 수집 단계 준수**: 정보 수집 task인데 해결책을 제시했다면 감점
7. **응답 길이**: 간결한가? (너무 길면 감점)

**점수 기준:**
- 9-10점: 거의 완벽, 모든 기준을 충족
- 7-8점: 양호하지만 개선 여지 있음
- 5-6점: 보통, 여러 문제점 존재
- 3-4점: 부족, 중요한 문제점 다수
- 1-2점: 매우 부족, 전면적 개선 필요

**피드백 작성 원칙:**
1. 잘한 점보다 개선할 점에 집중하세요
2. 구체적인 예시를 들어 지적하세요 (예: "~라는 표현이 판단적으로 들릴 수 있음")
3. 실제로 문제가 없을 때만 긍정적 피드백을 하세요
4. 개선점이 없으면 "개선할 점 없음"이라고 명시하세요
5. Task를 제대로 수행하지 않았다면 반드시 지적하세요"""
    
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
            
            # Task의 제약사항 확인
            task_restrictions = ""
            if current_task:
                restrictions = current_task.get('restrictions', '')
                if restrictions:
                    task_restrictions = f"\n**Task 제약사항**: {restrictions}"
            
            prompt = f"""다음은 상담 대화입니다.

대화 맥락:
{recent_context}
{task_info}{task_restrictions}

사용자: {user_message}
상담사: {counselor_response}

위 상담사의 응답을 시스템 프롬프트의 평가 기준에 따라 엄격하게 평가하세요.

다음 형식으로 응답하세요:
SCORE: [1-10점]
STRENGTHS: [잘한 점들 - 없으면 "없음"이라고 명시]
IMPROVEMENTS: [개선할 점들 - 반드시 구체적으로 제시, 없으면 "없음"이라고 명시]
FEEDBACK: [구체적인 피드백 - 문제점이 있으면 반드시 지적하고, 어떻게 개선할지 제시]"""

            messages = [
                ('system', self.get_system_prompt()),
                ('user', prompt)
            ]
            
            response = self.llm.invoke(messages)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # 응답 파싱
            score = 6  # 기본값을 6으로 낮춤 (더 엄격한 평가)
            strengths = ""
            improvements = ""
            feedback = ""
            
            current_section = None
            for line in response_text.split('\n'):
                line = line.strip()
                if 'SCORE:' in line.upper():
                    try:
                        score_text = line.split('SCORE:')[1] if 'SCORE:' in line else line.split('score:')[1]
                        score = int(score_text.strip().split()[0])
                    except:
                        pass
                elif 'STRENGTHS:' in line.upper():
                    current_section = 'strengths'
                    strengths = line.split('STRENGTHS:')[1] if 'STRENGTHS:' in line else line.split('strengths:')[1]
                    strengths = strengths.strip()
                elif 'IMPROVEMENTS:' in line.upper():
                    current_section = 'improvements'
                    improvements = line.split('IMPROVEMENTS:')[1] if 'IMPROVEMENTS:' in line else line.split('improvements:')[1]
                    improvements = improvements.strip()
                elif 'FEEDBACK:' in line.upper():
                    current_section = 'feedback'
                    feedback = line.split('FEEDBACK:')[1] if 'FEEDBACK:' in line else line.split('feedback:')[1]
                    feedback = feedback.strip()
                elif current_section and line:
                    if current_section == 'strengths':
                        strengths += " " + line
                    elif current_section == 'improvements':
                        improvements += " " + line
                    elif current_section == 'feedback':
                        feedback += " " + line
            
            # 피드백이 비어있으면 improvements와 strengths를 조합
            if not feedback.strip():
                if improvements.strip():
                    feedback = f"개선 필요: {improvements.strip()}"
                elif strengths.strip() and strengths.strip().lower() != '없음':
                    feedback = f"잘한 점: {strengths.strip()}"
                else:
                    feedback = response_text[:300]  # 원본 응답의 일부 사용
            
            return {
                "score": score,
                "strengths": strengths.strip() or "없음",
                "improvements": improvements.strip() or "없음",
                "feedback": feedback.strip() or response_text[:300],
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

