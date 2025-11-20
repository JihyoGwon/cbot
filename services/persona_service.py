"""페르소나 관리 서비스"""
from typing import Dict, List, Optional
from datetime import datetime
from services.firestore_service import FirestoreService


class PersonaService:
    """사용자 페르소나 관리 서비스"""
    
    def __init__(self):
        self.firestore = FirestoreService()
        self.collection_name = "personas"
    
    def create_persona(self, persona_data: Dict) -> Dict:
        """
        새 페르소나 타입 생성
        
        Args:
            persona_data: 페르소나 데이터
                {
                    "id": "type_a",
                    "name": "완벽주의 성향",
                    "description": "...",
                    "type_specific_keywords": ["키워드1", "키워드2", "키워드3", "키워드4"],
                    "common_keywords": ["공통키워드1", "공통키워드2", "공통키워드3", "공통키워드4"]
                }
        
        Returns:
            생성된 페르소나 데이터
        """
        persona_id = persona_data.get('id')
        if not persona_id:
            raise ValueError("페르소나 ID가 필요합니다.")
        
        # 기존 페르소나 확인
        existing = self.get_persona(persona_id)
        if existing:
            raise ValueError(f"페르소나 '{persona_id}'가 이미 존재합니다.")
        
        # 공통 키워드는 한 번만 저장 (첫 번째 페르소나 생성 시)
        common_keywords = persona_data.get('common_keywords', [])
        if common_keywords:
            self._save_common_keywords(common_keywords)
        
        # 페르소나 데이터 준비
        persona_doc = {
            "id": persona_id,
            "name": persona_data.get('name', ''),
            "description": persona_data.get('description', ''),
            "type_specific_keywords": persona_data.get('type_specific_keywords', []),
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        
        # Firestore에 저장
        persona_ref = self.firestore.db.collection(self.collection_name).document(persona_id)
        persona_ref.set(persona_doc)
        
        # 공통 키워드 추가하여 반환
        persona_doc['common_keywords'] = self.get_common_keywords()
        
        return persona_doc
    
    def get_persona(self, persona_id: str) -> Optional[Dict]:
        """
        페르소나 타입 가져오기
        
        Args:
            persona_id: 페르소나 ID
        
        Returns:
            페르소나 데이터 또는 None
        """
        persona_ref = self.firestore.db.collection(self.collection_name).document(persona_id)
        persona_doc = persona_ref.get()
        
        if persona_doc.exists:
            data = persona_doc.to_dict()
            # 공통 키워드 추가
            data['common_keywords'] = self.get_common_keywords()
            return data
        return None
    
    def list_personas(self) -> List[Dict]:
        """
        모든 페르소나 타입 목록 가져오기
        
        Returns:
            페르소나 목록
        """
        personas_ref = self.firestore.db.collection(self.collection_name)
        personas_docs = personas_ref.stream()
        
        personas = []
        common_keywords = self.get_common_keywords()
        
        for doc in personas_docs:
            # _common 문서는 제외
            if doc.id == '_common':
                continue
            
            data = doc.to_dict()
            if data:  # 데이터가 있는 경우만 추가
                data['common_keywords'] = common_keywords
                personas.append(data)
        
        # ID로 정렬
        personas.sort(key=lambda x: x.get('id', ''))
        
        return personas
    
    def update_persona(self, persona_id: str, updates: Dict) -> Dict:
        """
        페르소나 타입 수정
        
        Args:
            persona_id: 페르소나 ID
            updates: 수정할 필드들
                {
                    "name": "...",
                    "description": "...",
                    "type_specific_keywords": [...]
                }
        
        Returns:
            수정된 페르소나 데이터
        """
        persona_ref = self.firestore.db.collection(self.collection_name).document(persona_id)
        persona_doc = persona_ref.get()
        
        if not persona_doc.exists:
            raise ValueError(f"페르소나 '{persona_id}'를 찾을 수 없습니다.")
        
        # 업데이트할 데이터 준비
        update_data = {
            "updated_at": datetime.now()
        }
        
        if 'name' in updates:
            update_data['name'] = updates['name']
        if 'description' in updates:
            update_data['description'] = updates['description']
        if 'type_specific_keywords' in updates:
            update_data['type_specific_keywords'] = updates['type_specific_keywords']
        
        # Firestore 업데이트
        persona_ref.update(update_data)
        
        # 업데이트된 데이터 반환
        updated_doc = persona_ref.get()
        data = updated_doc.to_dict()
        data['common_keywords'] = self.get_common_keywords()
        
        return data
    
    def delete_persona(self, persona_id: str) -> bool:
        """
        페르소나 타입 삭제
        
        Args:
            persona_id: 페르소나 ID
        
        Returns:
            삭제 성공 여부
        """
        persona_ref = self.firestore.db.collection(self.collection_name).document(persona_id)
        persona_doc = persona_ref.get()
        
        if not persona_doc.exists:
            raise ValueError(f"페르소나 '{persona_id}'를 찾을 수 없습니다.")
        
        persona_ref.delete()
        return True
    
    def get_common_keywords(self) -> List[str]:
        """
        공통 키워드 가져오기
        
        Returns:
            공통 키워드 리스트
        """
        common_ref = self.firestore.db.collection("personas").document("_common")
        common_doc = common_ref.get()
        
        if common_doc.exists:
            data = common_doc.to_dict()
            return data.get('keywords', [])
        
        # 기본 공통 키워드 반환
        return ["감정 인식", "자기 이해", "대인 관계", "자기 돌봄"]
    
    def update_common_keywords(self, keywords: List[str]) -> List[str]:
        """
        공통 키워드 업데이트
        
        Args:
            keywords: 공통 키워드 리스트 (4개)
        
        Returns:
            업데이트된 공통 키워드 리스트
        """
        if len(keywords) != 4:
            raise ValueError("공통 키워드는 정확히 4개여야 합니다.")
        
        self._save_common_keywords(keywords)
        return keywords
    
    def _save_common_keywords(self, keywords: List[str]):
        """공통 키워드를 Firestore에 저장"""
        common_ref = self.firestore.db.collection("personas").document("_common")
        common_ref.set({
            "keywords": keywords,
            "updated_at": datetime.now()
        })
    
    def initialize_default_personas(self):
        """기본 페르소나 타입 초기화 (16개)"""
        default_personas = [
            {
                "id": "type_a",
                "name": "완벽주의 성향",
                "description": "높은 자기 기대와 완벽을 추구하는 성향",
                "type_specific_keywords": ["완벽주의", "자기 비판", "스트레스 관리", "목표 설정"]
            },
            {
                "id": "type_b",
                "name": "회피 성향",
                "description": "갈등과 어려운 상황을 회피하는 성향",
                "type_specific_keywords": ["갈등 회피", "감정 표현", "자기 주장", "경계 설정"]
            },
            {
                "id": "type_c",
                "name": "의존 성향",
                "description": "타인에게 의존하는 경향이 강한 성향",
                "type_specific_keywords": ["의존성", "자기 결정", "자기 효능감", "독립성"]
            },
            {
                "id": "type_d",
                "name": "불안 성향",
                "description": "불안과 걱정이 많은 성향",
                "type_specific_keywords": ["불안", "걱정", "안정감", "대처 전략"]
            },
            {
                "id": "type_e",
                "name": "우울 성향",
                "description": "우울감과 무기력이 있는 성향",
                "type_specific_keywords": ["우울", "무기력", "동기 부여", "긍정적 사고"]
            },
            {
                "id": "type_f",
                "name": "분노 성향",
                "description": "분노와 좌절감이 많은 성향",
                "type_specific_keywords": ["분노", "좌절", "감정 조절", "소통"]
            },
            {
                "id": "type_g",
                "name": "자존감 낮음",
                "description": "자존감이 낮고 자신감이 부족한 성향",
                "type_specific_keywords": ["자존감", "자기 긍정", "자기 수용", "자기 가치"]
            },
            {
                "id": "type_h",
                "name": "대인관계 어려움",
                "description": "대인관계에서 어려움을 겪는 성향",
                "type_specific_keywords": ["대인관계", "소통", "경계", "신뢰"]
            },
            {
                "id": "type_i",
                "name": "스트레스 과다",
                "description": "스트레스를 많이 받고 관리가 어려운 성향",
                "type_specific_keywords": ["스트레스", "압박감", "휴식", "시간 관리"]
            },
            {
                "id": "type_j",
                "name": "결정 어려움",
                "description": "결정을 내리기 어려워하는 성향",
                "type_specific_keywords": ["결정", "선택", "자신감", "책임감"]
            },
            {
                "id": "type_k",
                "name": "과도한 책임감",
                "description": "과도한 책임감을 느끼는 성향",
                "type_specific_keywords": ["책임감", "부담", "경계 설정", "자기 돌봄"]
            },
            {
                "id": "type_l",
                "name": "감정 억압",
                "description": "감정을 억압하거나 표현하지 못하는 성향",
                "type_specific_keywords": ["감정 표현", "감정 인식", "자기 수용", "소통"]
            },
            {
                "id": "type_m",
                "name": "비판적 사고",
                "description": "자기나 타인에 대해 비판적인 사고를 하는 성향",
                "type_specific_keywords": ["비판", "완화", "긍정적 관점", "수용"]
            },
            {
                "id": "type_n",
                "name": "변화 저항",
                "description": "변화에 저항하거나 두려워하는 성향",
                "type_specific_keywords": ["변화", "적응", "안정감", "성장"]
            },
            {
                "id": "type_o",
                "name": "과도한 타인 의존",
                "description": "타인의 인정과 승인에 과도하게 의존하는 성향",
                "type_specific_keywords": ["인정 욕구", "자기 확신", "자기 가치", "독립성"]
            },
            {
                "id": "type_p",
                "name": "감정 기복",
                "description": "감정 기복이 심하고 안정감이 부족한 성향",
                "type_specific_keywords": ["감정 조절", "안정감", "자기 인식", "대처 전략"]
            }
        ]
        
        # 공통 키워드 저장
        common_keywords = ["감정 인식", "자기 이해", "대인 관계", "자기 돌봄"]
        self.update_common_keywords(common_keywords)
        
        # 각 페르소나 생성 (이미 존재하면 스킵)
        created_count = 0
        for persona in default_personas:
            try:
                self.create_persona(persona)
                created_count += 1
            except ValueError:
                # 이미 존재하는 경우 스킵
                pass
        
        return {
            "created": created_count,
            "total": len(default_personas),
            "common_keywords": common_keywords
        }

