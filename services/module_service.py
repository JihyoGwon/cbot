"""Module 서비스 - 재사용 가능한 상담 도구/기법"""
from typing import List, Dict, Optional


class ModuleService:
    """Module 관리 서비스 - 재사용 가능한 상담 도구"""
    
    def __init__(self):
        """Module 서비스 초기화"""
        self.modules = self._initialize_modules()
    
    def _initialize_modules(self) -> List[Dict]:
        """초기 Module 목록 생성"""
        return [
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
    
    def get_module(self, module_id: str) -> Optional[Dict]:
        """Module 가져오기"""
        return next((m for m in self.modules if m.get('id') == module_id), None)
    
    def get_all_modules(self) -> List[Dict]:
        """모든 Module 목록 가져오기"""
        return self.modules
    
    def get_modules_by_session_type(self, session_type: str) -> List[Dict]:
        """세션 타입에 맞는 Module 목록 가져오기"""
        return [
            m for m in self.modules 
            if session_type in m.get('applicable_to', []) or 'all_sessions' in m.get('applicable_to', [])
        ]
    
    def get_module_guidelines(self, module_id: str) -> str:
        """Module의 가이드라인을 문자열로 반환"""
        module = self.get_module(module_id)
        if not module:
            return ""
        
        guidelines = module.get('guidelines', [])
        return "\n".join([f"- {g}" for g in guidelines])

