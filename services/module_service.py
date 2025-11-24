"""Module 서비스 - 재사용 가능한 상담 도구/기법"""
from typing import List, Dict, Optional
from datetime import datetime
from services.firestore_service import FirestoreService


class ModuleService:
    """Module 관리 서비스 - 재사용 가능한 상담 도구"""
    
    def __init__(self):
        """Module 서비스 초기화"""
        self.firestore = FirestoreService()
        self.collection_name = "modules"
        # 초기 모듈이 없으면 기본 모듈 생성
        self._initialize_default_modules()
    
    def _initialize_default_modules(self) -> None:
        """기본 Module이 없으면 초기화"""
        # Firestore에 기본 모듈이 있는지 확인
        modules_ref = self.firestore.db.collection(self.collection_name)
        existing_modules = list(modules_ref.stream())
        
        if len(existing_modules) == 0:
            # 기본 모듈 생성
            default_modules = [
            {
                "id": "rapport_building",
                "name": "관계 형성",
                "description": "사용자와 신뢰 관계를 구축하는 기법",
                "guidelines": [
                    "따뜻하고 친근한 톤 사용",
                    "사용자의 감정에 공감하기",
                    "편안한 분위기 조성",
                    "사용자의 말을 경청하고 이해한다는 것을 보여주기"
                ],
                "applicable_to": ["first_session", "all_sessions"]
            },
            {
                "id": "information_gathering",
                "name": "정보 수집",
                "description": "사용자의 배경, 상황, 요구사항을 파악하는 기법",
                "guidelines": [
                    "열린 질문 사용 (예: '어떻게 느끼세요?', '무엇이 도움이 될까요?')",
                    "판단하지 않고 듣기",
                    "중요한 정보를 자연스럽게 확인",
                    "사용자의 페이스에 맞추기"
                ],
                "applicable_to": ["first_session", "all_sessions"]
            },
            {
                "id": "goal_setting",
                "name": "목표 설정",
                "description": "상담 목표와 기대 결과를 설정하는 기법",
                "guidelines": [
                    "사용자와 함께 목표 설정",
                    "구체적이고 달성 가능한 목표",
                    "단기/장기 목표 구분",
                    "목표 달성을 위한 단계 제시"
                ],
                "applicable_to": ["first_session", "all_sessions"]
            },
            {
                "id": "trust_building",
                "name": "신뢰 구축",
                "description": "상담 과정에 대한 안내와 기대치를 설정하는 기법",
                "guidelines": [
                    "상담의 진행 방식 설명",
                    "기대할 수 있는 것과 없는 것 명확히 하기",
                    "비밀 보장과 안전한 공간 제공",
                    "사용자의 선택권 존중"
                ],
                "applicable_to": ["first_session"]
            },
            {
                "id": "empathy_expression",
                "name": "공감 표현",
                "description": "사용자의 감정을 이해하고 공감을 표현하는 기법",
                "guidelines": [
                    "사용자의 감정을 반영하기",
                    "판단하지 않고 이해하기",
                    "감정의 정당성 인정",
                    "지지와 격려 제공"
                ],
                "applicable_to": ["all_sessions"]
            },
            {
                "id": "questioning_technique",
                "name": "질문 기법",
                "description": "효과적인 질문을 통해 깊이 있는 대화를 이끌어내는 기법",
                "guidelines": [
                    "열린 질문 사용",
                    "닫힌 질문은 필요한 경우에만",
                    "사용자의 답변에 따라 후속 질문",
                    "질문이 압박이 되지 않도록 주의"
                ],
                "applicable_to": ["all_sessions"]
            }
            ]
            
            # Firestore에 저장
            for module in default_modules:
                module_doc = {
                    **module,
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                }
                module_ref = self.firestore.db.collection(self.collection_name).document(module['id'])
                module_ref.set(module_doc)
    
    def get_module(self, module_id: str) -> Optional[Dict]:
        """Module 가져오기"""
        module_ref = self.firestore.db.collection(self.collection_name).document(module_id)
        module_doc = module_ref.get()
        
        if module_doc.exists:
            data = module_doc.to_dict()
            # datetime 객체 제거 (JSON 직렬화를 위해)
            if 'created_at' in data and isinstance(data['created_at'], datetime):
                data['created_at'] = data['created_at'].isoformat()
            if 'updated_at' in data and isinstance(data['updated_at'], datetime):
                data['updated_at'] = data['updated_at'].isoformat()
            return data
        return None
    
    def get_all_modules(self) -> List[Dict]:
        """모든 Module 목록 가져오기"""
        modules_ref = self.firestore.db.collection(self.collection_name)
        modules_docs = modules_ref.stream()
        
        modules = []
        for doc in modules_docs:
            data = doc.to_dict()
            # datetime 객체 제거 (JSON 직렬화를 위해)
            if 'created_at' in data and isinstance(data['created_at'], datetime):
                data['created_at'] = data['created_at'].isoformat()
            if 'updated_at' in data and isinstance(data['updated_at'], datetime):
                data['updated_at'] = data['updated_at'].isoformat()
            modules.append(data)
        
        return modules
    
    def get_modules_by_session_type(self, session_type: str) -> List[Dict]:
        """세션 타입에 맞는 Module 목록 가져오기"""
        all_modules = self.get_all_modules()
        return [
            m for m in all_modules 
            if session_type in m.get('applicable_to', []) or 'all_sessions' in m.get('applicable_to', [])
        ]
    
    def get_module_guidelines(self, module_id: str) -> str:
        """Module의 가이드라인을 문자열로 반환"""
        module = self.get_module(module_id)
        if not module:
            return ""
        
        guidelines = module.get('guidelines', [])
        return "\n".join([f"- {g}" for g in guidelines])
    
    def create_module(self, module_data: Dict) -> Dict:
        """새 Module 생성"""
        module_id = module_data.get('id')
        if not module_id:
            raise ValueError('Module ID가 필요합니다.')
        
        # 중복 확인
        if self.get_module(module_id):
            raise ValueError(f'Module ID "{module_id}"가 이미 존재합니다.')
        
        # Module 데이터 준비
        module_doc = {
            'id': module_id,
            'name': module_data.get('name', ''),
            'description': module_data.get('description', ''),
            'guidelines': module_data.get('guidelines', []),
            'applicable_to': module_data.get('applicable_to', ['all_sessions']),
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        }
        
        # Firestore에 저장
        module_ref = self.firestore.db.collection(self.collection_name).document(module_id)
        module_ref.set(module_doc)
        
        # datetime을 문자열로 변환하여 반환
        module_doc['created_at'] = module_doc['created_at'].isoformat()
        module_doc['updated_at'] = module_doc['updated_at'].isoformat()
        
        return module_doc
    
    def update_module(self, module_id: str, module_data: Dict) -> Dict:
        """Module 수정"""
        module_ref = self.firestore.db.collection(self.collection_name).document(module_id)
        module_doc = module_ref.get()
        
        if not module_doc.exists:
            raise ValueError(f'Module ID "{module_id}"를 찾을 수 없습니다.')
        
        # 업데이트할 데이터 준비
        update_data = {
            'updated_at': datetime.now()
        }
        
        if 'name' in module_data:
            update_data['name'] = module_data['name']
        if 'description' in module_data:
            update_data['description'] = module_data['description']
        if 'guidelines' in module_data:
            update_data['guidelines'] = module_data['guidelines']
        if 'applicable_to' in module_data:
            update_data['applicable_to'] = module_data['applicable_to']
        
        # Firestore 업데이트
        module_ref.update(update_data)
        
        # 업데이트된 데이터 가져오기
        updated_module = self.get_module(module_id)
        return updated_module
    
    def delete_module(self, module_id: str) -> None:
        """Module 삭제"""
        module_ref = self.firestore.db.collection(self.collection_name).document(module_id)
        module_doc = module_ref.get()
        
        if not module_doc.exists:
            raise ValueError(f'Module ID "{module_id}"를 찾을 수 없습니다.')
        
        # Firestore에서 삭제
        module_ref.delete()

