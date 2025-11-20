"""Module Selector Service - Module 선택 및 업데이트"""
import os
from typing import Dict, List, Optional
from langchain_google_vertexai import ChatVertexAI
from config import Config
from services.module_service import ModuleService


class ModuleSelectorService:
    """Module Selector - Task와 상황에 맞는 Module 선택"""
    
    def __init__(self):
        if Config.GOOGLE_APPLICATION_CREDENTIALS and os.path.exists(Config.GOOGLE_APPLICATION_CREDENTIALS):
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = Config.GOOGLE_APPLICATION_CREDENTIALS
        
        self.llm = ChatVertexAI(
            model_name=Config.VERTEX_AI_MODEL,
            project=Config.PROJECT_ID,
            location=Config.LOCATION,
            temperature=0.6,
            max_output_tokens=200,
            model_kwargs={"thinking_budget": 0}
        )
        
        self.module_service = ModuleService()
    
    def get_system_prompt(self) -> str:
        """Module Selector 시스템 프롬프트"""
        return """당신은 상담 기법(Module) 선택 전문가입니다. Task 목표와 사용자 상태에 맞는 Module을 선택하세요.

**Module 선택 기준:**
1. Task 목표와 가장 잘 맞는 Module
2. 사용자 현재 상태 (저항, 감정 등)에 적합한 Module
3. Supervision 피드백 반영
4. 대화 맥락 고려

**응답 형식:**
SELECTED_MODULE_ID: [module_id]
CHANGE_REASON: [변경 이유 또는 None]"""
    
    def select_module(self, task: Dict, user_state: Dict, 
                     current_module_id: Optional[str] = None,
                     supervision_feedback: Optional[Dict] = None) -> Dict:
        """
        Module 선택
        
        Args:
            task: Task 정보
            user_state: User State Detector 결과
            current_module_id: 현재 Module ID (변경 체크용)
            supervision_feedback: Supervision 피드백
            
        Returns:
            {
                "module_id": str,
                "module_guidelines": str,
                "changed": bool,
                "change_reason": str
            }
        """
        # 사용 가능한 Module 목록
        all_modules = self.module_service.get_all_modules()
        modules_info = "\n".join([
            f"- {m.get('id')}: {m.get('name')} - {m.get('description')}"
            for m in all_modules
        ])
        
        task_info = f"""
Task 제목: {task.get('title', '')}
Task 목표: {task.get('target', '')}
"""
        
        user_state_info = f"""
저항 감지: {user_state.get('resistance_detected', False)}
감정 변화: {user_state.get('emotion_change', 'None')}
주제 변경: {user_state.get('topic_change', False)}
상태 요약: {user_state.get('user_state_summary', '')}
"""
        
        supervision_info = ""
        if supervision_feedback:
            score = supervision_feedback.get('score', 0)
            improvements = supervision_feedback.get('improvements', '')
            if score < 7 or improvements:
                supervision_info = f"""
Supervision 피드백:
- 점수: {score}/10
- 개선점: {improvements}
"""
        
        current_module_info = ""
        if current_module_id:
            current_module = self.module_service.get_module(current_module_id)
            if current_module:
                current_module_info = f"\n현재 Module: {current_module.get('name', current_module_id)}"
        
        prompt = f"""다음 정보를 바탕으로 적절한 Module을 선택하세요.

{task_info}

{user_state_info}

{supervision_info}

{current_module_info}

사용 가능한 Module 목록:
{modules_info}

위 Module 중에서 Task 목표와 사용자 상태에 가장 적합한 Module을 선택하세요.

{self.get_system_prompt()}"""
        
        messages = [
            ('system', self.get_system_prompt()),
            ('user', prompt)
        ]
        
        try:
            response = self.llm.invoke(messages)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # 응답 파싱
            selected_module_id = None
            change_reason = None
            
            for line in response_text.split('\n'):
                if 'SELECTED_MODULE_ID:' in line.upper():
                    selected_module_id = line.split(':', 1)[1].strip()
                elif 'CHANGE_REASON:' in line.upper():
                    change_reason = line.split(':', 1)[1].strip()
                    if change_reason.lower() == 'none':
                        change_reason = None
            
            # Module ID 검증
            if not selected_module_id or not self.module_service.get_module(selected_module_id):
                # 기본값: Task의 module_id 또는 첫 번째 Module
                if task.get('module_id'):
                    selected_module_id = task.get('module_id')
                else:
                    selected_module_id = all_modules[0].get('id') if all_modules else None
            
            # Module 가이드라인 가져오기
            module_guidelines = ""
            if selected_module_id:
                module_guidelines = self.module_service.get_module_guidelines(selected_module_id)
            
            # 변경 여부 확인
            changed = current_module_id is not None and selected_module_id != current_module_id
            
            return {
                "module_id": selected_module_id,
                "module_guidelines": module_guidelines,
                "changed": changed,
                "change_reason": change_reason if changed else None
            }
        
        except Exception as e:
            print(f"Module Selector 오류: {str(e)}")
            # 기본값 반환
            default_module_id = task.get('module_id') or (all_modules[0].get('id') if all_modules else None)
            return {
                "module_id": default_module_id,
                "module_guidelines": self.module_service.get_module_guidelines(default_module_id) if default_module_id else "",
                "changed": False,
                "change_reason": None
            }

