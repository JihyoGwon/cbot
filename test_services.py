"""서비스 테스트 스크립트"""
import sys
from config import Config
from services.llm_service import LLMService
from services.firestore_service import FirestoreService

def test_config():
    """설정 테스트"""
    print("=== 설정 확인 ===")
    print(f"PROJECT_ID: {Config.PROJECT_ID}")
    print(f"LOCATION: {Config.LOCATION}")
    print(f"GOOGLE_APPLICATION_CREDENTIALS: {Config.GOOGLE_APPLICATION_CREDENTIALS}")
    print(f"VERTEX_AI_MODEL: {Config.VERTEX_AI_MODEL}")
    print()

def test_firestore():
    """Firestore 서비스 테스트"""
    print("=== Firestore 서비스 테스트 ===")
    try:
        firestore_service = FirestoreService()
        print("[OK] Firestore 서비스 초기화 성공")
        
        # 테스트 대화 생성
        conversation_id = firestore_service.create_conversation("test_user", "테스트 메시지")
        print(f"[OK] 대화 생성 성공: {conversation_id}")
        
        # 대화 가져오기
        conversation = firestore_service.get_conversation(conversation_id)
        if conversation:
            print(f"[OK] 대화 조회 성공: {len(conversation.get('messages', []))}개 메시지")
        
        return True
    except Exception as e:
        print(f"[FAIL] Firestore 테스트 실패: {str(e)}")
        return False

def test_llm():
    """LLM 서비스 테스트"""
    print("=== LLM 서비스 테스트 ===")
    try:
        llm_service = LLMService()
        print("[OK] LLM 서비스 초기화 성공")
        
        # 간단한 테스트 메시지
        response = llm_service.chat("안녕하세요! 간단히 자기소개 해주세요.")
        print(f"[OK] LLM 응답 성공")
        print(f"응답: {response[:100]}...")
        
        return True
    except Exception as e:
        print(f"[FAIL] LLM 테스트 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("서비스 테스트 시작\n")
    
    test_config()
    
    # Firestore 테스트
    firestore_ok = test_firestore()
    print()
    
    # LLM 테스트
    llm_ok = test_llm()
    print()
    
    # 결과 요약
    print("=== 테스트 결과 ===")
    if firestore_ok and llm_ok:
        print("[OK] 모든 테스트 통과!")
        sys.exit(0)
    else:
        print("[FAIL] 일부 테스트 실패")
        sys.exit(1)

