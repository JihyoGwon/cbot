"""Task Planner LLM 서비스 - 상담 task 생성 및 업데이트"""
import os
import json
from typing import List, Dict, Optional
from langchain_google_vertexai import ChatVertexAI
from config import Config
from services.module_service import ModuleService


class TaskPlannerService:
    """Task Planner LLM - 사용자 상태 분석 및 task 생성"""
    
    def __init__(self):
        """Task Planner 초기화"""
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = Config.GOOGLE_APPLICATION_CREDENTIALS
        
        self.llm = ChatVertexAI(
            model_name=Config.VERTEX_AI_MODEL,
            project=Config.PROJECT_ID,
            location=Config.LOCATION,
            temperature=0.7,  # Task 생성은 더 구조화된 답변이 필요
            max_output_tokens=300,  # 짧은 응답
            model_kwargs={"thinking_budget": 0}  # Think budget을 0으로 설정하여 빠른 응답
        )
        
        self.module_service = ModuleService()
    
    def get_first_session_prompt(self) -> str:
        """첫 회기 상담을 위한 시스템 프롬프트"""
        return """당신은 전문 상담 계획가입니다. 첫 회기 상담에서 해야 할 task들을 생성하고 관리하세요.

첫 회기 상담의 주요 목표:
1. **관계 형성 (Rapport Building)**: 사용자와 신뢰 관계 구축
2. **정보 수집 (Information Gathering)**: 사용자의 배경, 문제 상황, 기대 등 파악
3. **목표 설정 (Goal Setting)**: 상담 목표와 기대 결과 설정
4. **신뢰 구축 (Trust Building)**: 상담 과정에 대한 안내와 기대치 설정

Task 생성 시 고려사항:
- 사용자의 현재 상태와 감정을 분석
- 첫 회기에서 필수적으로 다뤄야 할 항목들 포함
- Task 간 논리적 순서 고려
- 각 task에 우선순위 부여
- Task별 구체적인 실행 가이드 제공"""
    
    def create_initial_tasks(self, session_type: str = "first_session") -> List[Dict]:
        """
        초기 task 목록 생성 (구체적 목표 기반)
        
        Args:
            session_type: 세션 타입
            
        Returns:
            Task 목록 (구체적이고 완료 가능한 목표)
        """
        if session_type == "first_session":
            # 첫 회기 상담 기본 task 템플릿 (구체적 목표)
            return [
                {
                    "id": "task_rapport_1",
                    "module_id": "rapport_building",  # 사용할 Module
                    "priority": "high",
                    "title": "사용자에게 따뜻하게 환영 인사하기",
                    "description": "사용자를 따뜻하게 환영하고, 편안하게 이야기할 수 있음을 전달",
                    "target": "사용자가 편안하게 느끼고 대화를 시작할 수 있는 분위기 조성",
                    "completion_criteria": "사용자가 환영 인사에 응답하고 대화를 시작했을 때 완료",
                    "status": "pending"
                },
                {
                    "id": "task_info_1",
                    "module_id": "information_gathering",
                    "priority": "high",
                    "title": "사용자의 이름과 상담 목적 파악하기",
                    "description": "사용자의 이름과 이번 상담을 찾게 된 이유를 자연스럽게 물어보기",
                    "target": "사용자의 이름과 기본 상담 목적 확인",
                    "completion_criteria": "사용자가 이름과 상담 목적을 말했을 때 완료",
                    "restrictions": "이 단계에서는 해결책을 제시하지 말고, 오직 정보를 듣는 것에만 집중하세요.",
                    "status": "pending"
                },
                {
                    "id": "task_info_2",
                    "module_id": "information_gathering",
                    "priority": "high",
                    "title": "사용자의 현재 상황과 문제 파악하기",
                    "description": "사용자가 현재 겪고 있는 문제나 상황을 이해하기",
                    "target": "사용자의 현재 상황과 주요 문제점 파악",
                    "completion_criteria": "사용자가 문제를 설명했고, 상담사가 '~한 문제로 보이는데 맞아?' 같은 방식으로 요약/확인했을 때 완료",
                    "restrictions": "이 단계에서는 해결책이나 조언을 제시하지 말고, 오직 듣고 이해하는 것에만 집중하세요.",
                    "status": "pending"
                },
                {
                    "id": "task_goal_1",
                    "module_id": "goal_setting",
                    "priority": "medium",
                    "title": "이번 상담의 구체적 목표 설정하기",
                    "description": "사용자와 함께 이번 상담을 통해 달성하고 싶은 목표를 설정",
                    "target": "구체적이고 달성 가능한 상담 목표 1-2개 설정",
                    "completion_criteria": "사용자와 함께 상담 목표 1-2개를 구체적으로 설정했을 때 완료",
                    "status": "pending"
                },
                {
                    "id": "task_trust_1",
                    "module_id": "trust_building",
                    "priority": "medium",
                    "title": "상담 과정과 기대치 안내하기",
                    "description": "앞으로의 상담이 어떻게 진행될지, 무엇을 기대할 수 있는지 설명",
                    "target": "사용자가 상담 과정을 이해하고 기대치 설정",
                    "completion_criteria": "상담 과정과 기대치를 설명하고 사용자가 이해했다고 확인했을 때 완료",
                    "status": "pending"
                }
            ]
        else:
            return []
    
    def update_tasks(self, conversation_history: List[Dict], current_tasks: List[Dict]) -> List[Dict]:
        """
        대화 진행 상황에 따라 task 업데이트 (상태 관리 포함)
        
        Args:
            conversation_history: 대화 기록
            current_tasks: 현재 task 목록 (모든 상태 포함)
            
        Returns:
            업데이트된 task 목록 (상태 업데이트 포함)
        """
        try:
            # 대화 내용 요약
            recent_messages = conversation_history[-10:] if len(conversation_history) > 10 else conversation_history
            conversation_summary = "\n".join([
                f"{msg.get('role')}: {msg.get('content', '')[:100]}"
                for msg in recent_messages
            ])
            
            # Task 상태별 분류
            task_by_status = {
                "pending": [t for t in current_tasks if t.get("status") == "pending"],
                "in_progress": [t for t in current_tasks if t.get("status") == "in_progress"],
                "sufficient": [t for t in current_tasks if t.get("status") == "sufficient"],
                "completed": [t for t in current_tasks if t.get("status") == "completed"]
            }
            
            # 사용 가능한 Module 목록
            available_modules = self.module_service.get_modules_by_session_type("first_session")
            modules_info = "\n".join([
                f"- {m.get('id')}: {m.get('name')} - {m.get('description')}"
                for m in available_modules
            ])
            
            # LLM에게 task 업데이트 요청
            prompt = f"""다음은 첫 회기 상담의 대화 내용과 현재 task 상태입니다.

대화 내용:
{conversation_summary}

현재 task 상태:
- pending (대기 중): {[t.get('id') for t in task_by_status['pending']]}
- in_progress (진행 중): {[t.get('id') for t in task_by_status['in_progress']]}
- sufficient (충분히 다뤘음): {[t.get('id') for t in task_by_status['sufficient']]}
- completed (완전 종료): {[t.get('id') for t in task_by_status['completed']]}

현재 task 목록:
{json.dumps(current_tasks, ensure_ascii=False, indent=2)}

사용 가능한 Module 목록:
{modules_info}

**중요 제약사항:**
1. 첫 회기 상담은 관계 형성, 정보 수집, 목표 설정, 신뢰 구축에 집중하세요.
2. **최대 task 개수는 8개를 넘지 마세요.** (현재: {len(current_tasks)}개)
3. **Task 상태 관리:**
   - 충분히 다뤘다고 판단되면 status를 "sufficient"로 변경 (제거하지 않음)
   - 완전히 종료된 task만 status를 "completed"로 변경
   - completed 상태의 task는 제거하지 않고 유지 (재선택 불가)
4. 새로운 task는 정말 필요한 경우에만 추가하세요. 첫 회기 범위를 벗어나는 task는 추가하지 마세요.
5. 각 task는 구체적이고 완료 가능한 목표로 작성하세요.
6. Task는 Module을 참조해야 합니다 (module_id 필수).

다음을 수행하세요:
1. 대화 내용을 분석하여 충분히 다뤘다고 판단되는 task의 status를 "sufficient"로 변경
2. 사용자의 새로운 정보나 상황에 따라 새로운 task 추가 (필요시)
3. 우선순위 재조정
4. 각 task의 target(목표) 업데이트

JSON 형식으로 업데이트된 task 목록을 반환하세요. 각 task는 다음 형식을 따르세요:
{{
  "id": "task_id",
  "module_id": "module_id",
  "priority": "high|medium|low",
  "title": "task 제목 (구체적 목표)",
  "description": "task 설명",
  "target": "완료 목표 (측정 가능한 결과)",
  "completion_criteria": "완료 판단 기준",
  "restrictions": "제약사항 (있는 경우)",
  "status": "pending|in_progress|sufficient|completed"
}}

**반드시 8개 이하의 task만 반환하세요.** JSON만 반환하고 다른 설명은 하지 마세요."""

            messages = [
                ('system', self.get_first_session_prompt()),
                ('user', prompt)
            ]
            
            response = self.llm.invoke(messages)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # JSON 파싱 시도
            try:
                # JSON 부분만 추출
                json_start = response_text.find('[')
                json_end = response_text.rfind(']') + 1
                if json_start >= 0 and json_end > json_start:
                    json_text = response_text[json_start:json_end]
                    updated_tasks = json.loads(json_text)
                    return updated_tasks
            except json.JSONDecodeError:
                pass
            
            # JSON 파싱 실패 시 현재 task 반환
            return current_tasks
            
        except Exception as e:
            print(f"Task 업데이트 오류: {str(e)}")
            return current_tasks

