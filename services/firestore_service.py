"""Firestore 대화 저장 서비스 모듈"""
import os
from datetime import datetime
from typing import List, Dict, Optional
import firebase_admin
from firebase_admin import credentials, firestore
from config import Config


class FirestoreService:
    """Firestore를 사용한 대화 저장 서비스"""
    
    def __init__(self):
        """Firestore 서비스 초기화"""
        # Firebase Admin SDK 초기화 (이미 초기화되어 있지 않은 경우만)
        if not firebase_admin._apps:
            cred_path = Config.GOOGLE_APPLICATION_CREDENTIALS
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
        
        self.db = firestore.client()
        self.collection_name = Config.FIRESTORE_COLLECTION
    
    def create_conversation(self, user_id: str, initial_message: Optional[str] = None) -> str:
        """
        새 대화 생성
        
        Args:
            user_id: 사용자 ID
            initial_message: 초기 메시지 (선택사항)
            
        Returns:
            대화 ID
        """
        conversation_ref = self.db.collection(self.collection_name).document()
        conversation_id = conversation_ref.id
        
        conversation_data = {
            'user_id': user_id,
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
            'messages': []
        }
        
        if initial_message:
            conversation_data['messages'].append({
                'role': 'user',
                'content': initial_message,
                'timestamp': datetime.now()
            })
        
        conversation_ref.set(conversation_data)
        return conversation_id
    
    def add_message(self, conversation_id: str, role: str, content: str) -> None:
        """
        대화에 메시지 추가
        
        Args:
            conversation_id: 대화 ID
            role: 메시지 역할 ('user' 또는 'assistant')
            content: 메시지 내용
        """
        conversation_ref = self.db.collection(self.collection_name).document(conversation_id)
        
        message = {
            'role': role,
            'content': content,
            'timestamp': datetime.now()
        }
        
        conversation_ref.update({
            'messages': firestore.ArrayUnion([message]),
            'updated_at': datetime.now()
        })
    
    def get_conversation(self, conversation_id: str) -> Optional[Dict]:
        """
        대화 가져오기
        
        Args:
            conversation_id: 대화 ID
            
        Returns:
            대화 데이터 또는 None
        """
        conversation_ref = self.db.collection(self.collection_name).document(conversation_id)
        conversation_doc = conversation_ref.get()
        
        if conversation_doc.exists:
            return conversation_doc.to_dict()
        return None
    
    def get_conversation_history(self, conversation_id: str) -> List[Dict]:
        """
        대화 기록 가져오기
        
        Args:
            conversation_id: 대화 ID
            
        Returns:
            메시지 리스트
        """
        conversation = self.get_conversation(conversation_id)
        if conversation:
            return conversation.get('messages', [])
        return []
    
    def list_conversations(self, user_id: str, limit: int = 10) -> List[Dict]:
        """
        사용자의 대화 목록 가져오기
        
        Args:
            user_id: 사용자 ID
            limit: 가져올 대화 개수
            
        Returns:
            대화 목록
        """
        conversations_ref = self.db.collection(self.collection_name)
        # order_by는 복합 인덱스가 필요하므로 제거하고 Python에서 정렬
        query = conversations_ref.where('user_id', '==', user_id).limit(limit * 2)  # 정렬을 위해 더 많이 가져옴
        
        conversations = []
        for doc in query.stream():
            conv_data = doc.to_dict()
            conv_data['id'] = doc.id
            conversations.append(conv_data)
        
        # updated_at 기준으로 내림차순 정렬 (최신순)
        conversations.sort(
            key=lambda x: x.get('updated_at', datetime.min) if isinstance(x.get('updated_at'), datetime) else datetime.min,
            reverse=True
        )
        
        # limit만큼만 반환
        return conversations[:limit]

