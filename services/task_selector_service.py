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
        return """당신은 상담 진행 관리자입니다. 현재 대화 상황을 분석하여 다음에 실행할 task를 선택하세요.

**Task와 Module:**
- Task: 이번 상담에서 완료해야 할 구체적 목표
- Module: Task를 수행하기 위해 사용할 상담 도구/기법

선택 기준:
1. 우선순위가 높은 task 우선
2. 현재 대화 맥락과 자연스럽게 연결되는 task
3. 사용자의 현재 감정 상태와 요구사항 반영
4. Task의 module_id를 참조하여 해당 Module의 가이드라인을 활용

선택한 task와 해당 Module의 가이드라인을 바탕으로 구체적인 실행 가이드를 제공하세요."""
    
    def select_next_task(self, conversation_history: List[Dict], 
                        available_tasks: List[Dict]) -> Optional[Dict]:
        """
        다음 실행할 task 선택 (상태 기반 필터링)
        
        Args:
            conversation_history: 대화 기록
            available_tasks: 사용 가능한 task 목록 (모든 상태 포함)
            
        Returns:
            선택된 task와 실행 가이드
        """
        if not available_tasks:
            return None
        
        # completed 상태의 task는 제외
        selectable_tasks = [t for t in available_tasks if t.get('status') != 'completed']
        
        if not selectable_tasks:
            return None
        
        try:
            # 최근 대화 요약
            recent_messages = conversation_history[-6:] if len(conversation_history) > 6 else conversation_history
            conversation_context = "\n".join([
                f"{msg.get('role')}: {msg.get('content', '')[:150]}"
                for msg in recent_messages
            ])
            
            # 사용 가능한 task 목록 (상태 정보 포함)
            tasks_info = "\n".join([
                f"- [{t.get('priority', 'medium')}] [{t.get('status', 'pending')}] {t.get('id')}: {t.get('title')} (Module: {t.get('module_id', 'N/A')}) - {t.get('description')}"
                for t in selectable_tasks
            ])
            
            # Task별 Module 가이드라인 수집
            module_guidelines_map = {}
            for task in selectable_tasks:
                module_id = task.get('module_id')
                if module_id:
                    module = self.module_service.get_module(module_id)
                    if module:
                        module_guidelines_map[task.get('id')] = self.module_service.get_module_guidelines(module_id)
            
            prompt = f"""현재 대화 상황:
{conversation_context}

사용 가능한 task 목록 (상태 정보 포함):
{tasks_info}

**선택 기준:**
1. 상태 우선순위: pending > in_progress > sufficient (completed는 제외됨)
2. 우선순위: high > medium > low
3. 현재 대화 맥락과 자연스럽게 연결되는 task
4. 사용자의 현재 감정 상태와 요구사항 반영

위 task 중에서 현재 상황에 가장 적합한 task를 선택하고, 해당 task의 Module 가이드라인을 참고하여 구체적인 실행 가이드를 제공하세요.

다음 형식으로 응답하세요:
SELECTED_TASK_ID: [task_id]
EXECUTION_GUIDE: [구체적인 실행 가이드 - 선택한 task의 Module 가이드라인을 활용하여 어떤 말투로, 어떤 질문을, 어떤 순서로 진행할지]"""

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
                # Module 가이드라인 가져오기
                module_id = selected_task.get('module_id')
                module_guidelines = ""
                if module_id:
                    module_guidelines = self.module_service.get_module_guidelines(module_id)
                
                # 실행 가이드가 없으면 Module 가이드라인 사용
                if not execution_guide and module_guidelines:
                    execution_guide = f"다음 Module 가이드라인을 따르세요:\n{module_guidelines}"
                
                return {
                    "task": selected_task,
                    "execution_guide": execution_guide or selected_task.get('target', ''),
                    "module_id": module_id
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
                            # sufficient 상태
                            task = selectable_tasks[0]
                
                module_id = task.get('module_id')
                module_guidelines = ""
                if module_id:
                    module_guidelines = self.module_service.get_module_guidelines(module_id)
                return {
                    "task": task,
                    "execution_guide": module_guidelines or task.get('target', ''),
                    "module_id": module_id
                }
            
        except Exception as e:
            print(f"Task 선택 오류: {str(e)}")
            # 오류 시 첫 번째 selectable task 반환
            if selectable_tasks:
                task = selectable_tasks[0]
                module_id = task.get('module_id')
                module_guidelines = ""
                if module_id:
                    module_guidelines = self.module_service.get_module_guidelines(module_id)
                return {
                    "task": task,
                    "execution_guide": module_guidelines or task.get('target', ''),
                    "module_id": module_id
                }
            return None

