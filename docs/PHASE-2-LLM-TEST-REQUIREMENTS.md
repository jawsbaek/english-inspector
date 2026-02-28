# Phase 2: LLM 통합 테스트 요구사항

> **대상 독자**: 프로젝트 오너, LLM API 키 관리자
> **작성일**: 2026-02-28
> **상태**: 테스트 준비 완료, API 키 설정 대기

---

## 1. 필요한 API 키 및 설정

### 환경 변수 (`backend/.env`)

```bash
# 필수 — 문항 생성 (Generation)
OPENAI_API_KEY=sk-...          # GPT-5.2 사용
# 필수 — 검증 및 채점 (Verification & Scoring)
ANTHROPIC_API_KEY=sk-ant-...   # Claude Sonnet 4.6 사용
# 선택 — 멀티모달/장문맥 (향후 확장)
GEMINI_API_KEY=...             # Gemini 3.1 Pro
```

### 모델별 예상 비용

| 모델 | 용도 | 호출/문항 | 예상 토큰/호출 | 비고 |
|------|------|-----------|---------------|------|
| GPT-5.2 (`openai/gpt-5.2`) | 문항 생성 | 3회 (Best-of-3) | ~2,000 | reasoning 모델, temperature=None |
| Claude Sonnet 4.6 (`anthropic/claude-sonnet-4-6`) | 검증 + 채점 | 2회 (verify + score) × 3후보 = 6회 | ~800 | temperature=0.1 |
| **합계** | | **~9 API 호출/문항** | | 5문항 생성 시 ~45회 호출 |

### 최소 테스트 예산

- **Smoke test** (5문항 × 1회): ~45 API 호출
- **Grade level 전체 커버** (6등급 × 5문항): ~270 API 호출
- **Question type 전체 커버** (6유형 × 5문항): ~270 API 호출
- **MIPROv2 최적화** (15 trials): ~500+ API 호출
- **권장 초기 테스트 예산**: $20-50 (모델 가격에 따라 변동)

---

## 2. 테스트 데이터셋

### 2.1 Golden Dataset (정답 기준 데이터)

통합 테스트의 품질 판단 기준이 되는 수동 검증된 문항 세트가 필요합니다.

#### 구조

```json
{
  "id": "golden-001",
  "grade_level": "middle",
  "question_type": "multiple_choice",
  "topic": "daily_life",
  "difficulty": 3,
  "question_text": "Choose the correct word to complete the sentence: She ___ to school every day.",
  "choices": [
    {"label": "A", "text": "go"},
    {"label": "B", "text": "goes"},
    {"label": "C", "text": "going"},
    {"label": "D", "text": "gone"}
  ],
  "correct_answer": "B",
  "explanation": "3인칭 단수 현재시제에서 동사에 -es를 붙입니다.",
  "passage": null,
  "quality_scores": {
    "clarity": 9,
    "accuracy": 10,
    "difficulty_match": 8,
    "distractor_quality": 8,
    "overall": 9
  }
}
```

#### 필요 수량

| 등급 | 최소 문항 | 유형 분포 |
|------|----------|----------|
| phonics | 5 | vocabulary 3, fill_in_blank 2 |
| elementary_low | 5 | multiple_choice 2, vocabulary 2, fill_in_blank 1 |
| elementary_mid | 5 | multiple_choice 2, grammar 2, vocabulary 1 |
| elementary_high | 5 | multiple_choice 2, reading_comprehension 1, grammar 1, vocabulary 1 |
| middle | 10 | multiple_choice 3, reading_comprehension 2, grammar 2, fill_in_blank 1, vocabulary 1, short_answer 1 |
| high | 10 | multiple_choice 3, reading_comprehension 3, grammar 2, vocabulary 1, short_answer 1 |
| **합계** | **40** | |

#### 수집 방법

1. **수능/모의고사 기출문제** 변형 (저작권 주의 — 구조만 참고, 지문 변경)
2. **EBS 교재** 기반 유형 참고
3. **교사 직접 작성** — 가장 신뢰도 높음
4. **LLM 생성 후 교사 검수** — 효율적 (생성 후 교정)

### 2.2 Edge Case 데이터셋

파이프라인의 견고성을 검증하기 위한 경계 조건 테스트:

| 카테고리 | 테스트 케이스 | 예상 동작 |
|---------|-------------|----------|
| 극단 난이도 | difficulty=1 + high school | 경고 또는 자동 조정 |
| 극단 난이도 | difficulty=5 + phonics | 경고 또는 자동 조정 |
| 빈 토픽 | topic="" | 기본값 "general" 적용 |
| 특수 토픽 | topic="quantum physics" + elementary_low | 등급에 맞게 단순화 |
| 한국어 토픽 | topic="일상생활" | 영어로 변환 또는 처리 |
| 대량 생성 | count=30 (최대값) | 타임아웃 없이 완료 |
| 중복 요청 | 동일 조건 연속 3회 | 서로 다른 문항 생성 |

### 2.3 MIPROv2 최적화용 Training Set

최적화를 실행하려면 최소 5개, 권장 20개 이상의 고품질 검증 문항이 필요합니다.

```python
# backend/tests/fixtures/training_examples.py
TRAINING_EXAMPLES = [
    {
        "grade_level": "middle",
        "question_type": "multiple_choice",
        "topic": "daily_life",
        "difficulty": 3,
        "expected_question_json": '{"question_text": "...", "choices": [...], ...}',
        "expected_score": 9,
    },
    # ... 최소 20개
]
```

---

## 3. 테스트 시나리오

### 3.1 Smoke Test (최우선)

```bash
# 단일 문항 생성 — 파이프라인 전체 동작 확인
cd backend && uv run pytest tests/integration/test_smoke.py -v
```

검증 항목:
- [ ] GPT-5.2 API 연결 성공
- [ ] Claude Sonnet 4.6 API 연결 성공
- [ ] 문항 JSON 파싱 성공
- [ ] 검증(VerifyAnswer) 정상 동작
- [ ] 채점(ScoreQuestion) 정상 동작
- [ ] DB 저장 성공
- [ ] Quality Filter 통과

### 3.2 Grade Level 커버리지

각 등급(6개)별로 5문항씩 생성하여:
- [ ] 등급별 어휘 수준 적절성 (CEFR 기준)
- [ ] 등급별 문법 복잡도 적절성
- [ ] 난이도 캘리브레이션 정확도
- [ ] 한국어 해설(explanation) 품질

### 3.3 Question Type 커버리지

각 유형(6개)별로 5문항씩 생성하여:
- [ ] multiple_choice: 4지선다 형식 준수, 오답지 질
- [ ] fill_in_blank: `___` 포함, 정답 정확성
- [ ] reading_comprehension: 지문 + 문항 구조
- [ ] grammar: 문법 규칙 정확성
- [ ] vocabulary: 어휘 적절성
- [ ] short_answer: 모범 답안 품질

### 3.4 Best-of-N 품질 비교

```python
# N=1 vs N=3 vs N=5 품질 비교
# 동일 조건에서 N값에 따른 overall_score 분포 측정
```

- [ ] N=3이 N=1 대비 평균 점수 향상 확인
- [ ] N=5의 추가 비용 대비 품질 향상 폭 측정
- [ ] 최적 N값 결정

### 3.5 Cross-Model Verification 정확도

```python
# 검증 모듈의 오류 감지율 측정
# 의도적으로 틀린 답을 제공하고 검증 모듈이 감지하는지 확인
```

- [ ] 명백한 오답 감지율 (목표: >95%)
- [ ] 모호한 오답 감지율 (목표: >70%)
- [ ] False positive율 (정답을 오답으로 판정하는 비율, 목표: <5%)

### 3.6 Quality Filter 실전 검증

LLM이 실제 생성한 문항에 대해:
- [ ] DuplicateDetector: 동일 조건 반복 생성 시 중복 감지
- [ ] FormatValidator: LLM 출력 형식 불일치 감지
- [ ] DifficultyCalibrator: 난이도-복잡도 미스매치 감지
- [ ] 전체 pass_rate 측정 (목표: >80%)

---

## 4. 테스트 인프라 준비 사항

### 4.1 Integration Test 디렉토리 구조

```
backend/tests/
├── conftest.py              # 기존 (mock DB, auth fixtures)
├── integration/
│   ├── conftest.py          # LLM API 연결, 타임아웃 설정
│   ├── test_smoke.py        # Smoke test
│   ├── test_generation.py   # Grade/Type 커버리지
│   ├── test_verification.py # Cross-model 검증 정확도
│   ├── test_best_of_n.py    # N값 비교
│   └── test_optimization.py # MIPROv2 최적화
├── fixtures/
│   ├── golden_questions.json # Golden dataset
│   └── training_examples.py  # MIPROv2 training data
└── test_*.py                # 기존 단위 테스트
```

### 4.2 Integration Test Conftest

```python
# backend/tests/integration/conftest.py
import os
import pytest
import dspy

@pytest.fixture(scope="session")
def require_api_keys():
    """Skip integration tests if API keys are not set."""
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set")
    if not os.getenv("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")

@pytest.fixture(scope="session")
def generation_lm():
    return dspy.LM(model="openai/gpt-5.2", temperature=None, max_tokens=None)

@pytest.fixture(scope="session")
def evaluation_lm():
    return dspy.LM(model="anthropic/claude-sonnet-4-6", temperature=0.1, max_tokens=1500)

@pytest.fixture
def pipeline():
    from app.services.dspy_modules import ExamPipeline
    return ExamPipeline(best_of_n=3)
```

### 4.3 pytest 마커 설정

```toml
# backend/pyproject.toml 에 추가
[tool.pytest.ini_options]
markers = [
    "integration: LLM API 연동 테스트 (API 키 필요)",
    "slow: 10초 이상 소요되는 테스트",
    "optimization: MIPROv2 최적화 테스트",
]
```

```bash
# 단위 테스트만 실행 (기본)
uv run pytest -m "not integration"

# 통합 테스트만 실행 (API 키 필요)
uv run pytest -m integration

# 전체 실행
uv run pytest
```

### 4.4 테스트 결과 기록 형식

```json
{
  "test_run_id": "2026-02-28-001",
  "model_versions": {
    "generation": "openai/gpt-5.2",
    "evaluation": "anthropic/claude-sonnet-4-6"
  },
  "results": {
    "total_generated": 30,
    "quality_filter_passed": 25,
    "pass_rate": 0.833,
    "avg_overall_score": 7.4,
    "verification_accuracy": 0.96,
    "avg_latency_per_question_ms": 12500,
    "total_api_cost_usd": 3.45
  },
  "grade_level_breakdown": {
    "middle": {"generated": 5, "passed": 4, "avg_score": 7.6},
    "high": {"generated": 5, "passed": 5, "avg_score": 8.1}
  }
}
```

---

## 5. 실행 전 체크리스트

- [ ] `.env` 파일에 `OPENAI_API_KEY` 설정
- [ ] `.env` 파일에 `ANTHROPIC_API_KEY` 설정
- [ ] `uv sync` 로 의존성 최신화
- [ ] `uv run pytest -m "not integration"` — 기존 46개 단위 테스트 통과 확인
- [ ] Golden dataset (`tests/fixtures/golden_questions.json`) 최소 10개 준비
- [ ] 네트워크 연결 확인 (API 엔드포인트 접근 가능)
- [ ] `uv run pytest tests/integration/test_smoke.py -v` — Smoke test 실행

---

## 6. 성공 기준

| 지표 | 목표 | 비고 |
|------|------|------|
| Quality Filter Pass Rate | ≥ 80% | 생성된 문항 중 필터 통과 비율 |
| Average Overall Score | ≥ 7.0/10 | ScoreQuestion 평균 |
| Verification Accuracy | ≥ 95% | 오답 감지율 |
| False Positive Rate | ≤ 5% | 정답을 오답으로 판정 |
| Latency per Question | ≤ 30s | Best-of-3 포함 |
| Grade Appropriateness | ≥ 85% | 교사 검수 통과율 (수동) |
