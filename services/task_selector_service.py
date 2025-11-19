"""Task Selector LLM 서비스 - 다음 실행할 task 선택"""
import os
from typing import List, Dict, Optional
from langchain_google_vertexai import ChatVertexAI
from config import Config


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
        )
    
    def get_system_prompt(self) -> str:
        """Task Selector 시스템 프롬프트"""
        return """당신은 상담 진행 관리자입니다. 현재 대화 상황을 분석하여 다음에 실행할 task를 선택하세요.

선택 기준:
1. 우선순위가 높은 task 우선
2. 현재 대화 맥락과 자연스럽게 연결되는 task
3. 이전 task의 완료 상태 고려
4. 사용자의 현재 감정 상태와 요구사항 반영

선택한 task에 대해 구체적인 실행 가이드를 제공하세요."""
    
    def select_next_task(self, conversation_history: List[Dict], 
                        available_tasks: List[Dict]) -> Optional[Dict]:
        """
        다음 실행할 task 선택
        
        Args:
            conversation_history: 대화 기록
            available_tasks: 사용 가능한 task 목록
            
        Returns:
            선택된 task와 실행 가이드
        """
        if not available_tasks:
            return None
        
        try:
            # 최근 대화 요약
            recent_messages = conversation_history[-6:] if len(conversation_history) > 6 else conversation_history
            conversation_context = "\n".join([
                f"{msg.get('role')}: {msg.get('content', '')[:150]}"
                for msg in recent_messages
            ])
            
            # 사용 가능한 task 목록
            tasks_info = "\n".join([
                f"- [{t.get('priority', 'medium')}] {t.get('id')}: {t.get('title')} - {t.get('description')}"
                for t in available_tasks
            ])
            
            prompt = f"""현재 대화 상황:
{conversation_context}

사용 가능한 task 목록:
{tasks_info}

위 task 중에서 현재 상황에 가장 적합한 task를 선택하고, 구체적인 실행 가이드를 제공하세요.

다음 형식으로 응답하세요:
SELECTED_TASK_ID: [task_id]
EXECUTION_GUIDE: [구체적인 실행 가이드 - 어떤 말투로, 어떤 질문을, 어떤 순서로 진행할지]"""

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
            selected_task = next((t for t in available_tasks if t.get('id') == selected_task_id), None)
            
            if selected_task:
                return {
                    "task": selected_task,
                    "execution_guide": execution_guide or selected_task.get('guide', '')
                }
            else:
                # 선택 실패 시 우선순위가 높은 첫 번째 task 반환
                high_priority_tasks = [t for t in available_tasks if t.get('priority') == 'high']
                if high_priority_tasks:
                    return {
                        "task": high_priority_tasks[0],
                        "execution_guide": high_priority_tasks[0].get('guide', '')
                    }
                return {
                    "task": available_tasks[0],
                    "execution_guide": available_tasks[0].get('guide', '')
                }
            
        except Exception as e:
            print(f"Task 선택 오류: {str(e)}")
            # 오류 시 첫 번째 task 반환
            if available_tasks:
                return {
                    "task": available_tasks[0],
                    "execution_guide": available_tasks[0].get('guide', '')
                }
            return None

