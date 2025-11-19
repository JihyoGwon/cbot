"""Main Counselor LLM 서비스 - 다른 LLM들과 협력하여 상담 수행"""
import os
import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional
from langchain_google_vertexai import ChatVertexAI
from config import Config
from services.task_planner_service import TaskPlannerService
from services.task_selector_service import TaskSelectorService
from services.supervisor_service import SupervisorService
from services.session_service import SessionService
from services.module_service import ModuleService
from services.session_manager_service import SessionManagerService
from services.part_manager_service import PartManagerService
from services.task_completion_checker_service import TaskCompletionCheckerService
from services.user_state_detector_service import UserStateDetectorService
from services.module_selector_service import ModuleSelectorService

# 로깅 설정 (콘솔 + 파일)
import os
from datetime import datetime

log_dir = 'logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

log_file = os.path.join(log_dir, f'counselor_{datetime.now().strftime("%Y%m%d")}.log')

# 로거 설정
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 기존 핸들러 제거 (중복 방지)
if logger.handlers:
    logger.handlers.clear()

# 콘솔 핸들러
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
console_handler.setFormatter(console_format)

# 파일 핸들러
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
file_handler.setFormatter(file_format)

logger.addHandler(console_handler)
logger.addHandler(file_handler)


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
            max_output_tokens=500,  # 응답 길이 제한 (약 300-400자 정도)
            model_kwargs={"thinking_budget": 0}  # Think budget을 0으로 설정하여 빠른 응답
        )
        
        # 서브 서비스들
        self.part_manager = PartManagerService()
        self.task_planner = TaskPlannerService()
        self.task_selector = TaskSelectorService()
        self.task_completion_checker = TaskCompletionCheckerService()
        self.user_state_detector = UserStateDetectorService()
        self.module_selector = ModuleSelectorService()
        self.supervisor = SupervisorService()
        self.session_service = SessionService()
        self.module_service = ModuleService()
        self.session_manager = SessionManagerService()
        
        # Supervision 주기 설정 (N개 메시지마다)
        self.supervision_interval = Config.SUPERVISION_INTERVAL
        
        # Task 업데이트 주기 설정 (N개 메시지마다, 기본 3)
        self.task_update_interval = int(os.getenv('TASK_UPDATE_INTERVAL', 3))
        
        # Session Manager 주기 설정 (N개 메시지마다, 기본 5)
        self.session_manager_interval = int(os.getenv('SESSION_MANAGER_INTERVAL', 5))
        
        # 세션 캐시 (메모리)
        self.session_cache = {}
        
        # Thread pool for parallel execution
        self.executor = ThreadPoolExecutor(max_workers=3)
    
    def get_counselor_prompt(self, current_task: Optional[Dict] = None, 
                            execution_guide: str = "", module_id: Optional[str] = None,
                            recent_supervision: Optional[Dict] = None,
                            session_status: str = "active",
                            wrap_up_recommendation: Optional[Dict] = None) -> str:
        """메인 상담사 시스템 프롬프트"""
        base_prompt = Config.SYSTEM_PROMPT
        
        # Supervision 피드백 추가
        supervision_guidance = ""
        if recent_supervision:
            score = recent_supervision.get('score', 0)
            feedback = recent_supervision.get('feedback', '')
            improvements = recent_supervision.get('improvements', '')
            strengths = recent_supervision.get('strengths', '')
            
            if score < 7 or recent_supervision.get('needs_improvement', False):
                supervision_guidance = f"""

=== Supervision 피드백 (개선 필요) ===
점수: {score}/10
피드백: {feedback}
"""
                if improvements and improvements != '없음':
                    supervision_guidance += f"개선점: {improvements}\n"
                if strengths and strengths != '없음':
                    supervision_guidance += f"잘한 점: {strengths}\n"
                supervision_guidance += "\n위 피드백을 참고하여 응답을 개선하세요."
            elif feedback:
                supervision_guidance = f"""

=== Supervision 피드백 ===
점수: {score}/10
피드백: {feedback}
"""
                if improvements and improvements != '없음':
                    supervision_guidance += f"개선점: {improvements}\n"
                if strengths and strengths != '없음':
                    supervision_guidance += f"잘한 점: {strengths}\n"
                supervision_guidance += "\n위 피드백을 참고하여 계속 좋은 상담을 진행하세요."
        else:
            # Supervision 피드백이 없을 때도 명시적으로 표시 (디버깅용)
            supervision_guidance = "\n\n=== Supervision 피드백: 없음 (아직 평가되지 않음) ==="
        
        # Session Manager 종료 제안 추가
        session_guidance = ""
        if session_status == "wrapping_up" and wrap_up_recommendation:
            recommendation = wrap_up_recommendation.get('recommendation', '')
            completion_score = wrap_up_recommendation.get('completion_score', 0.0)
            missing_goals = wrap_up_recommendation.get('missing_goals', [])
            
            session_guidance = f"""

=== 상담 마무리 제안 ===
첫 회기 상담 목표 달성도: {completion_score:.1%}
"""
            if missing_goals:
                session_guidance += f"미달성 목표: {', '.join(missing_goals)}\n"
            
            session_guidance += """
이제 상담을 자연스럽게 마무리하세요:
1. 오늘 상담 내용 요약
2. 다음 상담 안내
3. 추가 질문이나 도움이 필요한지 확인

사용자가 추가 질문이 있으면 계속 진행하고, 만족하면 자연스럽게 마무리하세요."""
        
        if current_task:
            # Module 가이드라인 가져오기
            module_guidelines = ""
            if module_id:
                module_guidelines = self.module_service.get_module_guidelines(module_id)
            
            task_guidance = f"""

현재 수행해야 할 task:
- 제목: {current_task.get('title', '')}
- 설명: {current_task.get('description', '')}
- 목표: {current_task.get('target', '')}
- 실행 가이드: {execution_guide if execution_guide else current_task.get('target', '')}
"""
            
            if module_guidelines:
                task_guidance += f"""
사용할 Module 가이드라인:
{module_guidelines}
"""
            
            task_guidance += "\n위 task를 달성하기 위해 대화를 진행하세요. 자연스럽게 task를 수행하면서 사용자와의 대화를 이어가세요."
            
            return base_prompt + supervision_guidance + session_guidance + task_guidance
        
        return base_prompt + supervision_guidance + session_guidance
    
    def chat(self, conversation_id: str, message: str, 
             conversation_history: Optional[List[Dict]] = None) -> Dict:
        """
        통합 상담 수행 (최적화: 병렬 처리 및 비동기 실행)
        
        Args:
            conversation_id: 대화 ID
            message: 사용자 메시지
            conversation_history: 대화 기록
            
        Returns:
            상담사 응답 및 메타데이터
        """
        start_time = time.time()
        timing_log = {}
        
        try:
            # 세션 가져오기 또는 생성 (캐시 사용)
            t0 = time.time()
            session = self._get_or_create_session(conversation_id)
            timing_log['session_load'] = time.time() - t0
            
            # 대화 기록 가져오기
            t0 = time.time()
            if not conversation_history:
                from services.firestore_service import FirestoreService
                firestore = FirestoreService()
                conversation_history = firestore.get_conversation_history(conversation_id)
            timing_log['history_load'] = time.time() - t0
            
            current_tasks = session.get('tasks', [])
            message_count = session.get('message_count', 0) + 1
            
            # 최근 Supervision 피드백 가져오기 (항상 Firestore에서 최신 로그 가져오기)
            # 캐시는 비동기 업데이트로 인해 최신이 아닐 수 있으므로 Firestore에서 직접 가져옴
            latest_session = self.session_service.get_session(conversation_id)
            supervision_log = latest_session.get('supervision_log', []) if latest_session else []
            recent_supervision = None
            
            # Supervision 피드백은 정확히 한 턴에만 적용되어야 함
            # n-2턴의 Supervision은 n-1턴에만 적용되고, n턴에는 적용되지 않아야 함
            # 따라서 message_index가 정확히 message_count - 1인 Supervision만 사용
            # (직전 턴에서 생성된 Supervision만 사용)
            for log_entry in reversed(supervision_log):
                log_message_index = log_entry.get('message_index', -1)
                # 직전 턴의 Supervision만 사용 (message_count - 1)
                # 이전 턴의 Supervision은 사용하지 않음
                if log_message_index == message_count - 1:
                    recent_supervision = log_entry
                    break
            
            # 직전 턴의 Supervision이 없으면 Supervision 피드백 없음
            # (이전 턴의 Supervision을 재사용하지 않음)
            
            # 디버깅: Supervision 피드백 상태 로깅
            if recent_supervision:
                logger.info(f"[SUPERVISION] conversation_id={conversation_id[:8]}... | "
                           f"message_count={message_count} | "
                           f"supervision_message_index={recent_supervision.get('message_index', 'N/A')} | "
                           f"expected_message_index={message_count - 1} | "
                           f"score={recent_supervision.get('score', 'N/A')} | "
                           f"has_feedback={bool(recent_supervision.get('feedback'))} | "
                           f"all_supervision_indices={[log.get('message_index', -1) for log in supervision_log]}")
            else:
                logger.info(f"[SUPERVISION] conversation_id={conversation_id[:8]}... | "
                           f"message_count={message_count} | "
                           f"expected_message_index={message_count - 1} | "
                           f"no_recent_supervision (log_length={len(supervision_log)} | "
                           f"all_supervision_indices={[log.get('message_index', -1) for log in supervision_log]})")
            
            # Task 업데이트는 주기적으로만 실행 (성능 최적화)
            should_update_tasks = (
                len(conversation_history) > 2 and 
                message_count % self.task_update_interval == 0
            )
            
            # 선택 가능한 task (completed 제외)
            selectable_tasks = [t for t in current_tasks if t.get('status') != 'completed']
            
            # 병렬 처리: Task 업데이트와 Task 선택을 동시에 실행
            t0 = time.time()
            task_selection = None
            updated_tasks = current_tasks
            
            if selectable_tasks:
                # 병렬 실행: Task 업데이트와 Task 선택
                futures = {}
                
                if should_update_tasks:
                    task_update_start = time.time()
                    futures['update'] = self.executor.submit(
                        self._timed_task_update,
                        conversation_history,
                        current_tasks,
                        task_update_start
                    )
                
                task_select_start = time.time()
                futures['select'] = self.executor.submit(
                    self._timed_task_select,
                    conversation_history,
                    selectable_tasks,
                    task_select_start
                )
                
                # 결과 수집 (먼저 완료되는 것부터 처리)
                for future in as_completed(futures.values()):
                    result, elapsed_time, task_name = future.result()
                    
                    if task_name == 'update':
                        updated_tasks = result
                        timing_log['task_update'] = elapsed_time
                        if updated_tasks != current_tasks:
                            self.session_service.update_tasks(conversation_id, updated_tasks)
                            session['tasks'] = updated_tasks
                            self.session_cache[conversation_id] = session
                            # 업데이트 후 selectable_tasks 재계산
                            selectable_tasks = [t for t in updated_tasks if t.get('status') != 'completed']
                    
                    elif task_name == 'select':
                        task_selection = result
                        timing_log['task_select'] = elapsed_time
                        if task_selection:
                            selected_task = task_selection['task']
                            # 선택된 task의 status를 in_progress로 업데이트
                            if selected_task.get('status') != 'in_progress':
                                self.session_service.update_task_status(
                                    conversation_id,
                                    selected_task.get('id'),
                                    'in_progress'
                                )
                                # 캐시 업데이트
                                for task in session.get('tasks', []):
                                    if task.get('id') == selected_task.get('id'):
                                        task['status'] = 'in_progress'
                                        break
                                self.session_cache[conversation_id] = session
                            
                            self.session_service.set_current_task(
                                conversation_id, 
                                selected_task.get('id')
                            )
            
            timing_log['parallel_tasks'] = time.time() - t0
            
            # 메인 상담사 응답 생성
            t0 = time.time()
            current_task = task_selection['task'] if task_selection else None
            execution_guide = task_selection['execution_guide'] if task_selection else ""
            module_id = task_selection.get('module_id') if task_selection else None
            
            # Session Manager 평가 결과 가져오기 (최근 평가)
            session_manager_log = session.get('session_manager_log', [])
            recent_evaluation = session_manager_log[-1] if session_manager_log else None
            wrap_up_recommendation = None
            if recent_evaluation and recent_evaluation.get('recommendation') in ['wrap_up', 'complete']:
                wrap_up_recommendation = recent_evaluation
            
            messages = []
            messages.append(('system', self.get_counselor_prompt(
                current_task, 
                execution_guide, 
                module_id,
                recent_supervision,
                session.get('status', 'active'),
                wrap_up_recommendation
            )))
            
            # 대화 기록 추가
            # conversation_history에는 이미 현재 사용자 메시지가 포함되어 있을 수 있으므로
            # 마지막 사용자 메시지는 제외하고 추가
            if conversation_history:
                for i, msg in enumerate(conversation_history):
                    # 마지막 메시지가 사용자 메시지이고 현재 메시지와 같으면 건너뛰기
                    is_last_user_msg = (
                        i == len(conversation_history) - 1 and 
                        msg.get('role') == 'user' and 
                        msg.get('content', '').strip() == message.strip()
                    )
                    if is_last_user_msg:
                        continue
                    
                    if msg.get('role') == 'user':
                        messages.append(('user', msg.get('content', '')))
                    elif msg.get('role') == 'assistant':
                        messages.append(('assistant', msg.get('content', '')))
            
            # 현재 메시지 추가
            messages.append(('user', message))
            
            # LLM 호출 (메인 응답)
            counselor_start = time.time()
            
            # 프롬프트 구성 (나중에 저장하기 위해)
            full_prompt = self._format_messages_for_display(messages)
            
            response = self.llm.invoke(messages)
            counselor_response = response.content if hasattr(response, 'content') else str(response)
            timing_log['counselor_llm'] = time.time() - counselor_start
            
            # Supervision은 백그라운드에서 비동기 실행 (응답은 먼저 반환)
            # 현재 사용된 Supervision 정보를 반환값에 포함 (프론트 표시용)
            supervision_result = None
            if recent_supervision:
                supervision_result = {
                    'score': recent_supervision.get('score', 0),
                    'feedback': recent_supervision.get('feedback', ''),
                    'improvements': recent_supervision.get('improvements', ''),
                    'strengths': recent_supervision.get('strengths', ''),
                    'needs_improvement': recent_supervision.get('needs_improvement', False),
                    'message_index': recent_supervision.get('message_index', -1)
                }
            
            if message_count % self.supervision_interval == 0:
                # 백그라운드에서 실행 (메시지 인덱스 전달)
                threading.Thread(
                    target=self._run_supervision_async,
                    args=(conversation_id, message, counselor_response, current_task, conversation_history, message_count),
                    daemon=True
                ).start()
            
            # Session Manager는 백그라운드에서 비동기 실행 (5개 메시지마다)
            if message_count % self.session_manager_interval == 0:
                # 백그라운드에서 실행
                threading.Thread(
                    target=self._run_session_manager_async,
                    args=(conversation_id, conversation_history, current_tasks, session.get('session_type', 'first_session')),
                    daemon=True
                ).start()
            
            # 메시지 카운트 증가 (비동기)
            def update_message_count():
                self.session_service.increment_message_count(conversation_id)
                # 캐시 업데이트
                if conversation_id in self.session_cache:
                    self.session_cache[conversation_id]['message_count'] = message_count
            
            threading.Thread(
                target=update_message_count,
                daemon=True
            ).start()
            
            # 캐시 업데이트
            session['message_count'] = message_count
            self.session_cache[conversation_id] = session
            
            # 전체 시간 계산
            total_time = time.time() - start_time
            timing_log['total'] = total_time
            
            # 로깅
            logger.info(f"[LATENCY] conversation_id={conversation_id[:8]}... | "
                       f"total={total_time:.2f}s | "
                       f"session={timing_log.get('session_load', 0):.2f}s | "
                       f"history={timing_log.get('history_load', 0):.2f}s | "
                       f"parallel={timing_log.get('parallel_tasks', 0):.2f}s | "
                       f"task_update={timing_log.get('task_update', 0):.2f}s | "
                       f"task_select={timing_log.get('task_select', 0):.2f}s | "
                       f"counselor_llm={timing_log.get('counselor_llm', 0):.2f}s")
            
            return {
                "response": counselor_response,
                "current_task": current_task.get('id') if current_task else None,
                "supervision": supervision_result,
                "tasks_remaining": len(selectable_tasks),
                "timing": timing_log,  # 디버깅용
                "prompt": full_prompt  # 프롬프트 전문
            }
            
        except Exception as e:
            total_time = time.time() - start_time
            logger.error(f"[ERROR] conversation_id={conversation_id[:8]}... | "
                        f"total={total_time:.2f}s | error={str(e)}")
            raise Exception(f"상담 수행 중 오류 발생: {str(e)}")
    
    def _timed_task_update(self, conversation_history, current_tasks, start_time):
        """Task 업데이트 실행 및 시간 측정"""
        result = self.task_planner.update_tasks(conversation_history, current_tasks)
        elapsed = time.time() - start_time
        return result, elapsed, 'update'
    
    def _timed_task_select(self, conversation_history, pending_tasks, start_time):
        """Task 선택 실행 및 시간 측정"""
        result = self.task_selector.select_next_task(conversation_history, pending_tasks)
        elapsed = time.time() - start_time
        return result, elapsed, 'select'
    
    def _format_messages_for_display(self, messages: List) -> str:
        """메시지 리스트를 프롬프트 문자열로 변환"""
        prompt_parts = []
        for msg in messages:
            role = msg[0] if isinstance(msg, tuple) else msg.get('role', 'unknown')
            content = msg[1] if isinstance(msg, tuple) else msg.get('content', '')
            
            if role == 'system':
                prompt_parts.append(f"=== SYSTEM PROMPT ===\n{content}\n")
            elif role == 'user':
                prompt_parts.append(f"=== USER ===\n{content}\n")
            elif role == 'assistant':
                prompt_parts.append(f"=== ASSISTANT ===\n{content}\n")
        
        return "\n".join(prompt_parts)
    
    def _get_or_create_session(self, conversation_id: str) -> Dict:
        """세션 가져오기 또는 생성 (캐시 사용, 하지만 Supervision 로그는 항상 최신 확인)"""
        # Firestore에서 최신 세션 가져오기 (Supervision 로그가 최신인지 확인하기 위해)
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
        
        # 캐시가 있으면 tasks 등은 캐시에서 가져오되, supervision_log는 최신으로 업데이트
        if conversation_id in self.session_cache:
            cached_session = self.session_cache[conversation_id]
            # Supervision 로그는 항상 최신 것으로 업데이트
            session['supervision_log'] = session.get('supervision_log', [])
            # 캐시의 다른 정보는 유지하되 supervision_log는 최신으로
            cached_session['supervision_log'] = session['supervision_log']
            self.session_cache[conversation_id] = cached_session
            return cached_session
        
        # 캐시에 저장
        self.session_cache[conversation_id] = session
        return session
    
    def _run_supervision_async(self, conversation_id: str, message: str, 
                              counselor_response: str, current_task: Optional[Dict],
                              conversation_history: List[Dict], message_index: int) -> None:
        """Supervision을 백그라운드에서 비동기 실행"""
        try:
            supervision_result = self.supervisor.evaluate_response(
                message,
                counselor_response,
                current_task,
                conversation_history
            )
            
            # Supervision 로그 저장 (모든 필드 포함, 메시지 인덱스 포함)
            supervision_log_entry = {
                "message_index": message_index,  # 어떤 메시지에 대한 Supervision인지 저장
                "user_message": message[:200],
                "counselor_response": counselor_response[:200],
                "score": supervision_result.get('score', 0),
                "feedback": supervision_result.get('feedback', ''),
                "improvements": supervision_result.get('improvements', ''),
                "strengths": supervision_result.get('strengths', ''),
                "needs_improvement": supervision_result.get('needs_improvement', False)
            }
            
            self.session_service.add_supervision_log(conversation_id, supervision_log_entry)
            
            # 캐시 업데이트 (다음 요청에서 Supervision 피드백이 반영되도록)
            if conversation_id in self.session_cache:
                session = self.session_cache[conversation_id]
                supervision_log = session.get('supervision_log', [])
                supervision_log.append({
                    **supervision_log_entry,
                    "timestamp": datetime.now().isoformat()
                })
                session['supervision_log'] = supervision_log
                self.session_cache[conversation_id] = session
            
            logger.info(f"[SUPERVISION] conversation_id={conversation_id[:8]}... | "
                       f"score={supervision_log_entry['score']} | "
                       f"feedback_saved=True")
        except Exception as e:
            logger.error(f"[SUPERVISION ERROR] conversation_id={conversation_id[:8]}... | "
                        f"error={str(e)}")
            print(f"Supervision 실행 오류: {str(e)}")
    
    def _run_session_manager_async(self, conversation_id: str, conversation_history: List[Dict],
                                   tasks: List[Dict], session_type: str) -> None:
        """Session Manager를 백그라운드에서 비동기 실행"""
        try:
            evaluation_result = self.session_manager.evaluate_session(
                conversation_history,
                tasks,
                session_type
            )
            
            # Session Manager 로그 저장
            self.session_service.add_session_manager_log(conversation_id, {
                "completion_score": evaluation_result.get('completion_score', 0.0),
                "rapport_building": evaluation_result.get('rapport_building', 0.0),
                "information_gathering": evaluation_result.get('information_gathering', 0.0),
                "goal_setting": evaluation_result.get('goal_setting', 0.0),
                "trust_building": evaluation_result.get('trust_building', 0.0),
                "recommendation": evaluation_result.get('recommendation', 'continue'),
                "session_status": evaluation_result.get('session_status', 'active'),
                "first_session_goals_met": evaluation_result.get('first_session_goals_met', False),
                "missing_goals": evaluation_result.get('missing_goals', [])
            })
            
            # 세션 상태 업데이트
            session_status = evaluation_result.get('session_status', 'active')
            self.session_service.update_session_status(conversation_id, session_status)
            
            # wrap_up_tasks가 있으면 Task Planner에 추가
            wrap_up_tasks = evaluation_result.get('wrap_up_tasks', [])
            if wrap_up_tasks and session_status == 'wrapping_up':
                # 기존 tasks에 wrap_up_tasks 추가 (우선순위 high)
                session = self.session_service.get_session(conversation_id)
                if session:
                    current_tasks = session.get('tasks', [])
                    # wrap_up_tasks에 status와 priority 추가
                    for task in wrap_up_tasks:
                        task['status'] = 'pending'
                        task['priority'] = 'high'
                        # 이미 존재하는 task인지 확인
                        if not any(t.get('id') == task.get('id') for t in current_tasks):
                            current_tasks.append(task)
                    
                    self.session_service.update_tasks(conversation_id, current_tasks)
                    
                    # 캐시 업데이트
                    if conversation_id in self.session_cache:
                        self.session_cache[conversation_id]['tasks'] = current_tasks
                        self.session_cache[conversation_id]['status'] = session_status
            
            logger.info(f"[SESSION_MANAGER] conversation_id={conversation_id[:8]}... | "
                       f"completion_score={evaluation_result.get('completion_score', 0.0):.2f} | "
                       f"recommendation={evaluation_result.get('recommendation', 'continue')} | "
                       f"session_status={session_status}")
        except Exception as e:
            logger.error(f"[SESSION_MANAGER ERROR] conversation_id={conversation_id[:8]}... | "
                        f"error={str(e)}")
            print(f"Session Manager 실행 오류: {str(e)}")

