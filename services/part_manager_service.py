"""Part Manager Service - Part 관리 및 전환"""
from typing import Dict, List, Optional
from datetime import datetime
from services.session_service import SessionService


class PartManagerService:
    """Part Manager - Part 관리 및 전환"""
    
    def __init__(self):
        self.session_service = SessionService()
    
    def get_current_part(self, conversation_id: str) -> int:
        """
        현재 Part 가져오기
        
        Args:
            conversation_id: 대화 ID
            
        Returns:
            현재 Part 번호 (1, 2, 3)
        """
        session = self.session_service.get_session(conversation_id)
        if not session:
            return 1  # 기본값: Part 1
        
        return session.get('current_part', 1)
    
    def check_part_transition(self, conversation_id: str) -> Optional[int]:
        """
        Part 전환 여부 확인
        
        Args:
            conversation_id: 대화 ID
            
        Returns:
            다음 Part 번호 (전환 가능 시) 또는 None
        """
        session = self.session_service.get_session(conversation_id)
        if not session:
            return None
        
        current_part = session.get('current_part', 1)
        tasks = session.get('tasks', [])
        
        # 현재 Part의 Task만 필터링
        current_part_tasks = [t for t in tasks if t.get('part') == current_part]
        
        if not current_part_tasks:
            return None
        
        # Part 전환 조건 확인
        if current_part == 1:
            # Part 1 → Part 2: 모든 Task가 sufficient 이상
            all_sufficient = all(
                t.get('status') in ['sufficient', 'completed'] 
                for t in current_part_tasks
            )
            if all_sufficient:
                return 2
        
        elif current_part == 2:
            # Part 2 → Part 3: 주요 Task들이 충분히 다뤄짐 (LLM 판단 필요)
            # 여기서는 간단히 모든 Task가 sufficient 이상이면 전환
            # 실제로는 LLM이 판단해야 함
            all_sufficient = all(
                t.get('status') in ['sufficient', 'completed'] 
                for t in current_part_tasks
            )
            if all_sufficient:
                return 3
        
        elif current_part == 3:
            # Part 3 → 종료: 모든 Task 완료
            all_completed = all(
                t.get('status') == 'completed' 
                for t in current_part_tasks
            )
            if all_completed:
                return None  # 종료
        
        return None
    
    def transition_to_part(self, conversation_id: str, part_number: int) -> None:
        """
        Part 전환
        
        Args:
            conversation_id: 대화 ID
            part_number: 전환할 Part 번호 (1, 2, 3)
        """
        session_ref = self.session_service.firestore.db.collection("sessions").document(conversation_id)
        session_ref.update({
            "current_part": part_number,
            "updated_at": datetime.now()
        })
    
