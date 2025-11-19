"""Task Completion Checker Service - Task 완료 여부 판단"""
import os
from typing import Dict, List, Optional
from langchain_google_vertexai import ChatVertexAI
from config import Config


class TaskCompletionCheckerService:
    """Task Completion Checker - Task 완료 여부 판단 및 상태 업데이트"""
    
    def __init__(self):
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
        return """당신은 Task 완료 여부를 판단하는 전문가입니다. 현재 Task가 완료되었는지 판단하세요.

**Task 완료 판단 기준:**
1. 명시적 완료 신호: 사용자나 상담사가 Task 목표를 달성했다고 명시
2. Task 목표 달성: completion_criteria가 충족되었는지 확인
3. 충분히 다뤘음: 사용자의 문제를 더 깊이 다룰 준비가 되었음

**응답 형식:**
IS_COMPLETED: [True|False]
NEW_STATUS: [sufficient|completed|None]
COMPLETION_REASON: [완료 이유 또는 None]"""
    
    def check_completion(self, current_task: Dict, conversation_history: List[Dict]) -> Dict:
        """
        Task 완료 여부 확인
        
        Args:
            current_task: 현재 Task 정보
            conversation_history: 대화 기록
            
        Returns:
            {
                "is_completed": bool,
                "new_status": "sufficient" | "completed" | None,
                "completion_reason": str,
                "task_id": str
            }
        """
        if not current_task:
            return {
                "is_completed": False,
                "new_status": None,
                "completion_reason": None,
                "task_id": None
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

위 정보를 바탕으로 Task가 완료되었는지 판단하세요.

{self.get_system_prompt()}"""
        
        messages = [
            ('system', self.get_system_prompt()),
            ('user', prompt)
        ]
        
        try:
            response = self.llm.invoke(messages)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # 응답 파싱
            is_completed = False
            new_status = None
            completion_reason = None
            
            for line in response_text.split('\n'):
                if 'IS_COMPLETED:' in line.upper():
                    value = line.split(':', 1)[1].strip().lower()
                    is_completed = value == 'true'
                elif 'NEW_STATUS:' in line.upper():
                    value = line.split(':', 1)[1].strip().lower()
                    if value in ['sufficient', 'completed']:
                        new_status = value
                elif 'COMPLETION_REASON:' in line.upper():
                    completion_reason = line.split(':', 1)[1].strip()
                    if completion_reason.lower() == 'none':
                        completion_reason = None
            
            return {
                "is_completed": is_completed,
                "new_status": new_status if is_completed else None,
                "completion_reason": completion_reason,
                "task_id": current_task.get('id')
            }
        
        except Exception as e:
            print(f"Task Completion Checker 오류: {str(e)}")
            return {
                "is_completed": False,
                "new_status": None,
                "completion_reason": None,
                "task_id": current_task.get('id')
            }

