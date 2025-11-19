"""상담 세션 관리 서비스"""
from typing import Dict, List, Optional
from datetime import datetime
from services.firestore_service import FirestoreService


class SessionService:
    """상담 세션 상태 관리"""
    
    def __init__(self):
        self.firestore = FirestoreService()
    
    def create_session(self, conversation_id: str, session_type: str = "first_session") -> Dict:
        """
        새 상담 세션 생성
        
        Args:
            conversation_id: 대화 ID
            session_type: 세션 타입 (first_session 등)
            
        Returns:
            세션 데이터
        """
        session_data = {
            "conversation_id": conversation_id,
            "session_type": session_type,
            "status": "active",  # active, wrapping_up, completed
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "tasks": [],  # 모든 상태의 task 포함 (completed 포함)
            "current_task": None,
            "user_info": {},
            "goals": [],
            "supervision_log": [],
            "session_manager_log": [],  # Session Manager 평가 로그
            "message_count": 0
        }
        
        # Firestore에 세션 저장
        session_ref = self.firestore.db.collection("sessions").document(conversation_id)
        session_ref.set(session_data)
        
        return session_data
    
    def get_session(self, conversation_id: str) -> Optional[Dict]:
        """세션 가져오기"""
        session_ref = self.firestore.db.collection("sessions").document(conversation_id)
        session_doc = session_ref.get()
        
        if session_doc.exists:
            return session_doc.to_dict()
        return None
    
    def update_tasks(self, conversation_id: str, tasks: List[Dict]) -> None:
        """Task 목록 업데이트"""
        session_ref = self.firestore.db.collection("sessions").document(conversation_id)
        session_ref.update({
            "tasks": tasks,
            "updated_at": datetime.now()
        })
    
    def set_current_task(self, conversation_id: str, task_id: str) -> None:
        """현재 실행 중인 task 설정"""
        session_ref = self.firestore.db.collection("sessions").document(conversation_id)
        session_ref.update({
            "current_task": task_id,
            "updated_at": datetime.now()
        })
    
    def update_task_status(self, conversation_id: str, task_id: str, status: str) -> None:
        """
        Task 상태 업데이트
        
        Args:
            conversation_id: 대화 ID
            task_id: Task ID
            status: 새로운 상태 (pending, in_progress, sufficient, completed)
        """
        session = self.get_session(conversation_id)
        if not session:
            return
        
        tasks = session.get("tasks", [])
        
        # Task 찾기
        task = next((t for t in tasks if t.get("id") == task_id), None)
        if task:
            task["status"] = status
            
            # 상태별 타임스탬프 업데이트
            if status == "sufficient" and not task.get("sufficient_at"):
                task["sufficient_at"] = datetime.now().isoformat()
            elif status == "completed" and not task.get("completed_at"):
                task["completed_at"] = datetime.now().isoformat()
            
            # tasks 리스트 업데이트
            tasks = [t if t.get("id") != task_id else task for t in tasks]
            
            session_ref = self.firestore.db.collection("sessions").document(conversation_id)
            session_ref.update({
                "tasks": tasks,
                "updated_at": datetime.now()
            })
    
    def update_session_status(self, conversation_id: str, status: str) -> None:
        """
        세션 상태 업데이트
        
        Args:
            conversation_id: 대화 ID
            status: 새로운 상태 (active, wrapping_up, completed)
        """
        session_ref = self.firestore.db.collection("sessions").document(conversation_id)
        session_ref.update({
            "status": status,
            "updated_at": datetime.now()
        })
    
    def add_session_manager_log(self, conversation_id: str, evaluation: Dict) -> None:
        """Session Manager 평가 로그 추가"""
        session = self.get_session(conversation_id)
        if not session:
            return
        
        session_manager_log = session.get("session_manager_log", [])
        session_manager_log.append({
            **evaluation,
            "timestamp": datetime.now().isoformat()
        })
        
        session_ref = self.firestore.db.collection("sessions").document(conversation_id)
        session_ref.update({
            "session_manager_log": session_manager_log,
            "updated_at": datetime.now()
        })
    
    def add_supervision_log(self, conversation_id: str, feedback: Dict) -> None:
        """Supervision 피드백 로그 추가"""
        session = self.get_session(conversation_id)
        if not session:
            return
        
        supervision_log = session.get("supervision_log", [])
        supervision_log.append({
            **feedback,
            "timestamp": datetime.now().isoformat()
        })
        
        session_ref = self.firestore.db.collection("sessions").document(conversation_id)
        session_ref.update({
            "supervision_log": supervision_log,
            "updated_at": datetime.now()
        })
    
    def increment_message_count(self, conversation_id: str) -> None:
        """메시지 카운트 증가"""
        from firebase_admin import firestore
        session_ref = self.firestore.db.collection("sessions").document(conversation_id)
        session_ref.update({
            "message_count": firestore.Increment(1),
            "updated_at": datetime.now()
        })

