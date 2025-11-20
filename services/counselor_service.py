"""Main Counselor LLM 서비스 - Part-Task-Module 구조"""
import os
import time
import logging
import threading
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional
from datetime import datetime
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

# 로깅 설정
log_dir = 'logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

log_file = os.path.join(log_dir, f'counselor_{datetime.now().strftime("%Y%m%d")}.log')

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if logger.handlers:
    logger.handlers.clear()

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
console_handler.setFormatter(console_format)

file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
file_handler.setFormatter(file_format)

logger.addHandler(console_handler)
logger.addHandler(file_handler)


class CounselorService:
    """메인 상담사 LLM - Part-Task-Module 구조"""
    
    def __init__(self):
        """Counselor 초기화"""
        if Config.GOOGLE_APPLICATION_CREDENTIALS and os.path.exists(Config.GOOGLE_APPLICATION_CREDENTIALS):
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = Config.GOOGLE_APPLICATION_CREDENTIALS
        
        self.llm = ChatVertexAI(
            model_name=Config.VERTEX_AI_MODEL,
            project=Config.PROJECT_ID,
            location=Config.LOCATION,
            temperature=0.8,
            max_output_tokens=500,
            model_kwargs={"thinking_budget": 0}
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
        
        # 주기 설정
        self.supervision_interval = Config.SUPERVISION_INTERVAL
        
        # 세션 캐시
        self.session_cache = {}
        
        # Thread pool for parallel execution
        self.executor = ThreadPoolExecutor(max_workers=3)
    
    def get_counselor_prompt(self, current_part: int, current_task: Optional[Dict] = None, 
                            execution_guide: str = "", module_guidelines: str = "",
                            recent_supervision: Optional[Dict] = None,
                            module_changed: bool = False,
                            module_change_reason: Optional[str] = None) -> str:
        """
        메인 상담사 시스템 프롬프트 (최소화)
        
        Args:
            current_part: 현재 Part 번호
            current_task: 현재 Task 정보
            execution_guide: Task 실행 가이드
            module_guidelines: Module 가이드라인 (요약, 3-5줄)
            recent_supervision: Supervision 피드백 (점수 < 7일 때만)
            module_changed: Module 변경 여부
            module_change_reason: Module 변경 이유
        """
        base_prompt = Config.SYSTEM_PROMPT
        
        # Part 정보
        part_info = f"\n현재 Part {current_part} 진행 중입니다.\n"
        
        # Supervision 피드백 (점수 < 7일 때만)
        supervision_guidance = ""
        if recent_supervision and (recent_supervision.get('score', 0) < 7 or recent_supervision.get('needs_improvement', False)):
            score = recent_supervision.get('score', 0)
            improvements = recent_supervision.get('improvements', '')
            supervision_guidance = f"\n=== 개선 필요 ===\n점수: {score}/10\n"
            if improvements and improvements != '없음':
                supervision_guidance += f"개선점: {improvements}\n"
            supervision_guidance += "\n위 피드백을 참고하여 응답을 개선하세요.\n"
        
        # Module 변경 알림
        module_change_info = ""
        if module_changed and module_change_reason:
            module_change_info = f"\n=== Module 변경 ===\n이유: {module_change_reason}\n위 이유를 고려하여 대화를 진행하세요.\n"
        
        # Task 정보 (최소화)
        task_info = ""
        if current_task:
            task_info = f"\n현재 Task: {current_task.get('title', '')}\n목표: {current_task.get('target', '')}\n"
            if execution_guide:
                task_info += f"실행 가이드: {execution_guide}\n"
        
        # Module 가이드라인 (요약만)
        module_info = ""
        if module_guidelines:
            # 가이드라인을 요약 (3-5줄)
            lines = module_guidelines.split('\n')
            summary_lines = [line.strip() for line in lines[:5] if line.strip()]
            if summary_lines:
                module_info = f"\nModule 가이드라인:\n" + "\n".join(summary_lines) + "\n"
        
        return base_prompt + part_info + supervision_guidance + module_change_info + task_info + module_info
    
    def chat(self, conversation_id: str, message: str, 
             conversation_history: Optional[List[Dict]] = None) -> Dict:
        """
        통합 상담 수행 (Part-Task-Module 구조)
        
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
            # 세션 가져오기 또는 생성
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
            current_part = session.get('current_part', 1)
            current_task_id = session.get('current_task')
            current_module_id = session.get('current_module')
            
            # Part Manager: 현재 Part 확인
            current_part = self.part_manager.get_current_part(conversation_id)
            
            # 병렬 실행: Task Completion Checker + User State Detector
            t0 = time.time()
            completion_result = None
            user_state = None
            
            # 현재 Task 찾기
            current_task = None
            if current_task_id:
                current_task = next((t for t in current_tasks if t.get('id') == current_task_id), None)
                
                # 현재 Task가 다른 Part에 속해있으면 None으로 설정 (Part 전환 후 정리)
                if current_task and current_task.get('part') != current_part:
                    logger.info(f"[PART_CHECK] current_task가 다른 Part에 속함: task_part={current_task.get('part')}, current_part={current_part}")
                    current_task = None
                    current_task_id = None
                    session['current_task'] = None
            
            # 병렬 실행
            futures = {}
            if current_task:
                futures['completion'] = self.executor.submit(
                    self.task_completion_checker.check_completion,
                    current_task,
                    conversation_history
                )
            
            futures['user_state'] = self.executor.submit(
                self.user_state_detector.detect_state,
                conversation_history
            )
            
            # 결과 수집
            completion_result = None
            user_state = None
            for future in as_completed(futures.values()):
                result = future.result()
                # future와 매칭되는 키 찾기
                for key, f in futures.items():
                    if f == future:
                        if key == 'completion':
                            completion_result = result
                        elif key == 'user_state':
                            user_state = result
                        break
            
            timing_log['parallel_check'] = time.time() - t0
            
            # User State Detector 결과 로깅
            if user_state:
                logger.info(f"[USER_STATE] resistance={user_state.get('resistance_detected')} | "
                           f"emotion={user_state.get('emotion_change')} | "
                           f"topic_change={user_state.get('topic_change')} | "
                           f"circular={user_state.get('circular_conversation')}")
            
            # Task 완료 여부 확인
            task_completed = completion_result and completion_result.get('is_completed', False)
            
            # 디버깅 로그 추가
            if completion_result:
                logger.info(f"[TASK_COMPLETION] task_id={completion_result.get('task_id')} | "
                           f"is_completed={completion_result.get('is_completed')} | "
                           f"new_status={completion_result.get('new_status')} | "
                           f"reason={completion_result.get('completion_reason', 'N/A')[:100]}")
                logger.debug(f"[TASK_COMPLETION_RAW] {completion_result.get('raw_output', 'N/A')[:500]}")
                # 세션에 로그 저장
                self.session_service.add_completion_log(conversation_id, completion_result)
            
            # Task 완료 시 상태 업데이트
            if task_completed and completion_result.get('new_status'):
                task_id = completion_result.get('task_id')
                new_status = completion_result.get('new_status')
                self.session_service.update_task_status(conversation_id, task_id, new_status)
                # 캐시 업데이트
                for task in current_tasks:
                    if task.get('id') == task_id:
                        task['status'] = new_status
                        break
                session['tasks'] = current_tasks
                self.session_cache[conversation_id] = session
            
            # Task Selector 실행 (Task 완료 시에만)
            task_selection = None
            task_selector_output = None
            if task_completed:
                t0 = time.time()
                # 현재 Part의 Task만 선택
                part_tasks = [t for t in current_tasks if t.get('part') == current_part]
                task_selection = self.task_selector.select_next_task(
                    conversation_history,
                    part_tasks,
                    current_part
                )
                if task_selection:
                    task_selector_output = task_selection.get('raw_output', '')
                timing_log['task_select'] = time.time() - t0
                
                if task_selection:
                    selected_task = task_selection['task']
                    selected_task_status = selected_task.get('status')
                    
                    # 선택된 Task를 current_task로 설정
                    self.session_service.set_current_task(conversation_id, selected_task.get('id'))
                    
                    # sufficient 상태가 아닐 때만 in_progress로 변경
                    if selected_task_status != 'sufficient':
                        self.session_service.update_task_status(conversation_id, selected_task.get('id'), 'in_progress')
                        # 캐시 업데이트
                        for task in current_tasks:
                            if task.get('id') == selected_task.get('id'):
                                task['status'] = 'in_progress'
                                break
                    else:
                        # sufficient 상태는 그대로 유지
                        # 캐시만 업데이트
                        for task in current_tasks:
                            if task.get('id') == selected_task.get('id'):
                                # 이미 sufficient 상태이므로 변경하지 않음
                                break
                    
                    current_task = selected_task
                    current_task_id = selected_task.get('id')
                    session['current_task'] = selected_task.get('id')
                    session['tasks'] = current_tasks
                    self.session_cache[conversation_id] = session
                else:
                    # Task를 선택하지 못했다면 Part 전환 체크
                    # 단, 정말로 모든 Task가 sufficient 이상인지 확인
                    part_tasks_for_check = [t for t in current_tasks if t.get('part') == current_part]
                    all_sufficient_or_completed = all(
                        t.get('status') in ['sufficient', 'completed'] 
                        for t in part_tasks_for_check
                    )
                    
                    if all_sufficient_or_completed:
                        # 모든 Task가 sufficient 이상이면 Part 전환 체크
                        next_part = self.part_manager.check_part_transition(conversation_id)
                    else:
                        # 아직 pending이나 in_progress Task가 있으면 Part 전환하지 않음
                        next_part = None
                    
                    if next_part:
                        # 이전 Part의 sufficient Task들을 completed로 변경
                        previous_part = current_part
                        for task in current_tasks:
                            if task.get('part') == previous_part and task.get('status') == 'sufficient':
                                self.session_service.update_task_status(conversation_id, task.get('id'), 'completed')
                                task['status'] = 'completed'
                        
                        # Part 전환
                        self.part_manager.transition_to_part(conversation_id, next_part)
                        current_part = next_part
                        
                        # Part 2 Task 생성
                        if next_part == 2:
                            part2_tasks = self.task_planner.create_part2_tasks(conversation_history)
                            
                            logger.info(f"[PART_TRANSITION] Part 2 Task 생성: {len(part2_tasks)}개 Task 생성됨")
                            
                            if len(part2_tasks) == 0:
                                logger.warning(f"[PART_TRANSITION] Part 2 Task 생성 실패 - 빈 리스트 반환")
                                # Task 생성 실패 시에도 current_part는 업데이트하되, 기존 Task 유지
                                session_ref = self.session_service.firestore.db.collection("sessions").document(conversation_id)
                                session_ref.update({
                                    "current_part": next_part,
                                    "updated_at": datetime.now()
                                })
                                session['current_part'] = next_part
                                self.session_cache[conversation_id] = session
                            else:
                                # 기존 Task에 추가
                                current_tasks = current_tasks + part2_tasks
                                
                                # Firestore에 저장 (current_part와 tasks 함께 업데이트)
                                session_ref = self.session_service.firestore.db.collection("sessions").document(conversation_id)
                                session_ref.update({
                                    "current_part": next_part,
                                    "tasks": current_tasks,
                                    "updated_at": datetime.now()
                                })
                                
                                logger.info(f"[PART_TRANSITION] Firestore 업데이트 완료: current_part={next_part}, tasks_count={len(current_tasks)}")
                                
                                # 캐시 업데이트
                                session['current_part'] = next_part
                                session['tasks'] = current_tasks
                                self.session_cache[conversation_id] = session
                                
                                logger.info(f"[PART_TRANSITION] 캐시 업데이트 완료: current_part={next_part}, tasks_count={len(current_tasks)}")
                                
                                # Part 2의 첫 번째 Task 선택
                                part2_pending = [t for t in part2_tasks if t.get('status') == 'pending']
                                if part2_pending:
                                    first_task = part2_pending[0]
                                    self.session_service.set_current_task(conversation_id, first_task.get('id'))
                                    self.session_service.update_task_status(conversation_id, first_task.get('id'), 'in_progress')
                                    current_task = first_task
                                    current_task_id = first_task.get('id')
                                    session['current_task'] = first_task.get('id')
                                    self.session_cache[conversation_id] = session
                                    logger.info(f"[PART_TRANSITION] Part 2 첫 번째 Task 선택: {first_task.get('id')}")
                        
                        # Part 3 Task 생성
                        elif next_part == 3:
                            part3_tasks = self.task_planner.create_part3_tasks()
                            
                            logger.info(f"[PART_TRANSITION] Part 3 Task 생성: {len(part3_tasks)}개 Task 생성됨")
                            
                            # 기존 Task에 추가
                            current_tasks = current_tasks + part3_tasks
                            
                            # Firestore에 저장 (current_part와 tasks 함께 업데이트)
                            session_ref = self.session_service.firestore.db.collection("sessions").document(conversation_id)
                            session_ref.update({
                                "current_part": next_part,
                                "tasks": current_tasks,
                                "updated_at": datetime.now()
                            })
                            
                            logger.info(f"[PART_TRANSITION] Firestore 업데이트 완료: current_part={next_part}, tasks_count={len(current_tasks)}")
                            
                            # 캐시 업데이트
                            session['current_part'] = next_part
                            session['tasks'] = current_tasks
                            self.session_cache[conversation_id] = session
                            
                            logger.info(f"[PART_TRANSITION] 캐시 업데이트 완료: current_part={next_part}, tasks_count={len(current_tasks)}")
                            
                            # Part 3의 첫 번째 Task 선택
                            part3_pending = [t for t in part3_tasks if t.get('status') == 'pending']
                            if part3_pending:
                                first_task = part3_pending[0]
                                self.session_service.set_current_task(conversation_id, first_task.get('id'))
                                self.session_service.update_task_status(conversation_id, first_task.get('id'), 'in_progress')
                                current_task = first_task
                                current_task_id = first_task.get('id')
                                session['current_task'] = first_task.get('id')
                                self.session_cache[conversation_id] = session
                                logger.info(f"[PART_TRANSITION] Part 3 첫 번째 Task 선택: {first_task.get('id')}")
            
            # 현재 Task가 없으면 첫 번째 Task 선택
            if not current_task and current_tasks:
                # completed만 제외 (sufficient는 재선택 가능하지만 우선순위 낮음)
                part_tasks = [t for t in current_tasks if t.get('part') == current_part and t.get('status') != 'completed']
                if part_tasks:
                    current_task = part_tasks[0]
                    current_task_id = current_task.get('id')
                    self.session_service.set_current_task(conversation_id, current_task_id)
                    self.session_service.update_task_status(conversation_id, current_task_id, 'in_progress')
                    session['current_task'] = current_task_id
                    self.session_cache[conversation_id] = session
            
            # Module Selector 실행
            t0 = time.time()
            module_result = None
            if current_task:
                # 최근 Supervision 피드백 가져오기
                latest_session = self.session_service.get_session(conversation_id)
                supervision_log = latest_session.get('supervision_log', []) if latest_session else []
                recent_supervision = None
                for log_entry in reversed(supervision_log):
                    log_message_index = log_entry.get('message_index', -1)
                    if log_message_index == message_count - 1:
                        recent_supervision = log_entry
                        break
                
                module_result = self.module_selector.select_module(
                    current_task,
                    user_state or {},
                    current_module_id,
                    recent_supervision
                )
            timing_log['module_select'] = time.time() - t0
            
            # Module 정보 업데이트
            module_changed = False
            module_change_reason = None
            if module_result:
                new_module_id = module_result.get('module_id')
                if new_module_id != current_module_id:
                    module_changed = True
                    module_change_reason = module_result.get('change_reason')
                    # 세션에 Module 정보 저장
                    session_ref = self.session_service.firestore.db.collection("sessions").document(conversation_id)
                    session_ref.update({
                        "current_module": new_module_id,
                        "previous_module": current_module_id,
                        "module_change_reason": module_change_reason,
                        "updated_at": datetime.now()
                    })
                    session['current_module'] = new_module_id
                    session['previous_module'] = current_module_id
                    session['module_change_reason'] = module_change_reason
                    self.session_cache[conversation_id] = session
                current_module_id = new_module_id
            
            # Counselor 프롬프트 구성
            execution_guide = task_selection.get('execution_guide', '') if task_selection else ''
            module_guidelines = module_result.get('module_guidelines', '') if module_result else ''
            
            # 최근 Supervision 피드백 가져오기 (프롬프트용)
            latest_session = self.session_service.get_session(conversation_id)
            supervision_log = latest_session.get('supervision_log', []) if latest_session else []
            recent_supervision_for_prompt = None
            for log_entry in reversed(supervision_log):
                log_message_index = log_entry.get('message_index', -1)
                if log_message_index == message_count - 1:
                    recent_supervision_for_prompt = log_entry
                    break
            
            messages = []
            messages.append(('system', self.get_counselor_prompt(
                current_part,
                current_task,
                execution_guide,
                module_guidelines,
                recent_supervision_for_prompt,
                module_changed,
                module_change_reason
            )))
            
            # 대화 기록 추가 (중복 제거)
            if conversation_history:
                for i, msg in enumerate(conversation_history):
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
            
            # LLM 호출
            counselor_start = time.time()
            full_prompt = self._format_messages_for_display(messages)
            response = self.llm.invoke(messages)
            counselor_response = response.content if hasattr(response, 'content') else str(response)
            timing_log['counselor_llm'] = time.time() - counselor_start
            
            # Supervision 비동기 실행
            supervision_result = None
            if message_count % self.supervision_interval == 0:
                threading.Thread(
                    target=self._run_supervision_async,
                    args=(conversation_id, message, counselor_response, current_task, conversation_history, message_count),
                    daemon=True
                ).start()
            
            # Part 전환 확인 (비동기)
            threading.Thread(
                target=self._check_part_transition_async,
                args=(conversation_id, current_tasks, current_part, conversation_history),
                daemon=True
            ).start()
            
            # Part 2 Task 업데이트 확인 (비동기, Part 2일 때만)
            if current_part == 2 and user_state:
                threading.Thread(
                    target=self._check_part2_task_update_async,
                    args=(conversation_id, current_tasks, conversation_history, user_state),
                    daemon=True
                ).start()
            
            # 메시지 카운트 증가 (비동기)
            threading.Thread(
                target=lambda: self.session_service.increment_message_count(conversation_id),
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
                       f"part={current_part} | "
                       f"task_completed={task_completed} | "
                       f"module_changed={module_changed}")
            
            return {
                "response": counselor_response,
                "current_task": current_task.get('id') if current_task else None,
                "current_part": current_part,
                "current_module": current_module_id,
                "supervision": supervision_result,
                "timing": timing_log,
                "prompt": full_prompt,
                "task_selector_output": task_selector_output  # Task Selector 원본 출력 추가
            }
        
        except Exception as e:
            import traceback
            total_time = time.time() - start_time
            logger.error(f"[ERROR] conversation_id={conversation_id[:8]}... | "
                        f"total={total_time:.2f}s | error={str(e)}")
            raise Exception(f"상담 수행 중 오류 발생: {str(e)}")
    
    def _get_or_create_session(self, conversation_id: str, force_refresh: bool = False) -> Dict:
        """세션 가져오기 또는 생성 (캐시 사용)"""
        # 강제 새로고침이 아니고 캐시가 있으면 캐시 사용
        if not force_refresh and conversation_id in self.session_cache:
            return self.session_cache[conversation_id]
        
        # Firestore에서 가져오기
        session = self.session_service.get_session(conversation_id)
        
        if not session:
            # 새 세션 생성
            session = self.session_service.create_session(
                conversation_id, 
                session_type="first_session"
            )
            # Part 1 초기 Task 생성
            initial_tasks = self.task_planner.create_initial_tasks("first_session")
            self.session_service.update_tasks(conversation_id, initial_tasks)
            session['tasks'] = initial_tasks
        
        # 캐시에 저장
        self.session_cache[conversation_id] = session
        return session
    
    def _check_part_transition_async(self, conversation_id: str, tasks: List[Dict], 
                                    current_part: int, conversation_history: List[Dict]) -> None:
        """Part 전환 확인 (비동기)"""
        try:
            next_part = self.part_manager.check_part_transition(conversation_id)
            
            if next_part:
                # 이전 Part의 sufficient Task들을 completed로 변경
                for task in tasks:
                    if task.get('part') == current_part and task.get('status') == 'sufficient':
                        self.session_service.update_task_status(conversation_id, task.get('id'), 'completed')
                
                # Part 전환
                self.part_manager.transition_to_part(conversation_id, next_part)
                
                # Part 2 Task 생성
                if next_part == 2:
                    part2_tasks = self.task_planner.create_part2_tasks(conversation_history)
                    logger.info(f"[PART_TRANSITION_ASYNC] Part 2 Task 생성: {len(part2_tasks)}개 Task 생성됨")
                    
                    if len(part2_tasks) == 0:
                        logger.warning(f"[PART_TRANSITION_ASYNC] Part 2 Task 생성 실패 - 빈 리스트 반환")
                    else:
                        # 기존 Task에 추가
                        current_tasks = tasks + part2_tasks
                        self.session_service.update_tasks(conversation_id, current_tasks)
                        logger.info(f"[PART_TRANSITION_ASYNC] Firestore 업데이트 완료: tasks_count={len(current_tasks)}")
                        
                        # 캐시 업데이트
                        if conversation_id in self.session_cache:
                            self.session_cache[conversation_id]['tasks'] = current_tasks
                            self.session_cache[conversation_id]['current_part'] = 2
                            logger.info(f"[PART_TRANSITION_ASYNC] 캐시 업데이트 완료: tasks_count={len(current_tasks)}")
                
                # Part 3 Task 생성
                elif next_part == 3:
                    part3_tasks = self.task_planner.create_part3_tasks()
                    current_tasks = tasks + part3_tasks
                    self.session_service.update_tasks(conversation_id, current_tasks)
                    # 캐시 업데이트
                    if conversation_id in self.session_cache:
                        self.session_cache[conversation_id]['tasks'] = current_tasks
                        self.session_cache[conversation_id]['current_part'] = 3
                    
                    # Part 3의 첫 번째 Task 선택
                    part3_pending = [t for t in part3_tasks if t.get('status') == 'pending']
                    if part3_pending:
                        first_task = part3_pending[0]
                        self.session_service.set_current_task(conversation_id, first_task.get('id'))
                        self.session_service.update_task_status(conversation_id, first_task.get('id'), 'in_progress')
                        logger.info(f"[PART_TRANSITION_ASYNC] Part 3 첫 번째 Task 선택: {first_task.get('id')}")
                
                logger.info(f"[PART_TRANSITION] conversation_id={conversation_id[:8]}... | "
                           f"part {current_part} → {next_part}")
        
        except Exception as e:
            logger.error(f"[PART_TRANSITION ERROR] conversation_id={conversation_id[:8]}... | "
                        f"error={str(e)}")
    
    def _extract_part1_info(self, conversation_history: List[Dict]) -> Dict:
        """Part 1에서 수집한 정보 추출"""
        # 대화 내용에서 기본 정보 추출
        user_name = "N/A"
        counseling_purpose = "N/A"
        basic_problem = "N/A"
        
        # 사용자 메시지에서 정보 추출
        for msg in conversation_history:
            if msg.get('role') == 'user':
                content = msg.get('content', '').lower()
                
                # 이름 추출 시도 (간단한 패턴 매칭)
                if '이름' in content or '저는' in content or '제 이름' in content:
                    # 이름 패턴 찾기 (한글 이름 2-4자)
                    name_match = re.search(r'(?:이름|저는|제 이름)[은는이가]?\s*([가-힣]{2,4})', content)
                    if name_match:
                        user_name = name_match.group(1)
                
                # 상담 목적 추출
                if '상담' in content or '도움' in content or '문제' in content or '고민' in content:
                    # 상담 목적 관련 문장 추출
                    purpose_keywords = ['상담', '도움', '조언', '상담받', '상담하']
                    for keyword in purpose_keywords:
                        if keyword in content:
                            # 해당 문장 추출 (최대 100자)
                            sentences = re.split(r'[.!?]', content)
                            for sentence in sentences:
                                if keyword in sentence:
                                    counseling_purpose = sentence.strip()[:100]
                                    break
                            break
                
                # 기본 문제 추출
                problem_keywords = ['문제', '고민', '힘들', '어려', '스트레스', '불안', '우울', '무기력']
                for keyword in problem_keywords:
                    if keyword in content:
                        # 해당 문장 추출 (최대 150자)
                        sentences = re.split(r'[.!?]', content)
                        for sentence in sentences:
                            if keyword in sentence:
                                basic_problem = sentence.strip()[:150]
                                break
                        break
        
        # 대화 요약에서 더 많은 정보 추출 시도
        if user_name == "N/A" or counseling_purpose == "N/A" or basic_problem == "N/A":
            # 최근 사용자 메시지들을 합쳐서 요약
            recent_user_messages = [msg.get('content', '') for msg in conversation_history[-5:] if msg.get('role') == 'user']
            combined_text = ' '.join(recent_user_messages)
            
            if user_name == "N/A" and len(combined_text) > 0:
                # 이름 패턴 다시 찾기
                name_patterns = [
                    r'(?:저는|제 이름은|이름은)\s*([가-힣]{2,4})',
                    r'([가-힣]{2,4})(?:이라고|입니다|이에요)',
                ]
                for pattern in name_patterns:
                    match = re.search(pattern, combined_text)
                    if match:
                        user_name = match.group(1)
                        break
            
            if counseling_purpose == "N/A" and len(combined_text) > 0:
                # 상담 목적 관련 문장 찾기
                if '상담' in combined_text or '도움' in combined_text:
                    # 첫 번째 관련 문장 추출
                    sentences = re.split(r'[.!?]', combined_text)
                    for sentence in sentences:
                        if '상담' in sentence or '도움' in sentence:
                            counseling_purpose = sentence.strip()[:100]
                            break
            
            if basic_problem == "N/A" and len(combined_text) > 0:
                # 문제 관련 문장 찾기
                problem_sentences = []
                for msg in recent_user_messages:
                    if any(keyword in msg.lower() for keyword in ['문제', '고민', '힘들', '어려', '스트레스', '불안', '우울', '무기력']):
                        problem_sentences.append(msg[:150])
                
                if problem_sentences:
                    basic_problem = problem_sentences[0]
        
        return {
            "user_name": user_name,
            "counseling_purpose": counseling_purpose,
            "basic_problem": basic_problem
        }
    
    def _check_part2_task_update_async(self, conversation_id: str, current_tasks: List[Dict],
                                      conversation_history: List[Dict], user_state: Dict) -> None:
        """Part 2 Task 업데이트 확인 (비동기)"""
        try:
            # 세션에서 업데이트 횟수 확인
            session = self.session_service.get_session(conversation_id)
            if not session:
                logger.warning(f"[PART2_UPDATE] 세션을 찾을 수 없음")
                return
            
            update_count = session.get('part2_task_update_count', 0)
            MAX_UPDATE_COUNT = 2
            
            # 이미 최대 횟수에 도달했으면 업데이트하지 않음
            if update_count >= MAX_UPDATE_COUNT:
                logger.info(f"[PART2_UPDATE] 업데이트 횟수 제한 도달: {update_count}/{MAX_UPDATE_COUNT}회")
                return
            
            # 업데이트 조건 확인
            should_update = (
                user_state.get('topic_change', False) or
                user_state.get('resistance_detected', False) or
                user_state.get('circular_conversation', False)
            )
            
            if not should_update:
                logger.debug(f"[PART2_UPDATE] 업데이트 조건 미충족: topic_change={user_state.get('topic_change')}, "
                           f"resistance={user_state.get('resistance_detected')}, "
                           f"circular={user_state.get('circular_conversation')}")
                return
            
            logger.info(f"[PART2_UPDATE] Task 업데이트 시작 ({update_count + 1}/{MAX_UPDATE_COUNT}회): "
                       f"topic_change={user_state.get('topic_change')}, "
                       f"resistance={user_state.get('resistance_detected')}, "
                       f"circular={user_state.get('circular_conversation')}")
            
            # Task 업데이트 실행
            updated_tasks = self.task_planner.update_part2_tasks(
                conversation_history,
                current_tasks,
                user_state,
                should_update=True
            )
            
            if updated_tasks != current_tasks:
                # Firestore 업데이트
                self.session_service.update_tasks(conversation_id, updated_tasks)
                
                # 업데이트 횟수 증가
                session_ref = self.session_service.firestore.db.collection("sessions").document(conversation_id)
                new_update_count = update_count + 1
                session_ref.update({
                    "part2_task_update_count": new_update_count,
                    "updated_at": datetime.now()
                })
                
                # 캐시 업데이트
                if conversation_id in self.session_cache:
                    self.session_cache[conversation_id]['tasks'] = updated_tasks
                    self.session_cache[conversation_id]['part2_task_update_count'] = new_update_count
                
                logger.info(f"[PART2_UPDATE] Task 업데이트 완료 ({new_update_count}/{MAX_UPDATE_COUNT}회): {len(updated_tasks)}개 Task")
            else:
                logger.debug(f"[PART2_UPDATE] Task 업데이트 없음 (조건 충족했으나 변경사항 없음)")
        
        except Exception as e:
            import traceback
            logger.error(f"[PART2_UPDATE] 오류: {str(e)}")
            logger.error(f"[PART2_UPDATE] Traceback: {traceback.format_exc()}")
    
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
            
            supervision_log_entry = {
                "message_index": message_index,
                "user_message": message[:200],
                "counselor_response": counselor_response[:200],
                "score": supervision_result.get('score', 0),
                "feedback": supervision_result.get('feedback', ''),
                "improvements": supervision_result.get('improvements', ''),
                "strengths": supervision_result.get('strengths', ''),
                "needs_improvement": supervision_result.get('needs_improvement', False)
            }
            
            self.session_service.add_supervision_log(conversation_id, supervision_log_entry)
            
            # 캐시 업데이트
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
                       f"score={supervision_log_entry['score']}")
        
        except Exception as e:
            logger.error(f"[SUPERVISION ERROR] conversation_id={conversation_id[:8]}... | "
                        f"error={str(e)}")
    
    def _format_messages_for_display(self, messages: List) -> str:
        """메시지를 표시용 문자열로 변환"""
        prompt_parts = []
        for role, content in messages:
            if role == 'system':
                prompt_parts.append(f"[System]\n{content}\n")
            elif role == 'user':
                prompt_parts.append(f"[User]\n{content}\n")
            elif role == 'assistant':
                prompt_parts.append(f"[Assistant]\n{content}\n")
        
        return "\n".join(prompt_parts)

