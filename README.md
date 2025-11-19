# cbot

고도화된 AI 상담 에이전트 - Vertex AI 기반 멀티 LLM 시스템

## 기능

- **고도화된 상담 에이전트**: 여러 LLM이 협력하는 구조화된 상담 시스템
- **Task 기반 상담**: 첫 회기 상담에 특화된 체계적 접근
- **실시간 품질 관리**: Supervisor LLM을 통한 주기적 피드백
- **Vertex AI (Gemini)**: Google Cloud의 Vertex AI 사용
- **Firestore 저장**: 대화 기록 및 세션 상태 저장
- **RESTful API**: 완전한 API 지원

## 설치

1. 가상 환경 생성 및 활성화:
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

2. 패키지 설치:
```bash
pip install -r requirements.txt
```

3. 환경 변수 설정:
- `.env` 파일을 생성하고 필요한 값들을 설정하세요
- `GOOGLE_APPLICATION_CREDENTIALS`: Vertex AI 인증 키 파일 경로
- `PROJECT_ID`: Google Cloud 프로젝트 ID
- 기타 설정은 `config.py`를 참고하세요

## 실행

```bash
python app.py
```

서버가 `http://localhost:5000`에서 실행됩니다.

## API 엔드포인트

### 1. 헬스 체크
```
GET /health
```

### 2. 새 대화 생성
```
POST /api/conversations
Body: {
  "user_id": "user123",
  "message": "안녕하세요" (선택사항)
}
```

### 3. 대화하기
```
POST /api/conversations/<conversation_id>/chat
Body: {
  "message": "안녕하세요!"
}
```

### 4. 대화 가져오기
```
GET /api/conversations/<conversation_id>
```

### 5. 대화 목록 가져오기
```
GET /api/conversations?user_id=user123&limit=10
```

### 6. 상담 세션 정보 가져오기
```
GET /api/sessions/<conversation_id>
```

세션 정보에는 다음이 포함됩니다:
- 현재 task 목록
- 완료된 task 목록
- Supervision 로그
- 사용자 정보 및 목표

## 시스템 아키텍처

고도화된 상담 에이전트는 4개의 LLM이 협력합니다:

1. **Main Counselor LLM**: 사용자와 직접 대화하는 메인 상담사
2. **Task Planner LLM**: 사용자 상태 분석 및 task 생성/업데이트
3. **Task Selector LLM**: 현재 컨텍스트에서 다음 실행할 task 선택
4. **Supervisor LLM**: 상담 품질 모니터링 및 주기적 피드백

### 첫 회기 상담 특화

- 관계 형성 (Rapport Building)
- 정보 수집 (Information Gathering)
- 목표 설정 (Goal Setting)
- 신뢰 구축 (Trust Building)

## 프로젝트 구조

```
cbot/
├── app.py                      # Flask 메인 애플리케이션
├── config.py                   # 설정 관리
├── services/
│   ├── counselor_service.py    # 메인 상담사 서비스 (통합)
│   ├── task_planner_service.py # Task Planner LLM
│   ├── task_selector_service.py # Task Selector LLM
│   ├── supervisor_service.py    # Supervisor LLM
│   ├── session_service.py      # 상담 세션 관리
│   ├── llm_service.py          # 기본 LLM 서비스 (레거시)
│   └── firestore_service.py    # Firestore 저장 서비스
├── templates/                  # HTML 템플릿
├── static/                     # 정적 파일 (CSS, JS)
├── requirements.txt            # Python 패키지 의존성
└── README.md                   # 프로젝트 문서
```