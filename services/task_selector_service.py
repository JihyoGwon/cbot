"""Task Selector LLM 서비스 - 다음 실행할 task 선택"""
import os
from typing import List, Dict, Optional
from langchain_google_vertexai import ChatVertexAI
from config import Config
from services.module_service import ModuleService


class TaskSelectorService:
    """Task Selector LLM - 현재 컨텍스트에서 다음 task 선택"""
    
    def __init__(self):
        """Task Selector 초기화"""
        if Config.GOOGLE_APPLICATION_CREDENTIALS and os.path.exists(Config.GOOGLE_APPLICATION_CREDENTIALS):
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = Config.GOOGLE_APPLICATION_CREDENTIALS
            
        self.llm = ChatVertexAI(
            model_name=Config.VERTEX_AI_MODEL,
            project=Config.PROJECT_ID,
            location=Config.LOCATION,
            temperature=0.6,  # 선택은 더 결정적이어야 함
            max_output_tokens=200,  # 짧은 응답
            model_kwargs={"thinking_budget": 0}  # Think budget을 0으로 설정하여 빠른 응답
        )
        
        self.module_service = ModuleService()
    
    def get_system_prompt(self) -> str:
        """Task Selector 시스템 프롬프트"""
        return """당신은 상담 진행 관리자입니다. 현재 Part 내에서 다음에 실행할 task를 선택하고, 선택한 task에 대한 구체적인 실행 가이드를 제공하는 역할을 합니다.

**선택 기준:**
1. 현재 Part 내의 Task만 선택
2. 상태 우선순위: pending > in_progress > sufficient
3. 우선순위: high > medium > low
4. 현재 대화 맥락과 자연스럽게 연결되는 task
5. 사용자의 현재 감정 상태와 요구사항 반영
6. 사용자가 저항을 보일 경우 동일한 task 선택 금지

**실행 가이드 제공:**
1. 선택한 task를 바탕으로 구체적인 실행 가이드를 제공하세요. (Module은 나중에 선택됩니다)
2. **주의**: 앞의 대화에서 이미 다룬 내용을 가이드로 제공하는 것을 최대한 피해야 합니다.

**응답 형식:**
다음 형식으로 응답하세요:
SELECTED_TASK_ID: [task_id]
EXECUTION_GUIDE: [구체적인 실행 가이드 - 어떤 말투로, 어떤 질문을, 어떤 순서로 진행할지]"""
    
    def select_next_task(self, conversation_history: List[Dict], 
                        available_tasks: List[Dict], current_part: int) -> Optional[Dict]:
        """
        다음 실행할 task 선택 (현재 Part 내에서만)
        
        Args:
            conversation_history: 대화 기록
            available_tasks: 사용 가능한 task 목록 (모든 상태 포함)
            current_part: 현재 Part 번호
            
        Returns:
            선택된 task와 실행 가이드
        """
        if not available_tasks:
            return None
        
        # 현재 Part의 Task만 필터링
        part_tasks = [t for t in available_tasks if t.get('part') == current_part]
        
        # completed 상태의 task만 제외 (sufficient는 재선택 가능하지만 우선순위 낮음)
        selectable_tasks = [t for t in part_tasks if t.get('status') != 'completed']
        
        if not selectable_tasks:
            return None
        
        try:
            # 최근 대화 요약
            # recent_messages = conversation_history[-6:] if len(conversation_history) > 6 else conversation_history
            recent_messages = conversation_history
            conversation_context = "\n".join([
                f"{msg.get('role')}: {msg.get('content', '')[:150]}"
                for msg in recent_messages
            ])
            
            # 사용 가능한 task 목록 (상태 정보 포함)
            tasks_info = "\n".join([
                f"- [{t.get('priority', 'medium')}] [{t.get('status', 'pending')}] {t.get('id')}: {t.get('title')} - {t.get('description')}"
                for t in selectable_tasks
            ])
            
            prompt = f"""현재 Part {current_part}의 대화 상황:
{conversation_context}

현재 Part {current_part}의 사용 가능한 task 목록:
{tasks_info}

위 task 중에서 시스템 프롬프트의 선택 기준에 따라 현재 상황에 가장 적합한 task를 선택하고, 선택한 task에 맞춰 현재 대화 맥락을 반영한 구체적인 실행 가이드를 생성하세요."""

            messages = [
                ('system', self.get_system_prompt()),
                ('user', prompt)
            ]
            
            response = self.llm.invoke(messages)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # 응답 파싱
            selected_task_id = None
            execution_guide = ""
            
            for line in response_text.split('\n'):
                if 'SELECTED_TASK_ID:' in line:
                    selected_task_id = line.split('SELECTED_TASK_ID:')[1].strip()
                elif 'EXECUTION_GUIDE:' in line:
                    execution_guide = line.split('EXECUTION_GUIDE:')[1].strip()
            
            # Task 찾기
            selected_task = next((t for t in selectable_tasks if t.get('id') == selected_task_id), None)
            
            if selected_task:
                return {
                    "task": selected_task,
                    "execution_guide": execution_guide or selected_task.get('target', ''),
                    "raw_output": response_text  # 원본 LLM 응답 추가
                }
            else:
                # 선택 실패 시 상태와 우선순위 기반으로 선택
                # pending 상태 중 high priority 우선
                pending_high = [t for t in selectable_tasks if t.get('status') == 'pending' and t.get('priority') == 'high']
                if pending_high:
                    task = pending_high[0]
                else:
                    # pending 상태 중 아무거나
                    pending_tasks = [t for t in selectable_tasks if t.get('status') == 'pending']
                    if pending_tasks:
                        task = pending_tasks[0]
                    else:
                        # in_progress 상태
                        in_progress_tasks = [t for t in selectable_tasks if t.get('status') == 'in_progress']
                        if in_progress_tasks:
                            task = in_progress_tasks[0]
                        else:
                            # sufficient 상태 (낮은 우선순위지만 선택 가능)
                            sufficient_tasks = [t for t in selectable_tasks if t.get('status') == 'sufficient']
                            if sufficient_tasks:
                                task = sufficient_tasks[0]
                            else:
                                # selectable_tasks가 비어있으면 None 반환
                                return None
            
            return {
                "task": task,
                "execution_guide": task.get('target', ''),
                "raw_output": response_text  # 원본 LLM 응답 추가
            }
            
        except Exception as e:
            print(f"Task 선택 오류: {str(e)}")
            # 오류 시 상태 우선순위로 선택 (pending > in_progress > sufficient)
            pending_tasks = [t for t in selectable_tasks if t.get('status') == 'pending']
            if pending_tasks:
                task = pending_tasks[0]
                return {
                    "task": task,
                    "execution_guide": task.get('target', ''),
                    "raw_output": "오류 발생: " + str(e)
                }
            in_progress_tasks = [t for t in selectable_tasks if t.get('status') == 'in_progress']
            if in_progress_tasks:
                task = in_progress_tasks[0]
                return {
                    "task": task,
                    "execution_guide": task.get('target', ''),
                    "raw_output": "오류 발생: " + str(e)
                }
            sufficient_tasks = [t for t in selectable_tasks if t.get('status') == 'sufficient']
            if sufficient_tasks:
                task = sufficient_tasks[0]
                return {
                    "task": task,
                    "execution_guide": task.get('target', ''),
                    "raw_output": "오류 발생: " + str(e)
                }
            return None

