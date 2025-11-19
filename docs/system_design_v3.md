# CBot 상담 시스템 설계 문서 (v3.0 - Part-Task-Module 구조)

## 시스템 개요

CBot은 Part-Task-Module 3단계 계층 구조를 사용하는 AI 상담 에이전트 시스템입니다. Part는 선형 진행을 보장하고, Task는 비선형 선택을 허용하며, Module은 상황에 맞게 동적으로 선택됩니다.

## 핵심 설계 철학

1. **Part는 선형 구조**: Part 1 → Part 2 → Part 3 순서로 진행
2. **Task는 비선형 선택**: Part 내에서 대화 흐름에 맞게 Task 선택
3. **Module은 전역 도구**: Part와 무관하게 언제든 사용 가능
4. **동적 적응**: 사용자 상태, Supervision 피드백에 따라 Module과 Task 업데이트
5. **명확한 완료 조건**: Task 완료는 LLM이 판단, Part 전환은 모든 Task 완료 시

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
│  - Part 관리                                                 │
│  - Task/Module 선택 조율                                    │
│  - 최종 응답 생성                                            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│         Part Manager (직렬, 빠름)                          │
│  - 현재 Part 확인                                            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│         병렬 실행 구간                                      │
│  ┌────────────────────┐  ┌────────────────────┐            │
│  │Task Completion     │  │User State          │            │
│  │Checker (직렬)      │  │Detector (병렬)     │            │
│  │- Task 완료 판단    │  │- 저항/감정 감지    │            │
│  └────────┬───────────┘  └────────┬───────────┘            │
│           │                        │                        │
│           └────────────┬───────────┘                        │
└────────────────────────┼────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│         Task Selector (직렬, 조건부)                        │
│  - Task 완료 시에만 실행                                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│         Module Selector (직렬)                              │
│  - Task + User State 결과로 Module 선택                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│         Counselor LLM (직렬)                                │
│  - 최종 응답 생성                                            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│         비동기 실행 (응답 후)                               │
│  ┌────────────────────┐  ┌────────────────────┐            │
│  │Supervisor Service  │  │Task Planner        │            │
│  │(비동기, 3msg마다)  │  │(조건부, Part 2)    │            │
│  └────────────────────┘  └────────────────────┘            │
└─────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│         SessionService + FirestoreService                   │
│  - 상태 저장                                                │
└─────────────────────────────────────────────────────────────┘
```

## Part 구조

### Part 1: 시작 (고정 Task)

**목표**: 관계 형성, 기본 정보 수집

**고정 Task 목록**:
- 환영 인사
- 이름/상담 목적 파악
- 관계 형성

**완료 조건**: 모든 Task가 `sufficient` 이상

**전환**: Part 1 완료 → Part 2 시작 (Part 2 Task 생성)

### Part 2: 탐색 (동적 Task)

**목표**: 사용자 문제 상황 깊이 탐색

**Task 생성 시점**: Part 1 완료 시점에 LLM이 생성

**Task 업데이트 조건**:
- 대화 주제 변경 감지
- 사용자 저항/감정 변화
- Supervision 피드백 (전략 변경 필요)
- 대화가 빙빙 돈다 (Circular Conversation)

**완료 조건**: 주요 Task들이 충분히 다뤄짐 (LLM 판단)

**전환**: Part 2 완료 → Part 3 시작

### Part 3: 마무리 (고정 Task)

**목표**: 상담 요약, 목표 설정, 다음 상담 안내

**고정 Task 목록**:
- 상담 요약
- 목표 설정
- 다음 상담 안내

**완료 조건**: 모든 Task 완료

**전환**: Part 3 완료 → 상담 종료

## Task 구조

### Task 상태

```
pending (대기 중)
    ↓
in_progress (진행 중) - Task Selector가 선택
    ↓
sufficient (충분히 다뤘음) - Task Completion Checker가 판단
    ↓
completed (완전 종료) - Part 전환 시
```

### Task 속성

```python
{
    "id": "task_info_1",
    "part": 1,  # Part 번호
    "priority": "high|medium|low",
    "title": "사용자의 이름과 상담 목적 파악하기",
    "description": "사용자의 이름과 이번 상담을 찾게 된 이유를 자연스럽게 물어보기",
    "target": "사용자의 이름과 기본 상담 목적 확인",
    "completion_criteria": "사용자가 이름과 상담 목적을 말했을 때 완료",
    "status": "pending|in_progress|sufficient|completed"
}
```

## Module 구조

### Module은 전역 도구

- Part와 무관하게 언제든 사용 가능
- 예: Part 1에서도 저항 대처 모듈 사용 가능
- 예: Part 3에서도 공감 모듈 사용 가능

### Module 선택 로직

**선택 시점**:
- Task Selector가 Task 선택할 때 함께 선택
- 사용자 상태/저항 감지 시 동적 업데이트
- Supervision 피드백에 따라 업데이트

**선택 기준**:
- Task 목표
- 사용자 현재 상태 (저항, 감정 등)
- Supervision 피드백
- 대화 맥락

**업데이트 조건**:
- 사용자 저항 감지
- Supervision 피드백 (예: "공감을 더 다양하게")
- 대화 맥락 변화

### Module 변경 알림

Module이 변경되었을 때 Counselor에게 알림:

```
=== Module 변경 ===
이유: 사용자 저항 감지
이전: 정보 수집 모듈
새로운: 저항 대처 모듈
→ 저항을 먼저 다루고, 그 후 정보 수집 재개
```

## 실행 흐름

### 병렬/직렬 처리 기준

**직렬 처리 (의존성 있음)**:
- 이전 단계의 결과가 필요한 경우
- 예: Task Selector는 Task Completion Checker 결과 필요
- 예: Module Selector는 Task Selector 결과 필요

**병렬 처리 (독립적)**:
- 서로 의존성이 없는 경우
- 레이턴시 최적화 가능한 경우
- 예: User State Detector와 Task Completion Checker는 독립적

**비동기 처리 (응답 후)**:
- 응답 속도에 영향 없어야 하는 경우
- 예: Supervisor 평가

### 메인 흐름 (상세)

```
사용자 메시지
    ↓
Part Manager: 현재 Part 확인 (직렬, 빠름)
    ↓
병렬 실행:
  ├─ Task Completion Checker 실행
  │   → 현재 Task 완료 여부 판단
  │   → 완료 신호 감지
  │   → Task 목표 달성 확인
  │
  └─ User State Detector 실행 (독립적)
      → 저항/감정/주제 변경 감지
    ↓
Task Completion Checker 결과 확인
    ↓
Task 완료 여부
    ├─ 완료됨
    │   ↓
    │   Task Selector 실행 (직렬)
    │   → 현재 Part 내에서 다음 Task 선택
    │   ↓
    │   Module Selector 실행 (직렬)
    │   → Task + User State Detector 결과로 Module 선택
    │   ↓
    │   Counselor: Task + Module로 응답 생성
    │
    └─ 아직 진행 중
        ↓
        Module Selector 실행 (Module 업데이트 체크, 직렬)
        → User State Detector 결과 + Supervision 피드백 확인
        → 필요 시 Module 변경
        ↓
        Counselor: 현재 Task + Module로 응답 생성
    ↓
응답 반환 + Firestore 저장
    ↓
비동기 실행 (응답 후):
  ├─ Supervisor 평가 (3개 메시지마다)
  │   → 다음 턴에 반영
  │
  ├─ Part Manager: Part 전환 여부 확인
  │   → 모든 Task가 sufficient 이상 → 다음 Part
  │   → Part 2인 경우: Task Planner가 Task 업데이트 필요 시
  │
  └─ Task Planner: Part 2 Task 업데이트 (조건부)
      → 특정 조건 충족 시에만 실행
```

### 병렬 처리 상세

**병렬 가능한 조합**:

1. **Task Completion Checker + User State Detector**
   - 독립적이므로 동시 실행 가능
   - 레이턴시 절감

2. **Task Planner (Part 2 업데이트) + 기타 작업**
   - 조건부 실행이므로 다른 작업과 병렬 가능
   - 하지만 Task Selector와는 직렬 (Task 목록 변경 영향)

**직렬 처리 필수**:

1. **Part Manager → Task Completion Checker**
   - 현재 Part 확인 후 Task 체크 필요

2. **Task Completion Checker → Task Selector**
   - 완료 여부 확인 후 Task 선택 필요

3. **Task Selector → Module Selector**
   - 선택된 Task 기반으로 Module 선택 필요

4. **Module Selector → Counselor**
   - 선택된 Module 기반으로 응답 생성 필요

### Task Completion Checker 상세

**실행 시점**: 매 메시지마다

**체크 항목**:
1. 명시적 완료 신호 감지
   - 사용자: "이제 충분히 얘기한 것 같아"
   - Counselor: "이제 ~에 대해 이야기해볼까요?"
   - Supervision: "이 Task는 충분히 다뤘다"

2. Task 목표 달성 확인
   - `completion_criteria` 충족 여부
   - LLM이 판단

3. Supervision 피드백 확인
   - "다음 단계로 진행해야 한다"는 피드백

**Output**:
```python
{
    "is_completed": True/False,  # 완료 여부
    "new_status": "sufficient" | "completed" | None,  # 상태 변경 (있는 경우)
    "completion_reason": "...",  # 완료 이유
    "task_id": "task_xxx"  # 체크한 Task ID
}
```

**동작**:
- `is_completed = True` → Task Selector 실행 트리거, Task 상태를 `new_status`로 업데이트
- `is_completed = False` → 현재 Task 유지 (상태 변경 없음)

### Task Selector 상세

**실행 시점**: Task Completion Checker가 "완료"라고 판단했을 때만

**선택 기준**:
1. 현재 Part 내 Task만 선택
2. 상태 우선순위: pending > in_progress > sufficient
3. 우선순위: high > medium > low
4. 대화 맥락과 자연스러운 연결

**결과**: 선택된 Task + Module 후보

### Module Selector 상세

**실행 시점**:
1. Task Selector가 Task 선택할 때 (초기 Module 선택)
2. 매 메시지마다 (Module 업데이트 체크)

**선택/업데이트 기준**:
1. Task 목표
2. 사용자 현재 상태 (User State Detector 결과)
3. Supervision 피드백
4. 대화 맥락

**User State Detector 연동**:
- Module Selector 실행 전에 User State Detector 호출
- 감지 결과를 바탕으로 Module 선택/변경

**결과**: 선택된 Module (변경 시 변경 이유 포함)

### Part Manager 상세

**역할**:
- 현재 Part 추적
- Part 전환 조건 확인
- Part별 Task 목록 관리

**Part 전환 조건**:
- Part 1 → Part 2: 모든 Task가 `sufficient` 이상
- Part 2 → Part 3: 주요 Task들이 충분히 다뤄짐 (LLM 판단)
- Part 3 → 종료: 모든 Task 완료

**Part 2 Task 생성**:
- Part 1 완료 시점에 LLM이 생성
- 특정 조건 충족 시 업데이트 (주제 변경, 저항 등)

## 주요 컴포넌트

### 1. Part Manager Service

**역할**: Part 관리 및 전환

**주요 기능**:
- 현재 Part 추적
- Part 전환 조건 확인
- Part별 Task 목록 관리

### 2. Task Planner Service

**역할**: Task 생성 및 업데이트

**주요 기능**:
- Part 1, 3: 고정 Task 생성
- Part 2: 동적 Task 생성 (Part 1 완료 시)
- Part 2: Task 업데이트 (특정 조건 충족 시)

**Task 업데이트 조건**:
- 대화 주제 변경 감지
- 사용자 저항/감정 변화
- Supervision 피드백
- 대화가 빙빙 돈다

### 3. Task Selector Service

**역할**: 다음 Task 선택

**실행 시점**: Task Completion Checker가 "완료"라고 판단했을 때만

**주요 기능**:
- 현재 Part 내에서 Task 선택
- 상태 및 우선순위 기반 선택
- 대화 맥락 반영

### 4. Task Completion Checker Service (신규)

**역할**: Task 완료 여부 판단

**실행 시점**: 매 메시지마다

**주요 기능**:
- 명시적 완료 신호 감지
- Task 목표 달성 확인
- Supervision 피드백 확인

### 6. Module Selector Service (신규)

**역할**: Module 선택 및 업데이트

**실행 시점**:
- Task Selector가 Task 선택할 때
- 매 메시지마다 (Module 업데이트 체크)

**주요 기능**:
- Task + 상황에 맞는 Module 선택
- 사용자 상태/저항 감지 시 Module 변경
- Supervision 피드백에 따라 Module 업데이트

### 7. Counselor Service

**역할**: 메인 상담사 LLM

**주요 기능**:
- Part/Task/Module 정보를 바탕으로 응답 생성
- Supervision 피드백 반영
- Module 변경 알림 처리

### 8. Supervisor Service

**역할**: 상담 품질 평가

**주요 기능**:
- 상담 품질 평가 (비동기)
- Module/Task 변경 제안
- 피드백 제공

## 프롬프트 설계

### Counselor 프롬프트 (최소화)

**필수**:
- 기본 시스템 프롬프트
- 현재 Part 정보
- 현재 Task 목표 (1-2문장)
- 선택된 Module 가이드라인 (요약, 3-5줄)

**조건부**:
- Supervision 피드백 (점수 < 7일 때만)
- Module 변경 알림 (변경되었을 때만)
- Part 전환 안내 (Part 전환 시)

**제거**:
- Task의 상세 설명 (제목과 목표만)
- Supervision의 "잘한 점" (개선점에 집중)
- Module 가이드라인 전체 (요약만)

## 일관성 보장

### 1. 순차적 의존성

```
Task Completion Checker → Task Selector → Module Selector → Counselor
```

각 단계가 이전 단계의 결과를 기반으로 실행

### 2. 스냅샷 기반

- 같은 `conversation_history` 스냅샷을 모든 LLM에 전달
- 같은 시점의 상태를 기준으로 판단

### 3. 비동기 작업

- Supervisor는 비동기 실행 (다음 턴에 반영)
- 현재 턴의 일관성은 동기 작업으로 보장

## 데이터 구조

### Session 구조

```python
{
    "conversation_id": "...",
    "current_part": 1,  # 1, 2, 3
    "tasks": [
        {
            "id": "task_rapport_1",
            "part": 1,
            "priority": "high",
            "title": "...",
            "target": "...",
            "completion_criteria": "...",
            "status": "pending|in_progress|sufficient|completed"
        }
    ],
    "current_task": "task_rapport_1",
    "current_module": "rapport_building",
    "previous_module": "information_gathering",  # Module 변경 시
    "module_change_reason": "사용자 저항 감지",  # Module 변경 시
    "supervision_log": [...],
    "message_count": 5
}
```

## 주요 변경사항 (v2.0 → v3.0)

1. **Part 구조 도입**: 선형 진행 보장
2. **Task-Module 분리**: Module은 전역 도구로 변경
3. **Task Completion Checker 분리**: 독립적인 완료 판단
4. **Module Selector 분리**: 동적 Module 선택/업데이트
5. **Part 2 Task 동적 생성**: Part 1 완료 시점에 생성
6. **프롬프트 최소화**: 핵심 정보만 포함
7. **일관성 보장**: 순차적 의존성 및 스냅샷 기반

## 다음 단계

1. Part Manager Service 구현
2. Task Completion Checker Service 구현
3. Module Selector Service 구현
4. Task Planner Service 수정 (Part 2 동적 생성)
5. Task Selector Service 수정 (조건부 실행)
6. Counselor Service 수정 (새 구조 반영)
7. 프롬프트 최소화 적용

