"""Main Counselor LLM 서비스 - 다른 LLM들과 협력하여 상담 수행"""
import os
from typing import List, Dict, Optional
from langchain_google_vertexai import ChatVertexAI
from config import Config
from services.task_planner_service import TaskPlannerService
from services.task_selector_service import TaskSelectorService
from services.supervisor_service import SupervisorService
from services.session_service import SessionService


class CounselorService:
    """메인 상담사 LLM - 통합 상담 서비스"""
    
    def __init__(self):
        """Counselor 초기화"""
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = Config.GOOGLE_APPLICATION_CREDENTIALS
        
        self.llm = ChatVertexAI(
            model_name=Config.VERTEX_AI_MODEL,
            project=Config.PROJECT_ID,
            location=Config.LOCATION,
            temperature=0.8,  # 자연스러운 대화
        )
        
        # 서브 서비스들
        self.task_planner = TaskPlannerService()
        self.task_selector = TaskSelectorService()
        self.supervisor = SupervisorService()
        self.session_service = SessionService()
        
        # Supervision 주기 설정 (N개 메시지마다)
        self.supervision_interval = Config.SUPERVISION_INTERVAL
    
    def get_counselor_prompt(self, current_task: Optional[Dict] = None, 
                            execution_guide: str = "") -> str:
        """메인 상담사 시스템 프롬프트"""
        base_prompt = Config.SYSTEM_PROMPT
        
        if current_task:
            task_guidance = f"""

현재 수행해야 할 task:
- 제목: {current_task.get('title', '')}
- 설명: {current_task.get('description', '')}
- 실행 가이드: {execution_guide if execution_guide else current_task.get('guide', '')}

위 task를 달성하기 위해 대화를 진행하세요. 자연스럽게 task를 수행하면서 사용자와의 대화를 이어가세요."""
            return base_prompt + task_guidance
        
        return base_prompt
    
    def chat(self, conversation_id: str, message: str, 
             conversation_history: Optional[List[Dict]] = None) -> Dict:
        """
        통합 상담 수행
        
        Args:
            conversation_id: 대화 ID
            message: 사용자 메시지
            conversation_history: 대화 기록
            
        Returns:
            상담사 응답 및 메타데이터
        """
        try:
            # 세션 가져오기 또는 생성
            session = self.session_service.get_session(conversation_id)
            if not session:
                # 새 세션 생성
                session = self.session_service.create_session(
                    conversation_id, 
                    session_type="first_session"
                )
                # 초기 task 생성
                initial_tasks = self.task_planner.create_initial_tasks("first_session")
                self.session_service.update_tasks(conversation_id, initial_tasks)
                session['tasks'] = initial_tasks
            
            # 대화 기록 가져오기
            if not conversation_history:
                from services.firestore_service import FirestoreService
                firestore = FirestoreService()
                conversation_history = firestore.get_conversation_history(conversation_id)
            
            # Task 업데이트 (지속적 업데이트)
            current_tasks = session.get('tasks', [])
            completed_tasks = session.get('completed_tasks', [])
            
            # 대화가 진행되면 task 업데이트
            if len(conversation_history) > 2:
                updated_tasks = self.task_planner.update_tasks(
                    conversation_history,
                    current_tasks,
                    completed_tasks
                )
                if updated_tasks != current_tasks:
                    self.session_service.update_tasks(conversation_id, updated_tasks)
                    current_tasks = updated_tasks
            
            # 다음 task 선택
            pending_tasks = [t for t in current_tasks if t.get('status') != 'completed']
            task_selection = None
            
            if pending_tasks:
                task_selection = self.task_selector.select_next_task(
                    conversation_history,
                    pending_tasks
                )
                
                if task_selection:
                    selected_task = task_selection['task']
                    self.session_service.set_current_task(
                        conversation_id, 
                        selected_task.get('id')
                    )
            
            # 메인 상담사 응답 생성
            current_task = task_selection['task'] if task_selection else None
            execution_guide = task_selection['execution_guide'] if task_selection else ""
            
            messages = []
            messages.append(('system', self.get_counselor_prompt(current_task, execution_guide)))
            
            # 대화 기록 추가
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
            counselor_response = response.content if hasattr(response, 'content') else str(response)
            
            # Supervision (주기적 평가)
            message_count = session.get('message_count', 0) + 1
            supervision_result = None
            
            if message_count % self.supervision_interval == 0:
                supervision_result = self.supervisor.evaluate_response(
                    message,
                    counselor_response,
                    current_task,
                    conversation_history
                )
                
                # Supervision 로그 저장
                self.session_service.add_supervision_log(conversation_id, {
                    "user_message": message[:200],
                    "counselor_response": counselor_response[:200],
                    "score": supervision_result['score'],
                    "feedback": supervision_result['feedback']
                })
            
            # 메시지 카운트 증가
            self.session_service.increment_message_count(conversation_id)
            
            return {
                "response": counselor_response,
                "current_task": current_task.get('id') if current_task else None,
                "supervision": supervision_result,
                "tasks_remaining": len(pending_tasks)
            }
            
        except Exception as e:
            raise Exception(f"상담 수행 중 오류 발생: {str(e)}")

