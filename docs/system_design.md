# CBot 상담 시스템 설계 문서 (v2.0)

## 시스템 개요

CBot은 다중 LLM 아키텍처를 사용하는 AI 상담 에이전트 시스템입니다. 여러 LLM이 협력하여 전문적인 상담을 제공하며, 유연한 Task 기반 접근과 자연스러운 상담 종료를 지원합니다.

## 핵심 설계 철학

1. **Task는 가이드라인**: Task는 "완료해야 할 목표"가 아니라 "현재 상황에서 고려할 가이드라인"
2. **유연한 진행**: 선형적 단계 대신 컨텍스트 기반 동적 선택
3. **Module 재사용**: 재사용 가능한 상담 도구/기법을 Module로 관리
4. **자연스러운 종료**: 사용자 주도로 상담 종료 시점 결정
5. **병렬 처리**: 성능 최적화를 위한 병렬 실행
6. **비동기 평가**: Supervision은 비동기로 실행하여 응답 속도 향상

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
│Task Planner │ │Task Selector│ │Session Mgr  │ │  Supervisor │
│   Service   │ │   Service   │ │   Service   │ │   Service   │
│             │ │             │ │             │ │             │
│ - Task 생성 │ │ - 다음 Task │ │ - 상담 종료 │ │ - 품질 평가 │
│ - Task 업데이트│ │   선택     │ │   판단     │ │ - 피드백   │
│ - 상태 관리 │ │ (컨텍스트)  │ │ (주기적)   │ │ (비동기)   │
│ (3msg마다)  │ │ (매 메시지) │ │ (5msg마다)  │ │ (3msg마다)  │
└──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
       │               │               │               │
       └───────────────┴───────────────┴───────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              Module Service                                 │
│  - 재사용 가능한 상담 도구/기법 관리                         │
└─────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              SessionService + FirestoreService              │
│  - 세션 상태 관리 (tasks, current_task, session_status)    │
│  - 대화 기록 저장                                            │
│  - Supervision 로그 저장                                     │
└─────────────────────────────────────────────────────────────┘
```

## 주요 컴포넌트

### 1. CounselorService (메인 오케스트레이터)

**역할**: 전체 상담 프로세스를 조율하는 핵심 서비스

**주요 기능**:
- 세션 로드/캐싱
- Task Planner, Task Selector, Session Manager 병렬 실행
- 선택된 Task 기반으로 Counselor LLM 응답 생성
- Supervisor 비동기 실행
- Session Manager의 종료 제안 처리

**실행 흐름**:
```
사용자 메시지
    ↓
세션 로드 (캐시 또는 Firestore)
    ↓
병렬 실행:
  ├─ Task Planner (3개 메시지마다)
  │   └─ Task 상태 업데이트 (status 관리)
  │
  ├─ Task Selector (매 메시지)
  │   └─ 다음 Task 선택 (컨텍스트 기반)
  │
  └─ Session Manager (5개 메시지마다)
      └─ 상담 종료 여부 판단
    ↓
선택된 Task + Module 가이드라인
    ↓
Session Manager 종료 제안 확인
    ↓
Counselor LLM 프롬프트 구성
  - 기본 시스템 프롬프트
  - Supervision 피드백
  - 선택된 Task 정보
  - Module 가이드라인
  - 종료 제안 (있는 경우)
    ↓
Counselor 응답 생성
    ↓
Supervisor 평가 (비동기, 3개 메시지마다)
    ↓
응답 반환 + Firestore 저장
```

### 2. Task Planner Service

**역할**: 상담 진행 상황에 따라 Task를 생성하고 상태를 관리

**실행 주기**: 3개 메시지마다

**주요 기능**:
- 초기 Task 생성 (첫 회기 상담용)
- 대화 진행 상황 분석
- Task 상태 업데이트
  - `pending` → `in_progress` → `sufficient` → `completed`
- Task 목록 업데이트
  - 새로운 Task 추가
  - 우선순위 재조정
  - 충분히 다뤘지만 완전 종료는 아닌 Task는 `sufficient` 상태로

**Task 상태 생명주기**:
```
pending (대기 중)
    ↓
in_progress (진행 중) - Task Selector가 선택
    ↓
sufficient (충분히 다뤘음) - Task Planner가 판단
    ↓ (필요 시 재선택 가능, 우선순위 낮음)
completed (완전 종료) - Session Manager가 판단
```

**Task 구조**:
```python
{
    "id": "task_info_2",
    "module_id": "information_gathering",
    "priority": "high",  # high, medium, low
    "title": "사용자의 현재 상황과 문제 파악하기",
    "description": "사용자가 현재 겪고 있는 문제나 상황을 이해하기",
    "target": "사용자의 현재 상황과 주요 문제점 파악",
    "completion_criteria": "사용자가 문제를 설명했고, 상담사가 요약/확인했을 때",
    "restrictions": "이 단계에서는 해결책을 제시하지 말고, 오직 듣고 이해하는 것에만 집중하세요.",
    "status": "pending",  # pending, in_progress, sufficient, completed
    "created_at": "2024-01-01T00:00:00",
    "sufficient_at": null,  # sufficient 상태로 변경된 시점
    "completed_at": null   # completed 상태로 변경된 시점
}
```

### 3. Task Selector Service

**역할**: 현재 대화 맥락에서 가장 적합한 Task 선택

**실행 주기**: 매 메시지마다

**선택 기준**:
1. **상태 우선순위**: `pending` > `in_progress` > `sufficient` (completed는 제외)
2. **우선순위**: `high` > `medium` > `low`
3. **컨텍스트 적합성**: 현재 대화 맥락과 자연스럽게 연결되는 task
4. **사용자 감정/요구사항**: 사용자의 현재 감정 상태와 요구사항 반영
5. **Module 가이드라인**: Task의 module_id를 참조하여 해당 Module의 가이드라인 활용

**선택 로직**:
- `status`가 `completed`인 Task는 선택하지 않음
- `sufficient` 상태의 Task도 재선택 가능하지만 우선순위가 낮음
- 필요 시 이전에 다뤘던 Task도 재선택 가능 (유연성)

**출력**:
- 선택된 Task
- 실행 가이드 (Execution Guide)
- Module ID

### 4. Session Manager Service (신규)

**역할**: 상담 세션의 전체 진행 상황을 파악하고 종료 시점을 판단

**실행 주기**: 5개 메시지마다 (비동기)

**주요 기능**:
- 첫 회기 상담 목표 달성 여부 평가
- 상담 종료 제안 생성
- 세션 상태 관리 (`active` → `wrapping_up` → `completed`)

**평가 기준 (첫 회기)**:
1. **관계 형성 (Rapport Building)**
   - 사용자가 편안하게 대화하는가?
   - 신뢰 관계가 형성되었는가?

2. **정보 수집 (Information Gathering)**
   - 사용자의 주요 문제/상황 파악 완료?
   - 필요한 배경 정보 수집 완료?

3. **목표 설정 (Goal Setting)**
   - 상담 목표가 설정되었는가?
   - 구체적이고 달성 가능한 목표인가?

4. **신뢰 구축 (Trust Building)**
   - 상담 과정에 대한 안내 완료?
   - 기대치 설정 완료?

**출력**:
```python
{
    "session_status": "active" | "wrapping_up" | "completed",
    "first_session_goals_met": True | False,
    "completion_score": 0.0-1.0,  # 목표 달성도
    "missing_goals": ["goal_1", "goal_2"],  # 미달성 목표
    "recommendation": "continue" | "wrap_up" | "complete",
    "wrap_up_tasks": [  # 종료 제안 시 추가할 Task
        {
            "id": "task_wrapup_1",
            "title": "상담 요약 및 다음 상담 안내",
            ...
        }
    ]
}
```

**종료 제안 처리**:
- `recommendation`이 `wrap_up`이면 Counselor에게 마무리 Task 부여
- Counselor가 자연스럽게 마무리 대화 진행
- 사용자가 동의하면 종료, 추가 질문이 있으면 계속

### 5. Module Service

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

### 6. Supervisor Service

**역할**: Counselor의 응답 품질 평가 및 피드백

**실행 주기**: 3개 메시지마다 (비동기)

**평가 기준**:
1. 공감 수준
2. 적절한 질문
3. 비판/판단 회피
4. 구체적 조언
5. 반말 사용
6. Task 준수
7. 정보 수집 단계 준수
8. 응답 길이

**출력**:
- 점수 (1-10)
- 피드백
- 개선점
- 잘한 점
- 개선 필요 여부

**피드백 반영**:
- Supervision 피드백은 다음 메시지부터 Counselor 프롬프트에 포함
- 점수가 낮거나 개선 필요 시 강조 표시

### 7. Session Service

**역할**: 상담 세션 상태 관리

**세션 데이터 구조**:
```python
{
    "conversation_id": "...",
    "session_type": "first_session",
    "status": "active",  # active, wrapping_up, completed
    "created_at": datetime,
    "updated_at": datetime,
    "tasks": [...],              # 현재 Task 목록 (모든 상태 포함)
    "current_task": "task_id",   # 현재 진행 중인 Task ID
    "user_info": {},
    "goals": [],
    "supervision_log": [...],
    "session_manager_log": [...],  # Session Manager 평가 로그
    "message_count": 5
}
```

**주요 변경사항**:
- `completed_tasks` 제거 (Task는 삭제하지 않고 `status`로 관리)
- `session_status` 추가 (`active`, `wrapping_up`, `completed`)
- `session_manager_log` 추가

## 데이터 흐름

### 1. 사용자 메시지 처리 (일반)

```
사용자 메시지
    ↓
Firestore에 저장
    ↓
CounselorService.chat() 호출
    ↓
세션 로드 (캐시 우선, Supervision 로그는 최신 확인)
    ↓
대화 기록 로드
    ↓
병렬 실행:
  ├─ Task Planner (조건부: 3msg마다)
  │   └─ Task 상태 업데이트
  │       - sufficient 판단
  │       - 우선순위 재조정
  │
  ├─ Task Selector (매 메시지)
  │   └─ 컨텍스트 기반 Task 선택
  │       - status != completed인 Task만 선택
  │       - sufficient 상태도 재선택 가능 (우선순위 낮음)
  │
  └─ Session Manager (조건부: 5msg마다, 비동기)
      └─ 상담 종료 여부 판단
    ↓
Task 선택 결과
    ↓
Session Manager 종료 제안 확인
    ↓
Counselor LLM 프롬프트 구성
  - 기본 시스템 프롬프트
  - Supervision 피드백 (이전 메시지의 평가)
  - 선택된 Task 정보
  - Module 가이드라인
  - 종료 제안 (있는 경우)
    ↓
Counselor 응답 생성
    ↓
Supervisor 평가 (비동기, 3msg마다)
    ↓
응답 반환 + Firestore 저장
```

### 2. Task 생명주기

```
초기 생성 (Task Planner)
    ↓
tasks 리스트에 추가 (status: pending)
    ↓
Task Selector가 선택
    ↓
current_task로 설정 (status: in_progress)
    ↓
Counselor가 Task 수행
    ↓
Task Planner가 충분히 다뤘는지 판단 (3msg마다)
    ↓
sufficient 상태로 변경 (재선택 가능, 우선순위 낮음)
    ↓
Session Manager가 완전 종료 판단 (5msg마다)
    ↓
completed 상태로 변경 (재선택 불가)
```

### 3. 상담 종료 흐름

```
Session Manager 평가 (5msg마다)
    ↓
첫 회기 목표 달성 여부 확인
    ↓
목표 달성 시:
    ↓
recommendation: "wrap_up"
    ↓
wrap_up_tasks 생성
    - 상담 요약 Task
    - 다음 상담 안내 Task
    - 추가 질문 확인 Task
    ↓
Task Planner에 wrap_up_tasks 추가 (우선순위: high)
    ↓
Task Selector가 wrap_up_tasks 선택
    ↓
Counselor가 마무리 대화 진행
    ↓
사용자 응답:
    ├─ 동의/만족 → recommendation: "complete"
    │   └─ session_status: "completed"
    │
    └─ 추가 질문 → recommendation: "continue"
        └─ session_status: "active" (계속 진행)
```

## 성능 최적화

1. **병렬 처리**: Task Planner, Task Selector, Session Manager를 동시 실행
2. **비동기 실행**: Supervisor와 Session Manager는 백그라운드 실행
3. **세션 캐싱**: 메모리에 세션 캐시하여 Firestore 읽기 감소
4. **조건부 실행**: 
   - Task Planner: 3개 메시지마다만 실행
   - Session Manager: 5개 메시지마다만 실행
   - Supervisor: 3개 메시지마다만 실행
5. **토큰 제한**: 각 LLM의 max_output_tokens 설정으로 응답 속도 향상
6. **think_budget=0**: Gemini Flash 모델의 thinking 시간 제거

## 주요 개선사항 (v2.0)

### 1. Task 상태 관리 개선

**이전**:
- Task 완료 시 `completed_tasks`로 이동하고 `tasks`에서 제거
- 재선택 불가능

**개선**:
- Task는 삭제하지 않고 `status`로 관리
- `pending` → `in_progress` → `sufficient` → `completed`
- `sufficient` 상태는 재선택 가능 (우선순위 낮음)
- `completed` 상태만 재선택 불가

### 2. Session Manager 추가

**기능**:
- 상담 세션의 전체 진행 상황 파악
- 첫 회기 목표 달성 여부 평가
- 자연스러운 종료 제안

**장점**:
- 사용자 주도로 종료 시점 결정
- 선형적 진행 강제 없음
- 자연스러운 마무리 흐름

### 3. 유연한 Task 선택

**개선**:
- 컨텍스트 기반 선택 (순서 기반 아님)
- 필요 시 이전 Task도 재선택 가능
- `sufficient` 상태의 Task도 재선택 가능

### 4. Supervision 피드백 개선

**개선**:
- Supervision 피드백이 Counselor 프롬프트에 포함
- 메시지 인덱스 기반으로 올바른 피드백 매칭
- 개선점과 잘한 점 구분 표시

## 구현 우선순위

### Phase 1: Task 상태 관리 개선
1. Task 구조에 `status` 필드 추가
2. Task Planner에서 상태 업데이트 로직 구현
3. Task Selector에서 상태 기반 선택 로직 구현
4. `completed_tasks` 제거 및 마이그레이션

### Phase 2: Session Manager 구현
1. `SessionManagerService` 생성
2. 첫 회기 목표 달성 평가 로직 구현
3. 종료 제안 생성 로직 구현
4. CounselorService에 통합

### Phase 3: 종료 흐름 구현
1. `wrap_up_tasks` 생성 로직 구현
2. Counselor 프롬프트에 종료 제안 포함
3. 사용자 응답에 따른 세션 상태 업데이트
4. 프론트엔드에 세션 상태 표시

## 향후 개선 방향

1. **다양한 세션 타입 지원**: 두 번째 회기, 후속 회기 등
2. **Task 템플릿 시스템**: 세션 타입별 Task 템플릿 관리
3. **사용자 피드백 수집**: 상담 만족도 조사
4. **대화 요약 기능**: 세션 종료 시 대화 요약 생성
5. **다음 상담 계획**: 다음 회기 상담 계획 제안
