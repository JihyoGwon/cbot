"""Session Manager LLM 서비스 - 상담 세션 진행 상황 평가 및 종료 판단"""
import os
from typing import List, Dict, Optional
from langchain_google_vertexai import ChatVertexAI
from config import Config


class SessionManagerService:
    """Session Manager LLM - 상담 세션의 전체 진행 상황 파악 및 종료 판단"""
    
    def __init__(self):
        """Session Manager 초기화"""
        if Config.GOOGLE_APPLICATION_CREDENTIALS and os.path.exists(Config.GOOGLE_APPLICATION_CREDENTIALS):
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = Config.GOOGLE_APPLICATION_CREDENTIALS
        
        self.llm = ChatVertexAI(
            model_name=Config.VERTEX_AI_MODEL,
            project=Config.PROJECT_ID,
            location=Config.LOCATION,
            temperature=0.5,  # 평가는 객관적이어야 함
            max_output_tokens=400,  # 충분한 평가를 위해
            model_kwargs={"thinking_budget": 0}  # Think budget을 0으로 설정하여 빠른 응답
        )
    
    def get_system_prompt(self) -> str:
        """Session Manager 시스템 프롬프트"""
        return """당신은 전문 상담 세션 관리자입니다. 상담 세션의 전체 진행 상황을 평가하고 종료 시점을 판단하세요.

**첫 회기 상담의 주요 목표:**
1. **관계 형성 (Rapport Building)**: 사용자와 신뢰 관계 구축
2. **정보 수집 (Information Gathering)**: 사용자의 배경, 문제 상황, 기대 등 파악
3. **목표 설정 (Goal Setting)**: 상담 목표와 기대 결과 설정
4. **신뢰 구축 (Trust Building)**: 상담 과정에 대한 안내와 기대치 설정

**평가 기준:**
1. **관계 형성**: 사용자가 편안하게 대화하는가? 신뢰 관계가 형성되었는가?
2. **정보 수집**: 사용자의 주요 문제/상황 파악 완료? 필요한 배경 정보 수집 완료?
3. **목표 설정**: 상담 목표가 설정되었는가? 구체적이고 달성 가능한 목표인가?
4. **신뢰 구축**: 상담 과정에 대한 안내 완료? 기대치 설정 완료?

**종료 판단:**
- 모든 목표가 달성되었으면 "wrap_up" 제안
- 일부 목표만 달성되었으면 "continue" 제안
- 목표 달성도가 매우 낮으면 "continue" 제안

**중요:**
- 사용자가 추가 질문이나 도움이 필요하면 계속 진행해야 함
- 강제로 종료하지 말고, 자연스러운 마무리 제안만 하세요."""
    
    def evaluate_session(self, conversation_history: List[Dict], 
                        tasks: List[Dict], session_type: str = "first_session") -> Dict:
        """
        상담 세션 진행 상황 평가
        
        Args:
            conversation_history: 대화 기록
            tasks: 현재 task 목록 (모든 상태 포함)
            session_type: 세션 타입
            
        Returns:
            평가 결과 및 종료 제안
        """
        try:
            # 대화 내용 요약
            recent_messages = conversation_history[-15:] if len(conversation_history) > 15 else conversation_history
            conversation_summary = "\n".join([
                f"{msg.get('role')}: {msg.get('content', '')[:200]}"
                for msg in recent_messages
            ])
            
            # Task 상태 분석
            task_by_status = {
                "pending": [t.get('id') for t in tasks if t.get('status') == 'pending'],
                "in_progress": [t.get('id') for t in tasks if t.get('status') == 'in_progress'],
                "sufficient": [t.get('id') for t in tasks if t.get('status') == 'sufficient'],
                "completed": [t.get('id') for t in tasks if t.get('status') == 'completed']
            }
            
            # Task별 목표 달성도 추정
            task_summary = "\n".join([
                f"- {t.get('id')} ({t.get('status', 'pending')}): {t.get('title')} - {t.get('target', '')}"
                for t in tasks
            ])
            
            prompt = f"""다음은 첫 회기 상담의 대화 내용과 task 상태입니다.

대화 내용:
{conversation_summary}

Task 상태:
- pending (대기 중): {task_by_status['pending']}
- in_progress (진행 중): {task_by_status['in_progress']}
- sufficient (충분히 다뤘음): {task_by_status['sufficient']}
- completed (완전 종료): {task_by_status['completed']}

Task 목록:
{task_summary}

**평가 요청:**
1. 첫 회기 상담의 4가지 주요 목표 달성 여부 평가
2. 각 목표별 달성도 (0.0-1.0)
3. 미달성 목표가 있으면 나열
4. 종료 제안 (continue, wrap_up, complete)
5. wrap_up 제안 시 필요한 마무리 task 제안

다음 형식으로 응답하세요:
RAPPORT_BUILDING: [0.0-1.0] - [달성 여부 설명]
INFORMATION_GATHERING: [0.0-1.0] - [달성 여부 설명]
GOAL_SETTING: [0.0-1.0] - [달성 여부 설명]
TRUST_BUILDING: [0.0-1.0] - [달성 여부 설명]
COMPLETION_SCORE: [0.0-1.0] (전체 목표 달성도)
MISSING_GOALS: [미달성 목표 리스트, 없으면 "없음"]
RECOMMENDATION: [continue|wrap_up|complete]
WRAP_UP_TASKS: [마무리 task 제안, JSON 배열 형식, 없으면 "없음"]

마무리 task는 다음 형식을 따르세요:
[
  {{
    "id": "task_wrapup_1",
    "module_id": "goal_setting",
    "priority": "high",
    "title": "상담 요약 및 다음 상담 안내",
    "description": "오늘 상담 내용을 요약하고 다음 상담 계획을 안내",
    "target": "사용자가 오늘 상담 내용을 이해하고 다음 상담 계획을 확인",
    "completion_criteria": "상담 요약과 다음 상담 안내를 완료했을 때",
    "status": "pending"
  }}
]"""

            messages = [
                ('system', self.get_system_prompt()),
                ('user', prompt)
            ]
            
            response = self.llm.invoke(messages)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # 응답 파싱
            result = {
                "rapport_building": 0.0,
                "information_gathering": 0.0,
                "goal_setting": 0.0,
                "trust_building": 0.0,
                "completion_score": 0.0,
                "missing_goals": [],
                "recommendation": "continue",
                "wrap_up_tasks": []
            }
            
            current_section = None
            for line in response_text.split('\n'):
                line = line.strip()
                if 'RAPPORT_BUILDING:' in line.upper():
                    try:
                        parts = line.split(':', 1)[1].strip().split('-', 1)
                        result["rapport_building"] = float(parts[0].strip())
                    except:
                        pass
                elif 'INFORMATION_GATHERING:' in line.upper():
                    try:
                        parts = line.split(':', 1)[1].strip().split('-', 1)
                        result["information_gathering"] = float(parts[0].strip())
                    except:
                        pass
                elif 'GOAL_SETTING:' in line.upper():
                    try:
                        parts = line.split(':', 1)[1].strip().split('-', 1)
                        result["goal_setting"] = float(parts[0].strip())
                    except:
                        pass
                elif 'TRUST_BUILDING:' in line.upper():
                    try:
                        parts = line.split(':', 1)[1].strip().split('-', 1)
                        result["trust_building"] = float(parts[0].strip())
                    except:
                        pass
                elif 'COMPLETION_SCORE:' in line.upper():
                    try:
                        result["completion_score"] = float(line.split(':', 1)[1].strip().split()[0])
                    except:
                        pass
                elif 'MISSING_GOALS:' in line.upper():
                    try:
                        missing = line.split(':', 1)[1].strip()
                        if missing.lower() != '없음' and missing:
                            result["missing_goals"] = [g.strip() for g in missing.split(',')]
                    except:
                        pass
                elif 'RECOMMENDATION:' in line.upper():
                    try:
                        rec = line.split(':', 1)[1].strip().lower()
                        if rec in ['continue', 'wrap_up', 'complete']:
                            result["recommendation"] = rec
                    except:
                        pass
            
            # wrap_up_tasks 파싱 (전체 응답에서 JSON 찾기)
            if result["recommendation"] in ['wrap_up', 'complete']:
                try:
                    import json
                    # 전체 응답에서 JSON 배열 찾기
                    json_start = response_text.find('[')
                    json_end = response_text.rfind(']') + 1
                    if json_start >= 0 and json_end > json_start:
                        json_text = response_text[json_start:json_end]
                        parsed_tasks = json.loads(json_text)
                        if isinstance(parsed_tasks, list) and len(parsed_tasks) > 0:
                            result["wrap_up_tasks"] = parsed_tasks
                except:
                    pass
            
            # 세션 상태 결정
            if result["recommendation"] == "complete":
                session_status = "completed"
            elif result["recommendation"] == "wrap_up":
                session_status = "wrapping_up"
            else:
                session_status = "active"
            
            result["session_status"] = session_status
            result["first_session_goals_met"] = result["completion_score"] >= 0.7
            
            return result
            
        except Exception as e:
            print(f"Session Manager 평가 오류: {str(e)}")
            return {
                "rapport_building": 0.0,
                "information_gathering": 0.0,
                "goal_setting": 0.0,
                "trust_building": 0.0,
                "completion_score": 0.0,
                "missing_goals": [],
                "recommendation": "continue",
                "wrap_up_tasks": [],
                "session_status": "active",
                "first_session_goals_met": False
            }

