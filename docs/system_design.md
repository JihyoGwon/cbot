# CBot 상담 시스템 설계 문서

## 시스템 개요

CBot은 다중 LLM 아키텍처를 사용하는 AI 상담 에이전트 시스템입니다. 여러 LLM이 협력하여 전문적인 상담을 제공합니다.

## 핵심 설계 철학

- **Task 기반 접근**: 선형적인 단계 대신 유연한 Task 시스템 사용
- **Module 재사용**: 재사용 가능한 상담 도구/기법을 Module로 관리
- **병렬 처리**: 성능 최적화를 위한 병렬 실행
- **비동기 평가**: Supervision은 비동기로 실행하여 응답 속도 향상

## 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                      Flask API Layer                        │
│  /api/conversations/<id>/chat                              │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  CounselorService                           │
│  (메인 오케스트레이터)                                       │
│  - 세션 관리                                                 │
│  - 병렬 작업 조율                                            │
│  - 최종 응답 생성                                            │
└──────┬──────────────┬──────────────┬──────────────┬─────────┘
       │              │              │              │
       ▼              ▼              ▼              ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│Task Planner │ │Task Selector│ │  Supervisor │ │   Module    │
│   Service   │ │   Service   │ │   Service   │ │   Service   │
│             │ │             │ │             │ │             │
│ - Task 생성 │ │ - 다음 Task │ │ - 품질 평가 │ │ - 상담 도구 │
│ - Task 업데이트│ │   선택     │ │ - 피드백   │ │   관리      │
│ (3msg마다)  │ │ (매 메시지) │ │ (3msg마다)  │ │             │
└──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
       │               │               │               │
       └───────────────┴───────────────┴───────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              SessionService + FirestoreService              │
│  - 세션 상태 관리 (tasks, completed_tasks, current_task)   │
│  - 대화 기록 저장                                            │
│  - Supervision 로그 저장                                     │
└─────────────────────────────────────────────────────────────┘
```

## 주요 컴포넌트

### 1. CounselorService (메인 오케스트레이터)

**역할**: 전체 상담 프로세스를 조율하는 핵심 서비스

**주요 기능**:
- 세션 로드/캐싱
- Task Planner와 Task Selector 병렬 실행
- 선택된 Task 기반으로 Counselor LLM 응답 생성
- Supervisor 비동기 실행

**실행 흐름**:
```
사용자 메시지
    ↓
세션 로드 (캐시 또는 Firestore)
    ↓
병렬 실행:
  ├─ Task Planner (3개 메시지마다)
  │   └─ Task 목록 업데이트
  │
  └─ Task Selector (매 메시지)
      └─ 다음 Task 선택
    ↓
선택된 Task + Module 가이드라인
    ↓
Counselor LLM 응답 생성
    ↓
Supervisor 평가 (비동기, 3개 메시지마다)
    ↓
응답 반환
```

### 2. Task Planner Service

**역할**: 상담 진행 상황에 따라 Task를 생성하고 업데이트

**실행 주기**: 3개 메시지마다

**주요 기능**:
- 초기 Task 생성 (첫 회기 상담용)
- 대화 진행 상황 분석
- Task 목록 업데이트
  - 완료된 Task 제거
  - 새로운 Task 추가
  - 우선순위 재조정

**Task 구조**:
```python
{
    "id": "task_info_2",
    "module_id": "information_gathering",
    "priority": "high",
    "title": "사용자의 현재 상황과 문제 파악하기",
    "description": "사용자가 현재 겪고 있는 문제나 상황을 이해하기",
    "target": "사용자의 현재 상황과 주요 문제점 파악",
    "status": "pending"
}
```

### 3. Task Selector Service

**역할**: 현재 대화 맥락에서 가장 적합한 Task 선택

**실행 주기**: 매 메시지마다

**선택 기준**:
1. 우선순위가 높은 task 우선
2. 현재 대화 맥락과 자연스럽게 연결되는 task
3. 사용자의 현재 감정 상태와 요구사항 반영
4. Task의 module_id를 참조하여 해당 Module의 가이드라인 활용

**출력**:
- 선택된 Task
- 실행 가이드 (Execution Guide)
- Module ID

### 4. Module Service

**역할**: 재사용 가능한 상담 도구/기법 관리

**Module 종류**:
- `rapport_building`: 관계 형성
- `information_gathering`: 정보 수집
- `goal_setting`: 목표 설정
- `trust_building`: 신뢰 구축
- `empathy_expression`: 공감 표현
- `questioning_technique`: 질문 기법

**Module 구조**:
```python
{
    "id": "information_gathering",
    "name": "정보 수집",
    "description": "사용자의 배경, 상황, 요구사항을 파악하는 기법",
    "guidelines": [
        "열린 질문 사용",
        "판단하지 않고 듣기",
        "중요한 정보를 자연스럽게 확인",
        "사용자의 페이스에 맞추기"
    ],
    "applicable_to": ["first_session", "all_sessions"]
}
```

### 5. Supervisor Service

**역할**: Counselor의 응답 품질 평가 및 피드백

**실행 주기**: 3개 메시지마다 (비동기)

**평가 기준**:
1. 공감 수준
2. 적절한 질문
3. 비판/판단 회피
4. 구체적 조언
5. 반말 사용
6. Task 준수

**출력**:
- 점수 (1-10)
- 피드백
- 개선 필요 여부

### 6. Session Service

**역할**: 상담 세션 상태 관리

**세션 데이터 구조**:
```python
{
    "conversation_id": "...",
    "session_type": "first_session",
    "status": "active",
    "tasks": [...],              # 현재 Task 목록
    "completed_tasks": [...],    # 완료된 Task 목록
    "current_task": "task_id",   # 현재 진행 중인 Task ID
    "user_info": {},
    "goals": [],
    "supervision_log": [...],
    "message_count": 5
}
```

## 데이터 흐름

### 1. 사용자 메시지 처리

```
사용자 메시지
    ↓
Firestore에 저장
    ↓
CounselorService.chat() 호출
    ↓
세션 로드 (캐시 우선)
    ↓
대화 기록 로드
    ↓
병렬 실행:
  ├─ Task Planner (조건부)
  └─ Task Selector
    ↓
Task 선택 결과
    ↓
Counselor LLM 프롬프트 구성
  - 기본 시스템 프롬프트
  - 선택된 Task 정보
  - Module 가이드라인
    ↓
Counselor 응답 생성
    ↓
Supervisor 평가 (비동기)
    ↓
응답 반환 + Firestore 저장
```

### 2. Task 생명주기

```
초기 생성 (Task Planner)
    ↓
tasks 리스트에 추가
    ↓
Task Selector가 선택
    ↓
current_task로 설정
    ↓
Counselor가 Task 수행
    ↓
Task Planner가 완료 판단
    ↓
completed_tasks로 이동
tasks에서 제거
```

## 성능 최적화

1. **병렬 처리**: Task Planner와 Task Selector를 동시 실행
2. **비동기 실행**: Supervisor와 메시지 카운트 증가는 백그라운드 실행
3. **세션 캐싱**: 메모리에 세션 캐시하여 Firestore 읽기 감소
4. **조건부 실행**: Task Planner는 3개 메시지마다만 실행
5. **토큰 제한**: 각 LLM의 max_output_tokens 설정으로 응답 속도 향상
6. **think_budget=0**: Gemini Flash 모델의 thinking 시간 제거

## 현재 문제점

1. **Task 완료 개념의 경직성**
   - 완료된 Task가 제거되어 재선택 불가
   - 실제로는 필요 시 다시 다뤄야 할 수 있음

2. **Task Selector의 선택 기준 모호**
   - 순서 기반 접근이 경직성 유발
   - 컨텍스트 기반 선택이 부족

3. **Task의 역할 모호**
   - "완료해야 할 목표"인지 "가이드라인"인지 불명확

## 개선 방향 (제안)

1. **Task를 "완료"에서 "관련성" 개념으로 전환**
   - `completed_tasks` 제거
   - Task는 계속 존재하되 `relevance` 또는 `priority`로 관리

2. **Task Selector 개선**
   - 순서가 아닌 컨텍스트 기반 선택
   - 필요 시 이전 Task도 재선택 가능

3. **Task Planner 개선**
   - Task 제거 대신 관련성/우선순위 조정

