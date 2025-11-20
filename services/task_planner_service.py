"""Task Planner LLM 서비스 - 상담 task 생성 및 업데이트"""
import os
import json
import logging
from typing import List, Dict, Optional, Tuple
from langchain_google_vertexai import ChatVertexAI
from config import Config
from services.module_service import ModuleService
from services.session_service import SessionService
from services.persona_service import PersonaService

logger = logging.getLogger(__name__)


class TaskPlannerService:
    """Task Planner LLM - 사용자 상태 분석 및 task 생성"""
    
    def __init__(self):
        """Task Planner 초기화"""
        if Config.GOOGLE_APPLICATION_CREDENTIALS and os.path.exists(Config.GOOGLE_APPLICATION_CREDENTIALS):
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = Config.GOOGLE_APPLICATION_CREDENTIALS
            
        self.llm = ChatVertexAI(
            model_name=Config.VERTEX_AI_MODEL,
            project=Config.PROJECT_ID,
            location=Config.LOCATION,
            temperature=0.7,  # Task 생성은 더 구조화된 답변이 필요
            max_output_tokens=2000,  # JSON 배열 반환을 위해 충분한 토큰 필요
            model_kwargs={"thinking_budget": 0}  # Think budget을 0으로 설정하여 빠른 응답
        )
        
        self.module_service = ModuleService()
        self.session_service = SessionService()
        self.persona_service = PersonaService()
    
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
                    "part": 1,
                    "priority": "high",
                    "title": "환영 및 인사",
                    "target": "사용자가 편안하게 느끼고 대화를 시작할 수 있는 분위기 조성",
                    "description": "상담사는 사용자를 따뜻하게 환영하고, 가볍게 오늘 안부를 묻는다.",
                    "completion_criteria": "사용자가 환영 인사에 응답하고 대화를 시작했을 때 완료",
                    "status": "pending"
                },
                {
                    "id": "task_rapport_2",
                    "part": 1,
                    "priority": "medium",
                    "title": "관계 형성하기",
                    "target": "사용자가 편안하게 느끼고 신뢰할 수 있는 관계 형성",
                    "description": "상담사는 사용자가 어떤 대화를 원하는지 또는 어떤 고민을 가지고 있는지 파악한다.",
                    "completion_criteria": "사용자가 3턴 이상 편안하게 대화를 이어가거나, 핵심 고민을 얘기함",
                    "status": "pending"
                }
            ]
        else:
            return []
    
    def create_part2_goal_and_plan(self, conversation_id: str, conversation_history: List[Dict]) -> Tuple[str, List[str], List[Dict]]:
        """
        Part 2 목표 및 Task Plan 수립 (페르소나 기반)
        
        Args:
            conversation_id: 대화 ID
            conversation_history: Part 1 대화 기록
            
        Returns:
            (part2_goal, selected_keywords, tasks) 튜플
            - part2_goal: Part 2 목표 (문자열)
            - selected_keywords: 선택된 키워드 리스트 (최대 3~4개)
            - tasks: Part 2 Task 목록
        """
        # 1. 세션에서 페르소나 정보 조회
        session = self.session_service.get_session(conversation_id)
        if not session:
            logger.error(f"[PART2_GOAL] 세션을 찾을 수 없음: {conversation_id}")
            return "", [], []
        
        user_persona = session.get('user_persona')
        if not user_persona:
            logger.error(f"[PART2_GOAL] 페르소나 정보가 없음: {conversation_id}")
            return "", [], []
        
        persona_type = user_persona.get('type', '')
        type_specific_keywords = user_persona.get('type_specific_keywords', [])
        common_keywords = user_persona.get('common_keywords', [])
        counseling_level = user_persona.get('counseling_level', 1)
        
        # 모든 키워드 합치기 (8개)
        all_keywords = type_specific_keywords + common_keywords
        
        # 2. DB에서 상담 레벨 정보 조회
        counseling_levels = self.persona_service.get_counseling_levels()
        current_level_info = next((level for level in counseling_levels if level.get('level') == counseling_level), None)
        
        if not current_level_info:
            logger.warning(f"[PART2_GOAL] 상담 레벨 {counseling_level} 정보를 찾을 수 없음. 기본값 사용")
            current_level_info = {
                'level': counseling_level,
                'stage': '초기',
                'focus_area': '라포 형성, 문제 인식',
                'description': '상담 초기 단계, 관계 형성과 문제 인식에 집중'
            }
        
        level_stage = current_level_info.get('stage', '')
        level_focus_area = current_level_info.get('focus_area', '')
        level_description = current_level_info.get('description', '')
        
        # 모든 레벨 정보를 프롬프트에 포함 (Task 깊이 조절 가이드용)
        level_guide_text = "\n".join([
            f"   - 레벨 {level.get('level')}: {level.get('stage')} - {level.get('focus_area')} ({level.get('description')})"
            for level in counseling_levels
        ])
        
        # 3. Part 1 대화 분석
        conversation_summary = "\n".join([
            f"{msg.get('role')}: {msg.get('content', '')[:300]}"
            for msg in conversation_history
        ])
        
        prompt = f"""Part 1 상담이 완료되었습니다. 사용자의 페르소나 정보와 Part 1 대화 내용을 바탕으로 Part 2 목표와 Task Plan을 수립하세요.

## 페르소나 정보
- 타입: {persona_type}
- 타입 특화 키워드: {', '.join(type_specific_keywords)}
- 공통 키워드: {', '.join(common_keywords)}
- 상담 레벨: {counseling_level} ({level_stage} - {level_focus_area})
  - 설명: {level_description}

## Part 1 대화 내용
{conversation_summary}

## 작업 순서
1. **키워드 관련성 평가**: 위 8개 키워드 중 Part 1 대화와 가장 관련성 높은 키워드를 1개 선택하세요.
2. **Part 2 목표 생성**: 페르소나 타입 + 선택된 키워드 + 상담 레벨 + 대화 내용을 바탕으로 구체적이고 측정 가능한 Part 2 목표를 생성하세요.
   예: "완벽주의 성향과 스트레스 관리 문제를 중심으로, 감정 탐색과 대처 전략 수립에 집중"
3. **Task Plan 수립**: Part 2 목표 달성을 위한 구체적 Task를 생성하세요. 현재 상담 레벨({counseling_level})의 특성({level_description})을 고려하여 Task 깊이를 조절하세요.

상담 레벨별 가이드:
{level_guide_text}

JSON 형식으로 반환하세요:
{{
  "selected_keywords": ["키워드"],
  "part2_goal": "Part 2 목표 (구체적이고 측정 가능)",
  "tasks": [
    {{
      "id": "task_part2_1",
      "part": 2,
      "priority": "high|medium|low",
      "title": "Task 제목",
      "target": "Task 목표",
      "description": "Task 설명 (3문장 이하)",
      "completion_criteria": "Task 완료 판단 기준",
      "status": "pending"
    }}
  ]
}}

최대 7개의 Task를 생성하세요. JSON만 반환하고 다른 설명은 하지 마세요."""
        
        messages = [
            ('system', self.get_first_session_prompt()),
            ('user', prompt)
        ]
        
        try:
            response = self.llm.invoke(messages)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            logger.info(f"[PART2_GOAL] LLM 응답 (처음 1000자): {response_text[:1000]}")
            
            # JSON 파싱
            import re
            
            # JSON 객체 찾기
            json_match = re.search(r'\{[\s\S]*\}', response_text, re.DOTALL)
            
            # 코드 블록 안의 JSON 찾기
            if not json_match:
                code_block_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})', response_text, re.DOTALL)
                if code_block_match:
                    json_match = code_block_match
            
            if json_match:
                try:
                    json_text = json_match.group() if hasattr(json_match, 'group') else json_match
                    # 코드 블록 마커 제거
                    json_text = re.sub(r'```(?:json)?\s*', '', json_text)
                    json_text = re.sub(r'```\s*', '', json_text)
                    json_text = json_text.strip()
                    
                    result = json.loads(json_text)
                    
                    selected_keywords = result.get('selected_keywords', [])
                    part2_goal = result.get('part2_goal', '')
                    tasks = result.get('tasks', [])
                    
                    # tasks 검증 및 보완
                    if not isinstance(tasks, list):
                        logger.error(f"[PART2_GOAL] tasks가 리스트가 아님: {type(tasks)}")
                        tasks = []
                    
                    for task in tasks:
                        if 'part' not in task:
                            task['part'] = 2
                        if 'status' not in task:
                            task['status'] = 'pending'
                    
                    logger.info(f"[PART2_GOAL] 파싱 성공: 목표={part2_goal[:100]}, 키워드={selected_keywords}, Task={len(tasks)}개")
                    
                    return part2_goal, selected_keywords, tasks
                    
                except json.JSONDecodeError as e:
                    logger.error(f"[PART2_GOAL] JSON 파싱 실패: {str(e)}")
                    json_text = json_match.group() if hasattr(json_match, 'group') else str(json_match)
                    logger.error(f"[PART2_GOAL] JSON 텍스트: {json_text[:500]}")
                    return "", [], []
            else:
                logger.error(f"[PART2_GOAL] JSON 객체를 찾을 수 없음")
                logger.error(f"[PART2_GOAL] 전체 응답 텍스트: {response_text}")
                return "", [], []
        
        except Exception as e:
            import traceback
            logger.error(f"[PART2_GOAL] 목표 수립 오류: {str(e)}")
            logger.error(f"[PART2_GOAL] Traceback: {traceback.format_exc()}")
            return "", [], []
    
    def create_part2_tasks(self, conversation_history: List[Dict]) -> List[Dict]:
        """
        Part 2 Task 동적 생성 (Part 1 완료 시점)
        
        Args:
            conversation_history: 대화 기록
            
        Returns:
            Part 2 Task 목록
        """
        # 전체 대화 내용 요약 (Part 1 전체 대화 포함)
        conversation_summary = "\n".join([
            f"{msg.get('role')}: {msg.get('content', '')[:300]}"
            for msg in conversation_history
        ])
        
        prompt = f"""Part 1 상담이 완료되었습니다. 지금까지의 대화 내용을 바탕으로 Part 2 (탐색) Task를 생성하세요.

전체 대화 내용:
{conversation_summary}

Part 2는 사용자의 문제 상황을 깊이 탐색하는 단계입니다. 위 대화 내용을 분석하여 다음을 고려하여 Task를 생성하세요:

1. 사용자의 문제 상황을 더 깊이 이해하기 위한 Task
2. 감정과 경험을 탐색하기 위한 Task
3. 배경 정보와 맥락을 파악하기 위한 Task
4. 문제의 원인과 패턴을 찾기 위한 Task

각 Task는 구체적이고 달성 가능한 목표로 작성하세요. Task는 module_id 없이 생성하세요 (Module은 나중에 선택됩니다).
깊은 탐색이 중요하나, 사용자에게 부담을 주는 것을 피해야 합니다. 예를 들어, 3가지 이상 구체적인 상황 설명을 요청하는 것은 피해야 합니다.

JSON 형식으로 Task 목록을 반환하세요:
[
  {{
    "id": "task_part2_1",
    "part": 2,
    "priority": "high|medium|low",
    "title": "Task 제목",
    "target": "Task 목표",    
    "description": "Task 설명 (3문장 이하)",
    "completion_criteria": "Task 완료 판단 기준",
    "status": "pending"
  }}
]

최대 7개의 Task를 생성하세요. JSON만 반환하고 다른 설명은 하지 마세요."""
        
        messages = [
            ('system', self.get_first_session_prompt()),
            ('user', prompt)
        ]
        
        try:
            response = self.llm.invoke(messages)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # 디버깅: LLM 응답 로그
            logger.info(f"[PART2_TASK] LLM 응답 (처음 1000자): {response_text[:1000]}")
            
            # JSON 파싱
            import json
            import re
            
            # 여러 방법으로 JSON 배열 찾기
            json_match = None
            
            # 방법 1: 일반적인 JSON 배열 패턴
            json_match = re.search(r'\[[\s\S]*?\]', response_text, re.DOTALL)
            
            # 방법 2: 코드 블록 안의 JSON 찾기
            if not json_match:
                code_block_match = re.search(r'```(?:json)?\s*(\[[\s\S]*?\])', response_text, re.DOTALL)
                if code_block_match:
                    json_match = code_block_match
            
            # 방법 3: 첫 번째 [ 부터 마지막 ] 까지
            if not json_match:
                first_bracket = response_text.find('[')
                last_bracket = response_text.rfind(']')
                if first_bracket >= 0 and last_bracket > first_bracket:
                    json_match = type('obj', (object,), {'group': lambda: response_text[first_bracket:last_bracket+1]})()
            
            if json_match:
                try:
                    json_text = json_match.group() if hasattr(json_match, 'group') else json_match
                    # 코드 블록 마커 제거
                    json_text = re.sub(r'```(?:json)?\s*', '', json_text)
                    json_text = re.sub(r'```\s*', '', json_text)
                    json_text = json_text.strip()
                    
                    tasks = json.loads(json_text)
                    
                    # 리스트인지 확인
                    if not isinstance(tasks, list):
                        logger.error(f"[PART2_TASK] 파싱 실패 - 리스트가 아님: {type(tasks)}")
                        return []
                    
                    # part 필드 확인
                    for task in tasks:
                        if 'part' not in task:
                            task['part'] = 2
                        # status 필드 확인
                        if 'status' not in task:
                            task['status'] = 'pending'
                    logger.info(f"[PART2_TASK] 파싱 성공: {len(tasks)}개 Task 생성됨")
                    return tasks
                except json.JSONDecodeError as e:
                    logger.error(f"[PART2_TASK] JSON 파싱 실패: {str(e)}")
                    json_text = json_match.group() if hasattr(json_match, 'group') else str(json_match)
                    logger.error(f"[PART2_TASK] JSON 텍스트: {json_text[:500]}")
                    return []
            else:
                logger.error(f"[PART2_TASK] JSON 배열을 찾을 수 없음")
                logger.error(f"[PART2_TASK] 전체 응답 텍스트: {response_text}")
                return []
        
        except Exception as e:
            import traceback
            logger.error(f"[PART2_TASK] Task 생성 오류: {str(e)}")
            logger.error(f"[PART2_TASK] Traceback: {traceback.format_exc()}")
            return []
    
    def update_part2_tasks(self, conversation_history: List[Dict], current_tasks: List[Dict],
                          user_state: Dict, should_update: bool) -> List[Dict]:
        """
        Part 2 Task 업데이트 (특정 조건 충족 시)
        
        Args:
            conversation_history: 대화 기록
            current_tasks: 현재 Task 목록
            user_state: User State Detector 결과
            should_update: 업데이트 필요 여부
            
        Returns:
            업데이트된 Task 목록
        """
        if not should_update:
            return current_tasks
        
        # 업데이트 조건 확인
        update_reasons = []
        if user_state.get('topic_change'):
            update_reasons.append("대화 주제 변경")
        if user_state.get('resistance_detected'):
            update_reasons.append("사용자 저항 감지")
        if user_state.get('circular_conversation'):
            update_reasons.append("대화가 빙빙 돎")
        
        if not update_reasons:
            return current_tasks
        
        # Part 2 Task만 필터링
        part2_tasks = [t for t in current_tasks if t.get('part') == 2]
        other_tasks = [t for t in current_tasks if t.get('part') != 2]
        
        # 업데이트 프롬프트
        recent_messages = conversation_history[-10:] if len(conversation_history) > 10 else conversation_history
        conversation_summary = "\n".join([
            f"{msg.get('role')}: {msg.get('content', '')[:150]}"
            for msg in recent_messages
        ])
        
        prompt = f"""Part 2 Task를 업데이트해야 합니다.

업데이트 이유: {', '.join(update_reasons)}

현재 대화:
{conversation_summary}

현재 Part 2 Task:
{json.dumps(part2_tasks, ensure_ascii=False, indent=2)}

사용자 상태:
- 저항: {user_state.get('resistance_detected', False)}
- 감정 변화: {user_state.get('emotion_change', 'None')}
- 주제 변경: {user_state.get('topic_change', False)}
- 빙빙 도는 대화: {user_state.get('circular_conversation', False)}

위 정보를 바탕으로 Part 2 Task를 업데이트하세요:
1. 새로운 Task 추가 (필요 시)
2. 기존 Task 수정 (필요 시)
3. 불필요한 Task 제거 (필요 시)

JSON 형식으로 업데이트된 Part 2 Task 목록을 반환하세요. 최대 7개를 유지하세요."""
        
        messages = [
            ('system', self.get_first_session_prompt()),
            ('user', prompt)
        ]
        
        try:
            import re
            
            response = self.llm.invoke(messages)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if json_match:
                updated_part2_tasks = json.loads(json_match.group())
                # part 필드 확인
                for task in updated_part2_tasks:
                    if 'part' not in task:
                        task['part'] = 2
                return other_tasks + updated_part2_tasks
            return current_tasks
        
        except Exception as e:
            print(f"Part 2 Task 업데이트 오류: {str(e)}")
            return current_tasks
    
    def create_part3_tasks(self) -> List[Dict]:
        """
        Part 3 Task 생성 (고정)
        
        Returns:
            Part 3 Task 목록
        """
        return [
            {
                "id": "task_summary_1",
                "part": 3,
                "priority": "high",
                "title": "상담 내용 요약하기",
                "description": "오늘 상담에서 다룬 내용을 요약하고 정리",
                "target": "사용자가 오늘 상담 내용을 이해하고 정리",
                "completion_criteria": "상담 내용을 요약하고 사용자가 확인/동의/감사/만족 표현을 했을 때 완료",
                "status": "pending"
            },
            {
                "id": "task_goal_1",
                "part": 3,
                "priority": "high",
                "title": "상담 목표 설정하기",
                "description": "앞으로의 상담 목표를 설정",
                "target": "구체적이고 달성 가능한 상담 목표 설정",
                "completion_criteria": "상담 목표를 설정하고 사용자가 동의했을 때 완료",
                "status": "pending"
            },
            {
                "id": "task_next_1",
                "part": 3,
                "priority": "medium",
                "title": "다음 상담 안내하기",
                "description": "다음 상담 일정과 준비사항 안내",
                "target": "다음 상담 계획을 수립하고 안내",
                "completion_criteria": "다음 상담 안내를 완료했을 때 완료",
                "status": "pending"
            }
        ]
    
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
  "part": 1|2|3,
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
