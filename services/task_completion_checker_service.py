"""Task Completion Checker Service - Task 완료 여부 판단"""
import os
from typing import Dict, List, Optional
from langchain_google_vertexai import ChatVertexAI
from config import Config


class TaskCompletionCheckerService:
    """Task Completion Checker - Task 완료 여부 판단 및 상태 업데이트"""
    
    def __init__(self):
        if Config.GOOGLE_APPLICATION_CREDENTIALS and os.path.exists(Config.GOOGLE_APPLICATION_CREDENTIALS):
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = Config.GOOGLE_APPLICATION_CREDENTIALS
        
        self.llm = ChatVertexAI(
            model_name=Config.VERTEX_AI_MODEL,
            project=Config.PROJECT_ID,
            location=Config.LOCATION,
            temperature=0.5,
            max_output_tokens=200,
            model_kwargs={"thinking_budget": 0}
        )
    
    def get_system_prompt(self) -> str:
        """Task Completion Checker 시스템 프롬프트"""
        return """당신은 Task 완료 여부를 판단하는 전문가입니다. **실용적이고 관대한 기준**으로 Task 완료를 판단하세요.

**Task 상태 정의:**
- `sufficient`: 충분히 다뤘고, 완벽하지 않아도 다음 단계로 진행 가능한 상태
- `completed`: 
    - 완전히 완료되었고, 더 이상 다룰 필요가 없는 상태
    - 사용자의 강한 저항이 발생했을 때
- `None`: 아직 완료되지 않음

**1. "completed" 판단 기준 (완전 완료):**
다음 조건 중 하나라도 충족되면 `completed`로 판단:
- 명시적 완료 신호:
  * 사용자의 확인/동의, 감사, 만족 표현
  * 사용자가 다음 단계로 넘어가자고 제안
  * 상담사가 Task 목표를 달성했다고 명시하고 사용자가 긍정적으로 응답한 경우

- 완전한 목표 달성:
  * Task의 핵심 목표(target)가 완전히 달성되었고
  * completion_criteria의 모든 요구사항이 충족되었으며
  * 사용자가 명시적으로 확인하거나 동의한 경우

- 사용자의 강한 저항:
  * 사용자가 Task에 대해 명확한 거부, 회피, 또는 강한 저항을 보일 때
  * 예: "이건 하고 싶지 않아", "이 주제는 피하고 싶어", "더 이상 얘기하고 싶지 않아" 등
  * 이 경우 Task를 강제로 진행하는 것보다 완료 처리하고 다음 단계로 넘어가는 것이 적절함

**2. "sufficient" 판단 기준 (충분히 다뤘음):**
다음 조건 중 하나라도 충족되면 `sufficient`로 판단:
- Task의 핵심 목표(completion_criteria)가 기본적으로 달성되었을 때
- 상담사가 Task를 수행했고 사용자가 자연스럽게 응답했을 때
- 더 깊이 다루기보다는 다음 Task로 진행하는 것이 자연스러울 때

**3. 완료되지 않음 (None):**
- Task의 핵심 목표가 아직 달성되지 않았거나
- 사용자가 Task와 관련된 정보를 공유하기 시작했지만 아직 충분하지 않은 경우

**응답 형식:**
NEW_STATUS: [sufficient|completed|None]
COMPLETION_REASON: [완료 이유 또는 None]

**참고:**
- `NEW_STATUS: sufficient` 또는 `NEW_STATUS: completed` → 완료로 간주
- `NEW_STATUS: None` → 미완료"""
    
    def check_completion(self, current_task: Dict, conversation_history: List[Dict]) -> Dict:
        """
        Task 완료 여부 확인
        
        Args:
            current_task: 현재 Task 정보
            conversation_history: 대화 기록
            
        Returns:
            {
                "new_status": "sufficient" | "completed" | None,
                "completion_reason": str,
                "task_id": str,
                "raw_output": str
            }
        """
        if not current_task:
            return {
                "new_status": None,
                "completion_reason": None,
                "task_id": None,
                "raw_output": ""
            }
        
        # 최근 대화 요약
        recent_messages = conversation_history[-6:] if len(conversation_history) > 6 else conversation_history
        conversation_context = "\n".join([
            f"{msg.get('role')}: {msg.get('content', '')[:150]}"
            for msg in recent_messages
        ])
        
        task_info = f"""
Task ID: {current_task.get('id')}
제목: {current_task.get('title', '')}
목표: {current_task.get('target', '')}
완료 기준: {current_task.get('completion_criteria', '')}
현재 상태: {current_task.get('status', 'pending')}
"""
        
        prompt = f"""다음은 현재 Task와 최근 대화 내용입니다.

{task_info}

최근 대화:
{conversation_context}

위 정보를 바탕으로 시스템 프롬프트의 판단 기준에 따라 Task가 완료되었는지 판단하세요.

다음 형식으로 응답하세요:
NEW_STATUS: [sufficient|completed|None]
COMPLETION_REASON: [완료 이유 또는 None]"""
        
        messages = [
            ('system', self.get_system_prompt()),
            ('user', prompt)
        ]
        
        try:
            response = self.llm.invoke(messages)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # 응답 파싱
            new_status = None
            completion_reason = None
            
            for line in response_text.split('\n'):
                if 'NEW_STATUS:' in line.upper():
                    value = line.split(':', 1)[1].strip().lower()
                    if value in ['sufficient', 'completed']:
                        new_status = value
                    elif value == 'none':
                        new_status = None
                elif 'COMPLETION_REASON:' in line.upper():
                    completion_reason = line.split(':', 1)[1].strip()
                    if completion_reason.lower() == 'none':
                        completion_reason = None
            
            return {
                "new_status": new_status,
                "completion_reason": completion_reason,
                "task_id": current_task.get('id'),
                "raw_output": response_text  # 디버깅용 원본 출력
            }
        
        except Exception as e:
            print(f"Task Completion Checker 오류: {str(e)}")
            return {
                "new_status": None,
                "completion_reason": None,
                "task_id": current_task.get('id'),
                "raw_output": f"오류: {str(e)}"
            }

