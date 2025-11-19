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
            "status": "active",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "tasks": [],
            "completed_tasks": [],
            "current_task": None,
            "user_info": {},
            "goals": [],
            "supervision_log": [],
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
    
    def complete_task(self, conversation_id: str, task_id: str) -> None:
        """Task 완료 처리"""
        session = self.get_session(conversation_id)
        if not session:
            return
        
        tasks = session.get("tasks", [])
        completed_tasks = session.get("completed_tasks", [])
        
        # Task 찾기
        task = next((t for t in tasks if t.get("id") == task_id), None)
        if task:
            task["completed_at"] = datetime.now().isoformat()
            completed_tasks.append(task)
            
            # tasks에서 제거
            tasks = [t for t in tasks if t.get("id") != task_id]
            
            session_ref = self.firestore.db.collection("sessions").document(conversation_id)
            session_ref.update({
                "tasks": tasks,
                "completed_tasks": completed_tasks,
                "current_task": None,
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

