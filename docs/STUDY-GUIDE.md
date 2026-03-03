# English Inspector 프로젝트 학습 가이드

> **작성일**: 2026-02-28
> **대상**: 프로젝트 전체 문서를 공부하고자 하는 개발자
> **범위**: PDF 설계서, AGENTS.md, Phase 1/2 문서, 알고리즘 리뷰, LLM 테스트 요구사항

---

## 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [설계 철학과 목표 (PDF 설계서)](#2-설계-철학과-목표)
3. [기술 스택 정리](#3-기술-스택-정리)
4. [시스템 아키텍처](#4-시스템-아키텍처)
5. [DSPy 파이프라인 핵심 개념](#5-dspy-파이프라인-핵심-개념)
6. [품질 필터 시스템](#6-품질-필터-시스템)
7. [Phase 1에서 한 일](#7-phase-1에서-한-일)
8. [Phase 2에서 한 일](#8-phase-2에서-한-일)
9. [알고리즘 리뷰 — 현재 vs 권장](#9-알고리즘-리뷰--현재-vs-권장)
10. [LLM 통합 테스트 전략](#10-llm-통합-테스트-전략)
11. [향후 로드맵](#11-향후-로드맵)
12. [핵심 용어 사전](#12-핵심-용어-사전)

---

## 1. 프로젝트 개요

**English Inspector**는 Phonics부터 한국 고등학교 내신까지 다양한 수준의 **영어 시험지를 자동으로 생성하고 검수하는 시스템**이다.

### 핵심 특징
- **객관식 90% + 주관식 10%** 비율의 시험지 생성
- **DSPy 3.x 기반 멀티모델 파이프라인**으로 문제 생성 → 필터링 → 검증 → 채점
- **사람 개입 최소화**: AI가 생성하고 AI가 검수, 문제 있는 문항만 사람이 확인
- **대상 사용자**: 출제자(교사), 학부모·학생, 검수자

### 프로젝트 구조 (모노레포)

```
english-inspector/
├── backend/          # FastAPI + DSPy 파이프라인
│   ├── app/
│   │   ├── api/      # FastAPI 라우터 (auth, exams, questions)
│   │   ├── core/     # 설정, 상수, 로깅
│   │   ├── models/   # SQLAlchemy ORM 모델
│   │   ├── schemas/  # Pydantic 요청/응답 스키마
│   │   ├── services/ # 핵심 비즈니스 로직 (DSPy 모듈, 품질 필터)
│   │   └── main.py   # FastAPI 앱 진입점
│   ├── tests/        # pytest 테스트
│   ├── pyproject.toml
│   └── uv.lock
├── frontend/         # Next.js 16 + TypeScript
│   ├── src/
│   │   ├── app/      # App Router 페이지
│   │   └── components/
│   ├── package.json
│   └── tsconfig.json
├── docs/             # 프로젝트 문서
├── AGENTS.md         # 에이전트 협업 규칙
└── 영어 시험지 자동 생성 시스템.pdf  # 원본 설계서
```

---

## 2. 설계 철학과 목표

> 출처: `영어 시험지 자동 생성 시스템.pdf`

PDF 설계서는 이 프로젝트의 **원본 청사진**이다. 핵심 설계 원칙:

### 2.1 4단계 파이프라인

```
[생성] → [필터링] → [평가] → [최적화]
 Generation   Filtering   Evaluation   Optimization
```

| 단계 | 역할 | 핵심 기술 |
|------|------|----------|
| **생성** | GPT-5.2로 N개 후보 문항 병렬 생성 | DSPy Predict, Best-of-N, reasoning.effort |
| **필터링** | 불확실한 문항 걸러내기 | Semantic Energy, Llama 4 Scout (1차 필터) |
| **평가** | 정답 검증 + 품질 채점 | Answer Matching, PRM (Process Reward Model) |
| **최적화** | 피드백 반영하여 프롬프트 자동 개선 | MIPROv2, GEPA, HITL 피드백 루프 |

### 2.2 모델 역할 분담

| 역할 | 모델 | 왜 이 모델인가? |
|------|------|---------------|
| **메인 생성** | GPT-5.2 | reasoning.effort로 추론 강도 조절, 400K 컨텍스트 |
| **장문/멀티모달** | Gemini 3.1 Pro | 1M 컨텍스트, 멀티모달 이해 |
| **평가/채점** | Claude Sonnet/Opus 4.6 | extended thinking, 분석 정확도 |
| **비용 효율/1차 필터** | Llama 4 Scout | 10M 컨텍스트, 오픈소스, 단일 GPU 추론 |

### 2.3 설계서 vs 실제 구현의 차이

PDF 설계서는 **이상적인 전체 아키텍처**를 그린 것이고, 현재 구현은 **핵심 기능 우선**으로 축소되어 있다:

| 설계서 (이상) | 현재 구현 (현실) |
|-------------|---------------|
| PostgreSQL 16 + Qdrant + Redis | SQLite (aiosqlite) |
| LangGraph + CrewAI 멀티 에이전트 | DSPy 단일 파이프라인 |
| Semantic Energy 불확실성 필터 | Jaccard 유사도 + 규칙 기반 필터 |
| PRM (Process Reward Model) | 단일 모델 ScoreQuestion |
| Celery + Redis 비동기 태스크 | 동기 Best-of-N 루프 |
| Prometheus + Grafana 모니터링 | logging 모듈 |
| AWS ECS / GCP Cloud Run 배포 | 로컬 개발 환경 |

이 차이를 이해하는 것이 중요하다. Phase별로 설계서에 가까워지는 것이 목표.

---

## 3. 기술 스택 정리

> 출처: `AGENTS.md`

### 백엔드

| 기술 | 버전 | 용도 |
|------|------|------|
| Python | 3.12 | 런타임 (3.12+ 문법 적극 사용: `type`문, `match`문) |
| FastAPI | >=0.115 | 웹 프레임워크 (비동기 핸들러 기본) |
| SQLAlchemy | >=2.0 | ORM (async 모드 + aiosqlite) |
| DSPy | >=3.1 | AI 파이프라인 (LLM 오케스트레이션) |
| Pydantic v2 | - | 데이터 검증 + API 스키마 |
| uv | - | 패키지 매니저 (**pip/poetry 사용 금지**) |
| Ruff | - | 린터 (line-length=100, target=py312) |

### 프론트엔드

| 기술 | 버전 | 용도 |
|------|------|------|
| Next.js | 16 | App Router 기반 프레임워크 |
| React | 19 | UI 라이브러리 |
| TypeScript | 5.x | strict: true, any 사용 금지 |
| Tailwind CSS 4 | latest | 스타일링 |
| shadcn/ui | latest | Radix UI 기반 컴포넌트 |
| bun | - | 패키지 매니저 (**npm/yarn 사용 금지**) |
| Biome | 2.4.4 | 린터 + 포매터 |

### 핵심 컨벤션 (반드시 기억할 것)

1. **Python 패키지**: `uv add <package>` (pip 금지)
2. **Frontend 패키지**: `bun add <package>` (npm 금지)
3. **TypeScript**: `any` 대신 `unknown` + 타입 가드
4. **FastAPI**: 모든 핸들러 `async def`, Pydantic v2 스키마 필수
5. **테스트**: `cd backend && uv run pytest`
6. **빌드**: `cd frontend && bun run build`

---

## 4. 시스템 아키텍처

### 4.1 현재 구현된 아키텍처

```
[사용자 브라우저]
       │
       ▼
[Next.js 16 프론트엔드] ── localhost:3000
       │ (REST API 호출)
       ▼
[FastAPI 백엔드] ── localhost:8000
       │
       ├─ /api/auth/    → 인증 (JWT + bcrypt)
       ├─ /api/exams/   → 시험지 CRUD
       └─ /api/questions/ → 문항 생성
              │
              ▼
       [DSPy 파이프라인]
              │
              ├─ GPT-5.2 (생성)
              ├─ Claude Sonnet 4.6 (검증+채점)
              └─ Quality Filter (규칙 기반)
              │
              ▼
       [SQLite DB] ── 시험지, 문항, 사용자 저장
```

### 4.2 데이터 흐름 (문항 생성 과정)

```
1. 교사가 프론트엔드에서 조건 설정
   (등급, 유형, 난이도, 주제, 수량)
        │
        ▼
2. FastAPI가 요청 수신 → DSPy 파이프라인 호출
        │
        ▼
3. Best-of-N 생성 (N=3)
   GPT-5.2에 3번 요청 → 3개 후보 문항
        │
        ▼
4. 각 후보에 대해:
   4a. Claude Sonnet 4.6으로 답 검증 (VerifyAnswer)
   4b. Claude Sonnet 4.6으로 품질 채점 (ScoreQuestion)
        │
        ▼
5. 가장 높은 점수의 문항 선택
        │
        ▼
6. Quality Filter 통과 여부 확인
   - 중복 검사 (Jaccard)
   - 형식 검증 (객관식 4지선다 등)
   - 난이도 캘리브레이션
        │
        ▼
7. DB 저장 → 프론트엔드에 결과 반환
```

---

## 5. DSPy 파이프라인 핵심 개념

> 출처: `docs/ALGORITHM-REVIEW.md`, PDF 설계서

### 5.1 DSPy란?

DSPy는 Stanford에서 개발한 **선언적 LLM 프로그래밍 프레임워크**이다. 핵심 철학:

> **"프롬프트를 문자열로 작성하지 말고, 코드로 프로그래밍하라"**

```python
# 기존 방식 (프롬프트 엔지니어링)
prompt = "You are an English teacher. Generate a multiple choice question about..."

# DSPy 방식 (선언적 프로그래밍)
class GenerateQuestion(dspy.Signature):
    """Generate ONE high-quality English exam question."""
    grade_level: str = dspy.InputField()
    question_type: str = dspy.InputField()
    result: ExamQuestion = dspy.OutputField()  # Pydantic 모델
```

### 5.2 핵심 구성 요소

| 개념 | 설명 | 프로젝트에서의 역할 |
|------|------|-----------------|
| **Signature** | 입력/출력 형식 선언 | GenerateQuestion, VerifyAnswer, ScoreQuestion |
| **Module** | 추론 전략을 감싼 실행 단위 | ChainOfThought, Predict |
| **ChainOfThought** | 단계별 추론을 유도하는 모듈 | 문항 생성, 답 검증에 사용 |
| **Optimizer** | 프롬프트를 자동으로 최적화 | MIPROv2 (현재), GEPA (권장) |
| **Adapter** | LLM 출력 형식을 보장 | JSONAdapter (JSON 출력 보장) |
| **dspy.context** | 특정 호출에만 다른 모델 사용 | 생성=GPT, 검증=Claude 분리 |
| **LiteLLM** | DSPy에 내장된 멀티모델 라우터 | 별도 import 없이 다양한 LLM 호출 |

### 5.3 현재 파이프라인 코드 구조

```python
# backend/app/services/dspy_modules.py 핵심 구조

class GenerateQuestion(dspy.Signature):
    # 입력: 등급, 유형, 주제, 난이도 등
    # 출력: question_json (문자열) → ⚠️ 문자열이라 파싱 필요

class VerifyAnswer(dspy.Signature):
    # 입력: 문항 텍스트, 제출된 답
    # 출력: is_correct, correct_answer

class ScoreQuestion(dspy.Signature):
    # 입력: 문항 정보
    # 출력: clarity, accuracy, difficulty_match, distractor_quality, overall (1-5)

class ExamPipeline(dspy.Module):
    def forward(self, **kwargs):
        # 1. Best-of-N: N번 생성 → 후보 리스트
        # 2. 각 후보 검증 (VerifyAnswer)
        # 3. 각 후보 채점 (ScoreQuestion)
        # 4. 최고 점수 문항 선택
```

### 5.4 Optimizer 비교

| | MIPROv2 (현재) | GEPA (권장) | SIMBA |
|---|---|---|---|
| **원리** | Bayesian 탐색 + 부트스트랩 | LLM 반성적 프롬프트 진화 | 확률적 미니배치 |
| **필요 데이터** | 40+ 예제 | 3-10 예제 | 50+ 예제 |
| **장점** | 범용, 안정적 | 소규모에서 강력, 텍스트 피드백 활용 | 대규모에서 안정 |
| **비용** | 높음 | 낮음 | 중간 |
| **적합 시기** | 데이터 50개 이상 | 초기 (데이터 부족할 때) | 대규모 운영 |

---

## 6. 품질 필터 시스템

> 출처: `docs/ALGORITHM-REVIEW.md`, Phase 1/2 문서

### 6.1 3계층 필터 구조

```
생성된 문항
    │
    ▼
[DuplicateDetector] ── 기존 문항과 중복인가?
    │ 통과
    ▼
[FormatValidator] ── 형식이 올바른가? (4지선다, 빈칸 등)
    │ 통과
    ▼
[DifficultyCalibrator] ── 난이도가 적절한가?
    │ 통과
    ▼
  ✅ 최종 통과
```

### 6.2 각 필터 상세

**DuplicateDetector** (중복 감지)
- 현재: Jaccard 유사도 (단어 토큰 기반)
- 한계: "What is the capital of France?" vs "Which city serves as France's capital?" → 다른 문항으로 인식
- 개선 방향: sentence-transformers 기반 의미론적 유사도

**FormatValidator** (형식 검증)
- 객관식: 4개 보기 + 정답이 보기 중 하나
- 빈칸 채우기: `___` 포함 + 정답 존재
- 독해: 지문(passage) 존재 + 문항 구조

**DifficultyCalibrator** (난이도 검증)
- 현재: 단어 수 + 평균 단어 길이 기반 휴리스틱
- Phase 2 추가: Flesch-Kincaid 가독성 지수
- 개선 방향: CEFR 레벨 분류 + GSL/AWL 어휘 프로파일

### 6.3 Flesch-Kincaid 가독성 지수 (Phase 2에서 추가)

```
FK Grade Level = 0.39 × (총 단어수/총 문장수) + 11.8 × (총 음절수/총 단어수) − 15.59
```

| 난이도 | FK 최소 | FK 최대 | 의미 |
|--------|---------|---------|------|
| 1 | -5.0 | 8.0 | 매우 쉬운 텍스트 |
| 2 | -2.0 | 10.0 | 초등 수준 |
| 3 | 0.0 | 14.0 | 중학교 수준 |
| 4 | 2.0 | 16.0 | 고등 수준 |
| 5 | 4.0 | 20.0 | 대학 수준까지 |

---

## 7. Phase 1에서 한 일

> 출처: `docs/PHASE-1-SETUP.md`

### 요약: 프로젝트 기반 구축

| 작업 | 상세 |
|------|------|
| **모노레포 통합** | frontend/.git 제거, 단일 저장소 |
| **Bun 마이그레이션** | npm → bun 전환 |
| **AGENTS.md 작성** | 에이전트 협업 규칙 문서화 |
| **누락 의존성 추가** | python-jose, bcrypt, email-validator, greenlet |
| **Auth API 수정** | 로그인 응답에 user 정보 포함 `{token, user}` |
| **Lint 설정** | Python: ruff, TypeScript: biome, pre-commit hooks |
| **46개 테스트 작성** | Auth 9개, ExamSet CRUD 12개, Quality Filter 26개 |
| **프론트엔드 버그 수정** | QuestionCard showAnswer 상태 동기화 |

### 아키텍처 결정

| 결정 | 이유 |
|------|------|
| 모노레포 | 프론트/백 변경을 원자적으로 추적, 단일 CI 파이프라인 |
| Bun | npm 대비 3-5배 빠른 설치 속도 |
| Auth 통합 응답 | 로그인 시 단일 요청으로 토큰 + 사용자 정보 (round trip 감소) |
| Mock LLM 우선 테스트 | API 키 없이도 파이프라인 구조 검증 가능, 결정론적 |

---

## 8. Phase 2에서 한 일

> 출처: `docs/PHASE-2-IMPROVEMENTS.md`

### 요약: 알고리즘 개선 + 테스트 인프라

| 영역 | 변경 내용 |
|------|----------|
| **FastAPI 2026 컨벤션** | 구조화된 로깅, 글로벌 에러 핸들러, CORS 설정 분리 |
| **DSPy 스코어링** | 1-10 → 1-5 스케일 변경, GEPA 호환 메트릭, verdict 필드 |
| **품질 필터** | Flesch-Kincaid 가독성 지수 추가 |
| **통합 테스트 인프라** | pytest 마커, API 키 스킵, smoke 테스트 5개, golden 데이터셋 |
| **로깅** | 모든 `except: pass` → `logger.warning()` 으로 교체 |

### 스코어링 변경 상세

**왜 1-10에서 1-5로 변경했는가?**
- G-Eval 연구 (NeurIPS 2023)에 따르면 1-5 스케일이 LLM 평가에서 더 일관된 결과 생성
- 1-10 스케일은 LLM이 5-8에 편중되는 경향 (의미 있는 차별화 어려움)
- 각 점수에 명시적 기준(anchor) 제공: 1=Poor, 2=Below Avg, 3=Acceptable, 4=Good, 5=Excellent
- 합격 기준: 모든 항목 ≥3 AND 합계 ≥18

### 검증 결과

| 검증 항목 | 결과 |
|----------|------|
| ruff check | All passed |
| pytest | 46 passed, 5 skipped (integration) |
| biome check | 25 files, no issues |
| next build | Compiled successfully |

---

## 9. 알고리즘 리뷰 — 현재 vs 권장

> 출처: `docs/ALGORITHM-REVIEW.md`

이 문서는 현재 코드의 **개선 가능 영역**을 분석한 핵심 기술 문서이다.

### 9.1 우선순위별 개선 사항

#### 높음 (즉시 적용 가능)

| 현재 | 문제점 | 권장 |
|------|--------|------|
| 수동 Best-of-N for 루프 | 실패 피드백 미전달, 병렬화 불가 | `dspy.Refine` (피드백 루프) |
| 문자열 JSON 출력 + json.loads | 파싱 실패 가능, 필드 누락 런타임 발견 | Pydantic 모델 + `dspy.JSONAdapter` |
| `except Exception: pass` | 모든 에러 무시, 디버깅 불가 | 계층화된 에러 처리 + 로깅 (Phase 2에서 부분 해결) |

#### 중간 (데이터/의존성 필요)

| 현재 | 문제점 | 권장 |
|------|--------|------|
| Jaccard 유사도 중복 감지 | 의미적 중복 감지 불가 | sentence-transformers 임베딩 |
| 단어 수/길이 기반 난이도 | 어휘 빈도 무시, CEFR 무관 | GSL/AWL 어휘 프로파일 + CEFR |
| 단일 overall_score (1-10) | LLM이 5-8 편중, 기준 불명확 | G-Eval 패턴 1-5 스케일 (Phase 2에서 해결) |

#### 낮음 (장기)

| 현재 | 권장 |
|------|------|
| MIPROv2 단독 | GEPA (소규모) → MIPROv2 (중규모) → BetterTogether (대규모) |
| 단일 모델 검증 | 2-모델 합의 검증 (Claude + GPT) |

### 9.2 dspy.Refine vs dspy.BestOfN

```
BestOfN: N개 독립 병렬 생성 → 최고 선택 (빠름, 품질 보통)
Refine:  순차 생성, 실패 시 피드백 반영 후 재시도 (느림, 품질 우수)
```

시험 문항 생성은 **품질이 최우선**이므로 `dspy.Refine` 권장.

### 9.3 JSONAdapter + Pydantic

```python
# 현재: 문자열로 받아서 수동 파싱 (실패 가능)
question_json: str = dspy.OutputField(desc='JSON string...')
q = json.loads(candidate_json)  # ⚠️ 파싱 실패 가능

# 권장: Pydantic 모델로 직접 받기 (자동 검증)
result: ExamQuestion = dspy.OutputField()  # ✅ 타입 보장
dspy.configure(adapter=dspy.JSONAdapter())
```

### 9.4 2-모델 합의 검증

```python
# 현재: Claude 1회 호출
verify_result = self.verifier(question=..., answer=...)

# 권장: Claude + GPT 각각 검증 후 비교
# - 두 모델 동의 → 높은 신뢰도
# - 불일치 → 사람 검토 플래그
```

비용 2배이지만, 시험 문항 오답은 학생에게 직접적 피해 → **비용 대비 가치 높음**.

---

## 10. LLM 통합 테스트 전략

> 출처: `docs/PHASE-2-LLM-TEST-REQUIREMENTS.md`

### 10.1 필요한 API 키

```bash
# backend/.env
OPENAI_API_KEY=sk-...          # GPT-5.2 (문항 생성)
ANTHROPIC_API_KEY=sk-ant-...   # Claude Sonnet 4.6 (검증/채점)
GEMINI_API_KEY=...             # Gemini 3.1 Pro (선택, 향후 확장)
```

### 10.2 문항 1개 생성 시 API 호출 흐름

```
문항 1개 생성 = Best-of-3 + 검증 + 채점

GPT-5.2 생성 × 3회 = 3 API 호출
Claude 검증 × 3후보 = 3 API 호출
Claude 채점 × 3후보 = 3 API 호출
───────────────────────────
합계: ~9 API 호출/문항
```

### 10.3 테스트 레벨

| 레벨 | 실행 방법 | API 키 필요 | 문항 수 |
|------|----------|------------|--------|
| **유닛 테스트** | `uv run pytest` | 불필요 | 46개 통과 |
| **Smoke 테스트** | `uv run pytest -m integration` | 필요 | 5개 |
| **등급별 커버리지** | 6등급 × 5문항 | 필요 | 30문항 |
| **유형별 커버리지** | 6유형 × 5문항 | 필요 | 30문항 |
| **MIPROv2 최적화** | 별도 스크립트 | 필요 | 500+ 호출 |

### 10.4 Golden Dataset

40개 수동 검증된 문항으로 구성 (현재 5개 준비, 40개까지 확장 예정):

| 등급 | 최소 문항 | CEFR 대응 |
|------|----------|----------|
| phonics | 5 | pre-A1 |
| elementary_low | 5 | A1 |
| elementary_mid | 5 | A1-A2 |
| elementary_high | 5 | A2 |
| middle | 10 | B1 |
| high | 10 | B2 |

### 10.5 성공 기준

| 지표 | 목표 |
|------|------|
| Quality Filter 통과율 | ≥ 80% |
| 평균 Overall Score | ≥ 7.0/10 (이전 기준) |
| 검증 정확도 (오답 감지율) | ≥ 95% |
| False Positive율 | ≤ 5% |
| 문항당 지연 시간 | ≤ 30초 (Best-of-3 포함) |

---

## 11. 향후 로드맵

### Phase 2A — 즉시 적용 (코드 변경만)

- [ ] `dspy.JSONAdapter` + Pydantic 출력 모델
- [ ] `dspy.Refine` 적용 (수동 루프 교체)
- [ ] 통합 테스트 실행 및 결과 분석

### Phase 2B — 데이터/의존성 필요

- [ ] Golden Dataset 40문항 확장
- [ ] GEPA 옵티마이저 도입
- [ ] sentence-transformers 기반 시맨틱 중복 감지
- [ ] GSL/AWL 어휘 프로파일

### Phase 3 — 고도화

- [ ] 2-모델 합의 검증 (Claude + GPT)
- [ ] CEFR 자동 분류 모델
- [ ] BetterTogether 옵티마이저
- [ ] Playwright E2E 테스트
- [ ] Rate limiting, Docker 배포

---

## 12. 핵심 용어 사전

| 용어 | 설명 |
|------|------|
| **DSPy** | Stanford 개발 선언적 LLM 프로그래밍 프레임워크. 프롬프트를 코드로 작성하고 자동 최적화 |
| **Signature** | DSPy에서 입력/출력을 선언하는 클래스 (함수 시그니처와 유사) |
| **ChainOfThought** | LLM에게 단계별 추론을 유도하는 DSPy 모듈 |
| **MIPROv2** | Bayesian 탐색 기반 프롬프트 옵티마이저 (지시어 + few-shot 동시 최적화) |
| **GEPA** | LLM 반성적 프롬프트 진화 옵티마이저 (소규모 데이터에 강력, ICLR 2026 Oral) |
| **Best-of-N** | N개 후보를 생성하고 가장 좋은 것을 선택하는 전략 |
| **dspy.Refine** | Best-of-N의 발전형. 실패 시 피드백을 반영하여 재시도 |
| **JSONAdapter** | DSPy 어댑터. LLM 출력이 유효한 JSON임을 보장 |
| **G-Eval** | NeurIPS 2023 논문. LLM을 평가자로 사용할 때의 패턴 (분해된 루브릭 + 1-5 스케일) |
| **CEFR** | Common European Framework of Reference. 유럽 공통 언어 능력 기준 (A1~C2) |
| **GSL** | General Service List. 가장 빈번히 사용되는 영어 ~2,000 단어 |
| **AWL** | Academic Word List. 학술 영어 ~570 어휘 패밀리 |
| **Flesch-Kincaid** | 텍스트 가독성 측정 공식 (학년 수준 환산) |
| **Jaccard 유사도** | 두 집합의 교집합/합집합 비율. 단어 집합 비교에 사용 |
| **Semantic Energy** | 모델 불확실성 측정법. 임베딩 분산으로 환각 문항 감지 |
| **PRM** | Process Reward Model. 추론의 중간 단계까지 평가하는 모델 |
| **HITL** | Human-In-The-Loop. AI 판단이 불확실할 때 사람 개입 |
| **LiteLLM** | 다양한 LLM API를 통합 호출하는 라우터 (DSPy에 내장) |
| **Answer Matching** | 보기 없이 자유 응답을 생성한 뒤, 원래 정답과 비교하여 복수정답/오답 감지 |

---

## 참고 자료

### 프로젝트 문서
- `AGENTS.md` — 프로젝트 규칙, 기술 스택, 컨벤션
- `docs/PHASE-1-SETUP.md` — Phase 1 변경 내역, 아키텍처 결정
- `docs/PHASE-2-IMPROVEMENTS.md` — Phase 2 개선 사항, 검증 결과
- `docs/ALGORITHM-REVIEW.md` — 알고리즘 심층 리뷰, 개선 권장사항
- `docs/PHASE-2-LLM-TEST-REQUIREMENTS.md` — LLM 통합 테스트 요구사항
- `영어 시험지 자동 생성 시스템.pdf` — 원본 설계서

### 외부 참고
- [DSPy 공식 문서](https://dspy.ai/)
- [DSPy Modules](https://dspy.ai/learn/programming/modules/)
- [DSPy Optimizers](https://dspy.ai/learn/optimization/optimizers/)
- [DSPy Adapters](https://dspy.ai/learn/programming/adapters/)
- [G-Eval (NeurIPS 2023)](https://arxiv.org/abs/2303.16634)
- [GEPA (ICLR 2026 Oral)](https://arxiv.org/abs/2507.19457)
- [Sentence Transformers](https://sbert.net/)
- [CEFR-SP Corpus (EMNLP 2022)](https://aclanthology.org/2022.emnlp-main.416.pdf)
