# CBot 상담 시스템 설계 문서 (v4.0 - 페르소나 기반 개인화 상담)

## 시스템 개요

CBot은 **사용자 페르소나 기반 개인화 상담**을 제공하는 AI 상담 에이전트 시스템입니다. Part-Task-Module 3단계 계층 구조를 유지하면서, 사용자의 타입, 상담 키워드, 상담 레벨을 기반으로 Part 2의 목표와 Task Plan을 동적으로 수립합니다.

## 핵심 설계 철학

1. **Part는 선형 구조**: Part 1 → Part 2 → Part 3 순서로 진행
2. **Task는 비선형 선택**: Part 내에서 대화 흐름에 맞게 Task 선택
3. **Module은 전역 도구**: Part와 무관하게 언제든 사용 가능
4. **페르소나 기반 개인화**: 사용자 타입, 키워드, 레벨에 맞춘 상담
5. **동적 Part 2 목표 수립**: Part 1 대화 분석 + 페르소나 기반 목표 설정
6. **피드백 루프**: Part Manager ↔ Task Planner 간 긴밀한 협업
7. **명확한 완료 조건**: Task 완료는 LLM이 판단, Part 전환은 LLM이 판단

## 주요 변경사항 (v3.0 → v4.0)

### 1. 사용자 페르소나 시스템 도입
- **16타입 시스템**: 모든 사용자는 16개 중 1개 타입 부여
- **상담 키워드**: 타입별 4개 특화 키워드 + 공통 4개 키워드
- **상담 레벨**: 1~5 단계 (1=초기 라포형성/문제인식, 5=말기 문제해결)

### 2. Part 2 목표 설정 개선
- **동적 목표 수립**: Part 1 대화 분석 + 페르소나 기반 목표 생성
- **키워드 기반 선택**: Part 1 대화에서 가장 관련성 높은 키워드 선택
- **레벨 기반 범위 결정**: 상담 레벨에 따라 상담 깊이 조절

### 3. 피드백 루프 구축
- **Part Manager → Task Planner**: Part 목적 달성 피드백
- **Task Selector → Task Planner**: Task 선택 불가 시 피드백
- **Part Manager**: Part 완료 판단 (LLM 기반)

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
│  - Part 완료 판단 (LLM 기반)                                │
│  - Task Planner 피드백 제공                                 │
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
│  - 선택 불가 시 피드백 제공                                 │
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
│  │Supervisor Service  │  │Task Planner       │            │
│  │(비동기, 3msg마다)  │  │(조건부, Part 2)   │            │
│  │                    │  │- 페르소나 기반    │            │
│  │                    │  │  목표 수립        │            │
│  └────────────────────┘  └────────┬──────────┘            │
│                                   │                        │
│  ┌────────────────────┐          │                        │
│  │Part Manager        │◄─────────┘                        │
│  │(비동기, Part 전환) │                                   │
│  │- Part 완료 판단    │                                   │
│  │- 피드백 제공       │                                   │
│  └────────────────────┘                                   │
└─────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│         SessionService + FirestoreService                   │
│  - 상태 저장                                                │
│  - 페르소나 정보 저장                                       │
└─────────────────────────────────────────────────────────────┘
```

## 사용자 페르소나 시스템

### 1. 16타입 시스템

**개념**: 모든 사용자는 16개 타입 중 1개에 속합니다.

**타입 정의 예시** (가상):
- Type A: 완벽주의 성향, 높은 자기 기대
- Type B: 회피 성향, 갈등 회피
- Type C: 의존 성향, 타인 의존도 높음
- ... (총 16개 타입)

**구현**:
- 타입은 세션 생성 시 또는 첫 상담 시 할당
- Firestore에 `user_persona.type` 필드로 저장
- 타입별 특성은 별도 설정 파일 또는 데이터베이스에서 관리

### 2. 상담 키워드 시스템

**타입별 특화 키워드 (4개)**:
각 타입마다 4개의 특화 상담 키워드를 가집니다.

**예시**:
- Type A: `["완벽주의", "자기 비판", "스트레스 관리", "목표 설정"]`
- Type B: `["갈등 회피", "감정 표현", "자기 주장", "경계 설정"]`
- Type C: `["의존성", "자기 결정", "자기 효능감", "독립성"]`

**타입 공통 키워드 (4개)**:
모든 타입이 공통으로 가지는 키워드:
- `["감정 인식", "자기 이해", "대인 관계", "자기 돌봄"]`

**총 키워드**: 각 사용자는 최대 8개 키워드를 가집니다 (타입 특화 4개 + 공통 4개)

**구현**:
- Firestore에 `user_persona.keywords` 배열로 저장
- `user_persona.type_specific_keywords`: 타입 특화 키워드
- `user_persona.common_keywords`: 공통 키워드

### 3. 상담 레벨 시스템

**레벨 정의 (1~5)**:

| 레벨 | 단계 | 집중 영역 | 설명 |
|------|------|----------|------|
| 1 | 초기 | 라포 형성, 문제 인식 | 상담 초기 단계, 관계 형성과 문제 인식에 집중 |
| 2 | 탐색 | 감정 탐색, 상황 파악 | 문제의 깊이 있는 탐색, 감정과 상황 이해 |
| 3 | 이해 | 패턴 인식, 원인 파악 | 문제의 패턴과 원인을 이해하는 단계 |
| 4 | 변화 | 행동 변화, 대처 전략 | 구체적인 변화와 대처 전략 수립 |
| 5 | 말기 | 문제 해결, 유지 | 문제 해결과 변화 유지에 집중 |

**레벨 결정 기준**:
- 초기 상담 시 기본값: 레벨 1
- 상담 진행에 따라 레벨 업데이트 가능
- 사용자의 상담 경험, 문제 심각도, 변화 의지 등 고려

**구현**:
- Firestore에 `user_persona.counseling_level` (1~5) 저장
- 레벨에 따라 Part 2의 목표와 Task 범위 조절

## Part 구조

### Part 1: 시작 (고정 Task)

**목표**: 관계 형성, 기본 정보 수집, **페르소나 파악**

**고정 Task 목록**:
- 환영 인사
- 이름/상담 목적 파악
- 관계 형성
- **페르소나 정보 수집** (신규)

**페르소나 정보 수집 Task**:
- 사용자 타입 파악 (16타입 중 선택)
- 상담 키워드 관련성 확인 (Part 1 대화에서 키워드 관련성 평가)
- 상담 레벨 초기 설정 (기본값: 1)

**완료 조건**: 모든 Task가 `sufficient` 이상

**전환**: Part 1 완료 → Part 2 시작 (Part 2 목표 및 Task Plan 수립)

### Part 2: 탐색 (동적 Task, 페르소나 기반)

**목표**: **페르소나 기반 개인화된 목표 설정 및 Task Plan 수립**

**목표 수립 프로세스**:

1. **Part 1 대화 분석**:
   - Part 1 대화 내용 전체 분석
   - 사용자가 언급한 문제, 감정, 상황 파악

2. **키워드 관련성 평가**:
   - 사용자의 8개 키워드 (타입 특화 4개 + 공통 4개) 중
   - Part 1 대화와 가장 관련성 높은 키워드 선택 (최대 3~4개)

3. **레벨 기반 범위 결정**:
   - 상담 레벨에 따라 상담 깊이 조절:
     - 레벨 1: 라포 형성, 문제 인식에 집중 (표면적 탐색)
     - 레벨 2: 감정 탐색, 상황 파악 (중간 깊이)
     - 레벨 3: 패턴 인식, 원인 파악 (깊은 탐색)
     - 레벨 4: 행동 변화, 대처 전략 (실행 중심)
     - 레벨 5: 문제 해결, 유지 (해결 중심)

4. **Part 2 목표 생성**:
   - 선택된 키워드 + 레벨 + Part 1 대화 내용을 바탕으로
   - LLM이 Part 2의 구체적 목표 생성
   - 예: "사용자의 완벽주의 성향과 스트레스 관리 문제를 중심으로, 감정 탐색과 대처 전략 수립에 집중"

5. **Task Plan 수립**:
   - Part 2 목표를 달성하기 위한 구체적 Task 생성
   - 레벨에 따라 Task 깊이 조절:
     - 레벨 1: 표면적 Task (예: "현재 스트레스 상황 파악")
     - 레벨 3: 깊은 Task (예: "완벽주의 패턴의 근본 원인 탐색")
     - 레벨 5: 해결 중심 Task (예: "완벽주의 완화 전략 실행")

**Task 생성 시점**: Part 1 완료 시점에 LLM이 생성

**Task 업데이트 조건**:
- 대화 주제 변경 감지
- 사용자 저항/감정 변화
- Supervision 피드백 (전략 변경 필요)
- 대화가 빙빙 돈다 (Circular Conversation)
- **Part Manager 피드백** (Part 목적 달성 불가능)

**완료 조건**: **LLM이 판단** (Part Manager가 Part 완료 여부 평가)

**전환**: Part 2 완료 (LLM 판단) → Part 3 시작

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
    "status": "pending|in_progress|sufficient|completed",
    "restrictions": "해결책 제시 금지"  # 선택사항
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
- **페르소나 정보** (신규)

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
- 예: Part Manager의 Part 완료 판단
- 예: Task Planner의 Part 2 목표 수립

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
    │   → 선택 불가 시 피드백 제공
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
  ├─ Part Manager: Part 완료 판단 (LLM 기반)
  │   → Part 1: 모든 Task가 sufficient 이상 → Part 2
  │   → Part 2: LLM이 Part 목적 달성 여부 판단 → Part 3
  │   → Part 3: 모든 Task 완료 → 종료
  │   → Part 목적 달성 불가능 시 Task Planner에 피드백
  │
  └─ Task Planner: Part 2 목표 수립/업데이트 (조건부)
      → Part 1 완료 시: 페르소나 기반 목표 및 Task Plan 수립
      → 특정 조건 충족 시: Task 업데이트
      → Part Manager 피드백 수신 시: Task 재생성/수정
```

### Part 2 목표 수립 상세 흐름

```
Part 1 완료 감지
    ↓
Part Manager: Part 1 → Part 2 전환
    ↓
Task Planner: Part 2 목표 수립 시작
    ↓
1. Part 1 대화 분석
   → 전체 대화 내용 분석
   → 사용자 문제, 감정, 상황 파악
    ↓
2. 페르소나 정보 조회
   → user_persona.type (16타입 중 1개)
   → user_persona.keywords (8개 키워드)
   → user_persona.counseling_level (1~5)
    ↓
3. 키워드 관련성 평가
   → Part 1 대화와 키워드 매칭
   → 관련성 높은 키워드 선택 (최대 3~4개)
    ↓
4. 레벨 기반 범위 결정
   → 레벨 1: 표면적 탐색
   → 레벨 3: 깊은 탐색
   → 레벨 5: 해결 중심
    ↓
5. Part 2 목표 생성 (LLM)
   → 선택된 키워드 + 레벨 + 대화 내용 기반
   → 구체적이고 측정 가능한 목표 생성
   → 예: "완벽주의 성향과 스트레스 관리 문제를 중심으로,
          감정 탐색과 대처 전략 수립"
    ↓
6. Task Plan 수립 (LLM)
   → Part 2 목표 달성을 위한 구체적 Task 생성
   → 레벨에 따라 Task 깊이 조절
   → Task별 target, completion_criteria 설정
    ↓
Part 2 시작 (생성된 Task로 진행)
```

### 피드백 루프 상세

```
┌─────────────────────────────────────────────────┐
│           피드백 루프 구조                       │
└─────────────────────────────────────────────────┘

1. Task Selector → Task Planner
   ┌─────────────────────────────────────────────┐
   │ Task Selector: "적절한 Task 없음"           │
   │ 이유: "모든 Task가 현재 상황에 부적절"      │
   │      "Part 2 목적 달성에 필요한 Task 부재"   │
   └──────────────────┬──────────────────────────┘
                      │
                      ▼
   ┌─────────────────────────────────────────────┐
   │ Task Planner: Task 재생성/수정             │
   │ - Part 2 목적 재확인                       │
   │ - 새로운 Task 생성 또는 기존 Task 수정      │
   └─────────────────────────────────────────────┘

2. Part Manager → Task Planner
   ┌─────────────────────────────────────────────┐
   │ Part Manager: "Part 2 목적 달성 불가능"     │
   │ 이유: "현재 Task들이 Part 2 목적과 맞지 않음"│
   │      "Part 2 목적 달성에 필요한 Task 부족"   │
   │      "Task 범위가 너무 넓거나 깊음"          │
   └──────────────────┬──────────────────────────┘
                      │
                      ▼
   ┌─────────────────────────────────────────────┐
   │ Task Planner: Task Plan 재수립              │
   │ - Part 2 목적 재확인                       │
   │ - Task 재생성 또는 수정                    │
   │ - 레벨과 키워드 재고려                     │
   └─────────────────────────────────────────────┘

3. Part Manager: Part 완료 판단
   ┌─────────────────────────────────────────────┐
   │ Part Manager: Part 완료 여부 평가 (LLM)     │
   │ - Part 1: 모든 Task sufficient 이상?        │
   │ - Part 2: Part 목적 달성 여부? (LLM 판단)  │
   │ - Part 3: 모든 Task 완료?                   │
   └──────────────────┬──────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        │                           │
        ▼                           ▼
   완료됨                      완료 안됨
        │                           │
        ▼                           ▼
   다음 Part로 전환          Task Planner에 피드백
```

## 주요 컴포넌트

### 1. Persona Service (신규)

**역할**: 사용자 페르소나 관리

**주요 기능**:
- 사용자 타입 할당 (16타입 중 1개)
- 상담 키워드 관리 (타입 특화 4개 + 공통 4개)
- 상담 레벨 관리 (1~5)
- 페르소나 정보 조회/업데이트

**데이터 구조**:
```python
{
    "user_id": "...",
    "persona": {
        "type": "Type_A",  # 16타입 중 1개
        "type_specific_keywords": ["완벽주의", "자기 비판", "스트레스 관리", "목표 설정"],
        "common_keywords": ["감정 인식", "자기 이해", "대인 관계", "자기 돌봄"],
        "counseling_level": 1  # 1~5
    }
}
```

### 2. Part Manager Service (강화)

**역할**: Part 관리, 전환, 완료 판단, 피드백 제공

**주요 기능**:
- 현재 Part 추적
- **Part 완료 판단 (LLM 기반)** (신규)
  - Part 1: 모든 Task가 `sufficient` 이상
  - Part 2: LLM이 Part 목적 달성 여부 판단
  - Part 3: 모든 Task 완료
- **Task Planner 피드백 제공** (신규)
  - Part 목적 달성 불가능 시 피드백
  - Task Plan 부적절 시 피드백
- Part별 Task 목록 관리

**Part 완료 판단 프로세스**:
```python
def check_part_completion(self, conversation_id: str, current_part: int, 
                         tasks: List[Dict], conversation_history: List[Dict],
                         part2_goal: Optional[str] = None) -> Dict:
    """
    Part 완료 여부 판단
    
    Args:
        conversation_id: 대화 ID
        current_part: 현재 Part (1, 2, 3)
        tasks: 현재 Part의 Task 목록
        conversation_history: 대화 기록
        part2_goal: Part 2 목표 (Part 2인 경우만)
    
    Returns:
        {
            "is_completed": True/False,
            "reason": "...",
            "feedback_to_task_planner": "..."  # 완료 불가능 시 피드백
        }
    """
```

### 3. Task Planner Service (강화)

**역할**: Task 생성 및 업데이트, **Part 2 목표 수립**

**주요 기능**:
- Part 1, 3: 고정 Task 생성
- **Part 2: 페르소나 기반 목표 및 Task Plan 수립** (신규)
  - Part 1 대화 분석
  - 키워드 관련성 평가
  - 레벨 기반 범위 결정
  - Part 2 목표 생성
  - Task Plan 수립
- Part 2: Task 업데이트 (특정 조건 충족 시)
- **Part Manager 피드백 수신 및 Task 재생성** (신규)

**Part 2 목표 수립 프로세스**:
```python
def create_part2_goal_and_plan(self, conversation_id: str, 
                                conversation_history: List[Dict],
                                user_persona: Dict) -> Dict:
    """
    Part 2 목표 및 Task Plan 수립
    
    Args:
        conversation_id: 대화 ID
        conversation_history: Part 1 대화 기록
        user_persona: 사용자 페르소나 정보
    
    Returns:
        {
            "part2_goal": "Part 2의 구체적 목표",
            "selected_keywords": ["키워드1", "키워드2", ...],
            "tasks": [
                {
                    "id": "task_part2_1",
                    "part": 2,
                    "priority": "high",
                    "title": "...",
                    "description": "...",
                    "target": "...",
                    "completion_criteria": "...",
                    "status": "pending"
                }
            ]
        }
    """
```

**Task 업데이트 조건**:
- 대화 주제 변경 감지
- 사용자 저항/감정 변화
- Supervision 피드백
- 대화가 빙빙 돈다
- **Part Manager 피드백** (신규)
- **Task Selector 피드백** (신규)

### 4. Task Selector Service (강화)

**역할**: 다음 Task 선택, **선택 불가 시 피드백 제공**

**실행 시점**: Task Completion Checker가 "완료"라고 판단했을 때만

**주요 기능**:
- 현재 Part 내에서 Task 선택
- 상태 및 우선순위 기반 선택
- 대화 맥락 반영
- **선택 불가 시 피드백 제공** (신규)
  - "적절한 Task 없음"
  - "Part 목적 달성에 필요한 Task 부재"
  - "모든 Task가 현재 상황에 부적절"

**Output**:
```python
{
    "selected_task_id": "task_xxx" | None,  # None = 선택 불가
    "execution_guide": "...",
    "selection_reason": "...",
    "feedback_to_task_planner": "..."  # 선택 불가 시 피드백
}
```

### 5. Task Completion Checker Service

**역할**: Task 완료 여부 판단

**실행 시점**: 매 메시지마다

**주요 기능**:
- 명시적 완료 신호 감지
- Task 목표 달성 확인
- Supervision 피드백 확인

### 6. Module Selector Service

**역할**: Module 선택 및 업데이트

**실행 시점**:
- Task Selector가 Task 선택할 때
- 매 메시지마다 (Module 업데이트 체크)

**주요 기능**:
- Task + 상황에 맞는 Module 선택
- 사용자 상태/저항 감지 시 Module 변경
- Supervision 피드백에 따라 Module 업데이트
- **페르소나 정보 반영** (신규)

### 7. User State Detector Service

**역할**: 사용자 상태 감지

**주요 기능**:
- 저항 감지
- 감정 변화 감지
- 주제 변경 감지
- 순환 대화 감지

### 8. Counselor Service

**역할**: 메인 상담사 LLM

**주요 기능**:
- Part/Task/Module 정보를 바탕으로 응답 생성
- Supervision 피드백 반영
- Module 변경 알림 처리
- **페르소나 정보 반영** (신규)

### 9. Supervisor Service

**역할**: 상담 품질 평가

**주요 기능**:
- 상담 품질 평가 (비동기)
- Module/Task 변경 제안
- 피드백 제공

## 데이터 구조

### Session 구조

```python
{
    "conversation_id": "...",
    "session_type": "first_session",
    "status": "active",  # active, wrapping_up, completed
    "current_part": 1,  # Part 번호 (1, 2, 3)
    "created_at": datetime,
    "updated_at": datetime,
    "tasks": [
        {
            "id": "task_rapport_1",
            "part": 1,
            "priority": "high",
            "title": "...",
            "description": "...",
            "target": "...",
            "completion_criteria": "...",
            "status": "pending|in_progress|sufficient|completed",
            "restrictions": "..."  # 선택사항
        }
    ],
    "current_task": "task_rapport_1",
    "current_module": "rapport_building",
    "previous_module": "information_gathering",
    "module_change_reason": "사용자 저항 감지",
    "user_info": {},
    "user_persona": {  # 신규
        "type": "Type_A",
        "type_specific_keywords": ["완벽주의", "자기 비판", "스트레스 관리", "목표 설정"],
        "common_keywords": ["감정 인식", "자기 이해", "대인 관계", "자기 돌봄"],
        "counseling_level": 1
    },
    "part2_goal": "완벽주의 성향과 스트레스 관리 문제를 중심으로, 감정 탐색과 대처 전략 수립",  # 신규
    "selected_keywords": ["완벽주의", "스트레스 관리"],  # 신규
    "goals": [],
    "supervision_log": [],
    "session_manager_log": [],
    "completion_log": [],
    "message_count": 0,
    "part2_task_update_count": 0
}
```

### User Persona 구조

```python
{
    "user_id": "...",
    "persona": {
        "type": "Type_A",  # 16타입 중 1개
        "type_specific_keywords": [
            "완벽주의",
            "자기 비판",
            "스트레스 관리",
            "목표 설정"
        ],
        "common_keywords": [
            "감정 인식",
            "자기 이해",
            "대인 관계",
            "자기 돌봄"
        ],
        "counseling_level": 1,  # 1~5
        "updated_at": datetime
    }
}
```

## 프롬프트 설계

### Counselor 프롬프트 (최소화)

**필수**:
- 기본 시스템 프롬프트
- 현재 Part 정보
- 현재 Task 목표 (1-2문장)
- 선택된 Module 가이드라인 (요약, 3-5줄)
- **페르소나 정보** (신규, Part 2에서 중요)

**조건부**:
- Supervision 피드백 (점수 < 7일 때만)
- Module 변경 알림 (변경되었을 때만)
- Part 전환 안내 (Part 전환 시)
- **Part 2 목표** (Part 2인 경우만, 신규)

**제거**:
- Task의 상세 설명 (제목과 목표만)
- Supervision의 "잘한 점" (개선점에 집중)
- Module 가이드라인 전체 (요약만)

### Task Planner 프롬프트 (Part 2 목표 수립)

**입력**:
- Part 1 대화 기록 전체
- 사용자 페르소나 정보 (타입, 키워드, 레벨)
- Part 2 목적 (일반적)

**프롬프트 구조**:
```
1. Part 1 대화 분석 요청
2. 키워드 관련성 평가 요청
3. 레벨 기반 범위 결정 안내
4. Part 2 목표 생성 요청
5. Task Plan 수립 요청
```

**출력**:
- Part 2 목표 (구체적, 측정 가능)
- 선택된 키워드 (최대 3~4개)
- Task 목록 (레벨에 맞는 깊이)

### Part Manager 프롬프트 (Part 완료 판단)

**입력**:
- 현재 Part 번호
- 현재 Part의 Task 목록 및 상태
- 대화 기록
- Part 2 목표 (Part 2인 경우만)

**프롬프트 구조**:
```
1. Part별 완료 조건 안내
2. 현재 상태 평가 요청
3. Part 목적 달성 여부 판단 요청
4. 피드백 생성 요청 (완료 불가능 시)
```

**출력**:
- 완료 여부 (True/False)
- 완료 이유
- Task Planner 피드백 (완료 불가능 시)

## 일관성 보장

### 1. 순차적 의존성

```
Task Completion Checker → Task Selector → Module Selector → Counselor
Part Manager → Task Planner (Part 2 목표 수립)
```

각 단계가 이전 단계의 결과를 기반으로 실행

### 2. 스냅샷 기반

- 같은 `conversation_history` 스냅샷을 모든 LLM에 전달
- 같은 시점의 상태를 기준으로 판단
- 페르소나 정보는 세션 시작 시 고정

### 3. 비동기 작업

- Supervisor는 비동기 실행 (다음 턴에 반영)
- Part Manager의 Part 완료 판단은 비동기 실행
- Task Planner의 Part 2 목표 수립은 비동기 실행
- 현재 턴의 일관성은 동기 작업으로 보장

### 4. 피드백 루프 일관성

- 피드백은 비동기로 전달되지만, 다음 요청 시 반영 보장
- Task Planner는 피드백을 받으면 즉시 Task 재생성/수정
- Part Manager는 Task Plan 변경 후 재평가

## 구현 우선순위

### Phase 1: 페르소나 시스템 구축
1. ✅ Persona Service 구현
2. ✅ 16타입 정의 및 키워드 매핑
3. ✅ 상담 레벨 시스템 구현
4. ✅ 세션에 페르소나 정보 저장

### Phase 2: Part 2 목표 수립
5. ✅ Task Planner에 Part 2 목표 수립 기능 추가
6. ✅ 키워드 관련성 평가 로직 구현
7. ✅ 레벨 기반 범위 결정 로직 구현
8. ✅ Part 1 대화 분석 기능 추가

### Phase 3: 피드백 루프 구축
9. ✅ Part Manager에 Part 완료 판단 기능 추가 (LLM 기반)
10. ✅ Task Selector에 선택 불가 피드백 기능 추가
11. ✅ Task Planner에 피드백 수신 및 재생성 기능 추가
12. ✅ Part Manager → Task Planner 피드백 루프 구현

### Phase 4: 통합 및 테스트
13. ✅ 전체 시스템 통합
14. ✅ 페르소나 기반 개인화 상담 테스트
15. ✅ 피드백 루프 동작 확인
16. ✅ Part 2 목표 수립 정확도 검증

## 다음 단계

1. Persona Service 구현
2. Task Planner Service 수정 (Part 2 목표 수립)
3. Part Manager Service 강화 (Part 완료 판단, 피드백)
4. Task Selector Service 강화 (선택 불가 피드백)
5. Counselor Service 수정 (페르소나 정보 반영)
6. 프롬프트 업데이트 (페르소나 기반)
7. 통합 테스트

## 참고사항

### 페르소나 타입 및 키워드 예시 (가상)

**Type A - 완벽주의 성향**:
- 타입 특화 키워드: `["완벽주의", "자기 비판", "스트레스 관리", "목표 설정"]`

**Type B - 회피 성향**:
- 타입 특화 키워드: `["갈등 회피", "감정 표현", "자기 주장", "경계 설정"]`

**Type C - 의존 성향**:
- 타입 특화 키워드: `["의존성", "자기 결정", "자기 효능감", "독립성"]`

**공통 키워드** (모든 타입):
- `["감정 인식", "자기 이해", "대인 관계", "자기 돌봄"]`

### 레벨별 Task 예시

**레벨 1 (초기)**:
- "현재 스트레스 상황 파악하기"
- "주요 걱정거리 확인하기"

**레벨 3 (이해)**:
- "완벽주의 패턴의 근본 원인 탐색하기"
- "자기 비판의 기원 이해하기"

**레벨 5 (말기)**:
- "완벽주의 완화 전략 실행하기"
- "자기 비판 대신 자기 긍정 습관화하기"

