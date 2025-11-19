"""API 테스트 스크립트"""
import requests
import json

BASE_URL = "http://localhost:5000"

def test_health():
    """헬스 체크 테스트"""
    print("=== 헬스 체크 ===")
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"[FAIL] 헬스 체크 실패: {str(e)}")
        return False

def test_create_conversation():
    """대화 생성 테스트"""
    print("\n=== 대화 생성 ===")
    try:
        data = {
            "user_id": "test_user_123",
            "message": "안녕하세요!"
        }
        response = requests.post(
            f"{BASE_URL}/api/conversations",
            json=data
        )
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2, ensure_ascii=False)}")
        
        if response.status_code == 201:
            return result.get('conversation_id')
        return None
    except Exception as e:
        print(f"[FAIL] 대화 생성 실패: {str(e)}")
        return None

def test_chat(conversation_id):
    """대화 테스트"""
    print(f"\n=== 대화하기 (conversation_id: {conversation_id}) ===")
    try:
        data = {
            "message": "파이썬에 대해 간단히 설명해주세요."
        }
        response = requests.post(
            f"{BASE_URL}/api/conversations/{conversation_id}/chat",
            json=data
        )
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2, ensure_ascii=False)}")
        return response.status_code == 200
    except Exception as e:
        print(f"[FAIL] 대화 실패: {str(e)}")
        return False

def test_get_conversation(conversation_id):
    """대화 조회 테스트"""
    print(f"\n=== 대화 조회 (conversation_id: {conversation_id}) ===")
    try:
        response = requests.get(f"{BASE_URL}/api/conversations/{conversation_id}")
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"메시지 개수: {len(result.get('messages', []))}")
        print(f"첫 메시지: {result.get('messages', [])[0] if result.get('messages') else 'None'}")
        return response.status_code == 200
    except Exception as e:
        print(f"[FAIL] 대화 조회 실패: {str(e)}")
        return False

def test_list_conversations():
    """대화 목록 조회 테스트"""
    print("\n=== 대화 목록 조회 ===")
    try:
        response = requests.get(
            f"{BASE_URL}/api/conversations",
            params={"user_id": "test_user_123", "limit": 5}
        )
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"대화 개수: {result.get('count', 0)}")
        return response.status_code == 200
    except Exception as e:
        print(f"[FAIL] 대화 목록 조회 실패: {str(e)}")
        return False

if __name__ == "__main__":
    print("API 테스트 시작\n")
    print("주의: Flask 앱이 실행 중이어야 합니다 (python app.py)")
    print("-" * 50)
    
    # 헬스 체크
    if not test_health():
        print("\n[FAIL] 서버가 실행 중이 아닙니다. 먼저 'python app.py'를 실행하세요.")
        exit(1)
    
    # 대화 생성
    conversation_id = test_create_conversation()
    if not conversation_id:
        print("\n[FAIL] 대화 생성 실패")
        exit(1)
    
    # 대화하기
    test_chat(conversation_id)
    
    # 대화 조회
    test_get_conversation(conversation_id)
    
    # 대화 목록 조회
    test_list_conversations()
    
    print("\n" + "=" * 50)
    print("[OK] 모든 API 테스트 완료!")

