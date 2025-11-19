"""Task Planner LLM 서비스 - 상담 task 생성 및 업데이트"""
import os
import json
from typing import List, Dict, Optional
from langchain_google_vertexai import ChatVertexAI
from config import Config


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
            model_kwargs={"thinking_budget": 0}  # Think budget을 0으로 설정하여 빠른 응답
        )
    
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
        초기 task 목록 생성 (특정 주제 기반)
        
        Args:
            session_type: 세션 타입
            
        Returns:
            Task 목록
        """
        if session_type == "first_session":
            # 첫 회기 상담 기본 task 템플릿
            return [
                {
                    "id": "rapport_1",
                    "type": "rapport_building",
                    "priority": "high",
                    "title": "환영 및 관계 형성",
                    "description": "따뜻하게 환영하고 편안한 분위기 조성",
                    "guide": "사용자를 따뜻하게 환영하고, 편하게 이야기할 수 있음을 전달하세요.",
                    "status": "pending"
                },
                {
                    "id": "info_1",
                    "type": "information_gathering",
                    "priority": "high",
                    "title": "기본 정보 수집",
                    "description": "사용자의 이름, 상담을 찾게 된 이유 등 기본 정보 파악",
                    "guide": "자연스럽게 이름과 상담 목적을 물어보세요.",
                    "status": "pending"
                },
                {
                    "id": "info_2",
                    "type": "information_gathering",
                    "priority": "high",
                    "title": "현재 상황 파악",
                    "description": "사용자가 현재 겪고 있는 문제나 상황 이해",
                    "guide": "열린 질문으로 사용자의 상황을 듣고, 공감하며 이해하세요.",
                    "status": "pending"
                },
                {
                    "id": "goal_1",
                    "type": "goal_setting",
                    "priority": "medium",
                    "title": "상담 목표 설정",
                    "description": "이번 상담을 통해 달성하고 싶은 목표 설정",
                    "guide": "사용자와 함께 구체적이고 달성 가능한 목표를 설정하세요.",
                    "status": "pending"
                },
                {
                    "id": "trust_1",
                    "type": "trust_building",
                    "priority": "medium",
                    "title": "상담 과정 안내",
                    "description": "앞으로의 상담 과정과 기대치 안내",
                    "guide": "상담이 어떻게 진행될지, 무엇을 기대할 수 있는지 설명하세요.",
                    "status": "pending"
                }
            ]
        else:
            return []
    
    def update_tasks(self, conversation_history: List[Dict], current_tasks: List[Dict], 
                    completed_tasks: List[Dict]) -> List[Dict]:
        """
        대화 진행 상황에 따라 task 업데이트
        
        Args:
            conversation_history: 대화 기록
            current_tasks: 현재 task 목록
            completed_tasks: 완료된 task 목록
            
        Returns:
            업데이트된 task 목록
        """
        try:
            # 대화 내용 요약
            recent_messages = conversation_history[-10:] if len(conversation_history) > 10 else conversation_history
            conversation_summary = "\n".join([
                f"{msg.get('role')}: {msg.get('content', '')[:100]}"
                for msg in recent_messages
            ])
            
            # 현재 task 상태
            task_status = {
                "current": [t.get("id") for t in current_tasks],
                "completed": [t.get("id") for t in completed_tasks]
            }
            
            # LLM에게 task 업데이트 요청
            prompt = f"""다음은 첫 회기 상담의 대화 내용과 현재 task 상태입니다.

대화 내용:
{conversation_summary}

현재 task 상태:
- 진행 중: {task_status['current']}
- 완료됨: {task_status['completed']}

현재 task 목록:
{json.dumps(current_tasks, ensure_ascii=False, indent=2)}

다음을 수행하세요:
1. 완료된 task는 제거하거나 상태를 'completed'로 변경
2. 사용자의 새로운 정보나 상황에 따라 새로운 task 추가
3. 우선순위 재조정
4. 각 task의 실행 가이드를 업데이트

JSON 형식으로 업데이트된 task 목록을 반환하세요. 각 task는 다음 형식을 따르세요:
{{
  "id": "task_id",
  "type": "task_type",
  "priority": "high|medium|low",
  "title": "task 제목",
  "description": "task 설명",
  "guide": "실행 가이드",
  "status": "pending|in_progress|completed"
}}

JSON만 반환하고 다른 설명은 하지 마세요."""

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

