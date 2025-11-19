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
            model_kwargs={"thinking_budget": 0}  # Think budget을 0으로 설정하여 빠른 응답
        )
        
        # 서브 서비스들
        self.task_planner = TaskPlannerService()
        self.task_selector = TaskSelectorService()
        self.supervisor = SupervisorService()
        self.session_service = SessionService()
        
        # Supervision 주기 설정 (N개 메시지마다)
        self.supervision_interval = Config.SUPERVISION_INTERVAL
        
        # Task 업데이트 주기 설정 (N개 메시지마다, 기본 3)
        self.task_update_interval = int(os.getenv('TASK_UPDATE_INTERVAL', 3))
        
        # 세션 캐시 (메모리)
        self.session_cache = {}
        
        # Thread pool for parallel execution
        self.executor = ThreadPoolExecutor(max_workers=3)
    
    def get_counselor_prompt(self, current_task: Optional[Dict] = None, 
                            execution_guide: str = "") -> str:
        """메인 상담사 시스템 프롬프트"""
        base_prompt = Config.SYSTEM_PROMPT
        
        if current_task:
            task_guidance = f"""

현재 수행해야 할 task:
- 제목: {current_task.get('title', '')}
- 설명: {current_task.get('description', '')}
- 실행 가이드: {execution_guide if execution_guide else current_task.get('guide', '')}

위 task를 달성하기 위해 대화를 진행하세요. 자연스럽게 task를 수행하면서 사용자와의 대화를 이어가세요."""
            return base_prompt + task_guidance
        
        return base_prompt
    
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
            completed_tasks = session.get('completed_tasks', [])
            message_count = session.get('message_count', 0) + 1
            
            # Task 업데이트는 주기적으로만 실행 (성능 최적화)
            should_update_tasks = (
                len(conversation_history) > 2 and 
                message_count % self.task_update_interval == 0
            )
            
            pending_tasks = [t for t in current_tasks if t.get('status') != 'completed']
            
            # 병렬 처리: Task 업데이트와 Task 선택을 동시에 실행
            t0 = time.time()
            task_selection = None
            updated_tasks = current_tasks
            
            if pending_tasks:
                # 병렬 실행: Task 업데이트와 Task 선택
                futures = {}
                
                if should_update_tasks:
                    task_update_start = time.time()
                    futures['update'] = self.executor.submit(
                        self._timed_task_update,
                        conversation_history,
                        current_tasks,
                        completed_tasks,
                        task_update_start
                    )
                
                task_select_start = time.time()
                futures['select'] = self.executor.submit(
                    self._timed_task_select,
                    conversation_history,
                    pending_tasks,
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
                            pending_tasks = [t for t in updated_tasks if t.get('status') != 'completed']
                    
                    elif task_name == 'select':
                        task_selection = result
                        timing_log['task_select'] = elapsed_time
                        if task_selection:
                            selected_task = task_selection['task']
                            self.session_service.set_current_task(
                                conversation_id, 
                                selected_task.get('id')
                            )
            
            timing_log['parallel_tasks'] = time.time() - t0
            
            # 메인 상담사 응답 생성
            t0 = time.time()
            current_task = task_selection['task'] if task_selection else None
            execution_guide = task_selection['execution_guide'] if task_selection else ""
            
            messages = []
            messages.append(('system', self.get_counselor_prompt(current_task, execution_guide)))
            
            # 대화 기록 추가
            if conversation_history:
                for msg in conversation_history:
                    if msg.get('role') == 'user':
                        messages.append(('user', msg.get('content', '')))
                    elif msg.get('role') == 'assistant':
                        messages.append(('assistant', msg.get('content', '')))
            
            # 현재 메시지 추가
            messages.append(('user', message))
            
            # LLM 호출 (메인 응답)
            counselor_start = time.time()
            response = self.llm.invoke(messages)
            counselor_response = response.content if hasattr(response, 'content') else str(response)
            timing_log['counselor_llm'] = time.time() - counselor_start
            
            # Supervision은 백그라운드에서 비동기 실행 (응답은 먼저 반환)
            supervision_result = None
            if message_count % self.supervision_interval == 0:
                # 백그라운드에서 실행
                threading.Thread(
                    target=self._run_supervision_async,
                    args=(conversation_id, message, counselor_response, current_task, conversation_history),
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
                "tasks_remaining": len(pending_tasks),
                "timing": timing_log  # 디버깅용
            }
            
        except Exception as e:
            total_time = time.time() - start_time
            logger.error(f"[ERROR] conversation_id={conversation_id[:8]}... | "
                        f"total={total_time:.2f}s | error={str(e)}")
            raise Exception(f"상담 수행 중 오류 발생: {str(e)}")
    
    def _timed_task_update(self, conversation_history, current_tasks, completed_tasks, start_time):
        """Task 업데이트 실행 및 시간 측정"""
        result = self.task_planner.update_tasks(conversation_history, current_tasks, completed_tasks)
        elapsed = time.time() - start_time
        return result, elapsed, 'update'
    
    def _timed_task_select(self, conversation_history, pending_tasks, start_time):
        """Task 선택 실행 및 시간 측정"""
        result = self.task_selector.select_next_task(conversation_history, pending_tasks)
        elapsed = time.time() - start_time
        return result, elapsed, 'select'
    
    def _get_or_create_session(self, conversation_id: str) -> Dict:
        """세션 가져오기 또는 생성 (캐시 사용)"""
        # 캐시 확인
        if conversation_id in self.session_cache:
            return self.session_cache[conversation_id]
        
        # Firestore에서 가져오기
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
        
        # 캐시에 저장
        self.session_cache[conversation_id] = session
        return session
    
    def _run_supervision_async(self, conversation_id: str, message: str, 
                              counselor_response: str, current_task: Optional[Dict],
                              conversation_history: List[Dict]) -> None:
        """Supervision을 백그라운드에서 비동기 실행"""
        try:
            supervision_result = self.supervisor.evaluate_response(
                message,
                counselor_response,
                current_task,
                conversation_history
            )
            
            # Supervision 로그 저장
            self.session_service.add_supervision_log(conversation_id, {
                "user_message": message[:200],
                "counselor_response": counselor_response[:200],
                "score": supervision_result['score'],
                "feedback": supervision_result['feedback']
            })
        except Exception as e:
            print(f"Supervision 실행 오류: {str(e)}")

