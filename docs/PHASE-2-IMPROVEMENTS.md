# Phase 2 — 개발 문서 (Development Document)

> **Date**: 2026-02-28
> **Phase**: 2 — Backend Algorithm Improvements & Test Infrastructure
> **Previous**: Phase 1 — Project scaffold, lint tooling, critical fixes

---

## 1. 변경 요약 (Summary of Changes)

Phase 2에서는 세 가지 영역을 개선했습니다:

| 영역 | 변경 내용 | 파일 수 |
|------|----------|--------|
| FastAPI 컨벤션 | 2026 기준 구조화된 로깅, 글로벌 에러 핸들링, CORS 설정 분리 | 4 |
| DSPy 파이프라인 | 1-5 스케일 루브릭, GEPA 호환 메트릭, Flesch-Kincaid 가독성 | 3 |
| 통합 테스트 인프라 | pytest 마커, API 키 스킵, smoke 테스트, golden 데이터셋 | 5 |

---

## 2. FastAPI 2026 컨벤션 적용

### 2.1 구조화된 로깅 (`backend/app/core/logging_config.py`)

**신규 파일** — 중앙 집중식 로깅 설정

```python
def setup_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
```

- `debug=True`일 때 DEBUG 레벨, 아닐 때 INFO
- SQLAlchemy, httpx 등 외부 라이브러리 로그는 WARNING으로 억제
- `main.py`에서 앱 시작 시 호출

### 2.2 글로벌 예외 핸들러 (`backend/app/main.py`)

```python
@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
```

- 처리되지 않은 예외가 클라이언트에 스택 트레이스 노출하지 않도록 방지
- 모든 미처리 예외를 로깅 후 500 응답 반환

### 2.3 CORS 설정 분리 (`backend/app/core/config.py`)

```python
cors_origins: list[str] = ["http://localhost:3000"]
```

- 하드코딩된 CORS origins를 Settings 클래스로 이동
- 환경변수 `CORS_ORIGINS`로 오버라이드 가능
- `main.py`에서 `settings.cors_origins` 참조

---

## 3. DSPy 파이프라인 개선

### 3.1 스코어링 루브릭 변경 (1-10 → 1-5)

**근거**: G-Eval 연구 (NeurIPS 2023)에 따르면 1-5 스케일이 1-10보다 LLM 평가에서
더 일관된 결과를 생성합니다. 각 점수에 명시적 기준(anchor)을 제공합니다.

**ScoreQuestion Signature 변경**:

| 차원 | 이전 | 이후 |
|------|------|------|
| clarity_score | 1-10 (기준 없음) | 1-5 (1=Very unclear, 3=Acceptable, 5=Crystal clear) |
| accuracy_score | 1-10 | 1-5 (1=Major errors, 3=Acceptable, 5=Perfectly correct) |
| difficulty_match | 1-10 | 1-5 (1=Completely mismatched, 3=Roughly aligned, 5=Perfect) |
| distractor_quality | 1-10 | 1-5 (1=Trivially obvious, 3=Acceptable, 5=Excellent) |
| overall_score | 1-10 | 1-5 (1=Reject, 3=Acceptable, 5=Excellent) |

**verdict 필드 추가**: `"PASS if overall_score >= 3 and no individual score is 1, else FAIL"`

**quality_threshold 변경**: 6 → 3 (1-5 스케일에 맞춤)

### 3.2 GEPA 호환 메트릭

`question_quality_metric()`이 이제 `{"score": float, "feedback": str}` dict를 반환합니다.

- `score`: 0.0-1.0 범위의 정규화된 품질 점수
- `feedback`: 문제점 설명 또는 "Question meets quality standards"
- MIPROv2는 `score` 키를 읽고, GEPA는 `feedback`도 활용 (reflective optimization)

### 3.3 로깅 추가

모든 `except Exception` 블록에 `logger.warning()` 추가:
- 질문 생성 실패 → 로그 기록 후 계속
- 답변 검증 실패 → 로그 기록 후 기본값 사용
- 품질 스코어링 실패 → 로그 기록 후 기본 점수 3

이전에는 `pass`로 무시되던 에러가 이제 추적 가능합니다.

---

## 4. 품질 필터 개선

### 4.1 Flesch-Kincaid 가독성 지수

`DifficultyCalibrator`에 Flesch-Kincaid Grade Level 체크 추가:

```python
FK = 0.39 × (words/sentences) + 11.8 × (syllables/words) − 15.59
```

| 난이도 | FK 최소 | FK 최대 | 비고 |
|--------|---------|---------|------|
| 1 | -5.0 | 8.0 | 매우 쉬운 텍스트 허용 |
| 2 | -2.0 | 10.0 | |
| 3 | 0.0 | 14.0 | 중학교 수준 |
| 4 | 2.0 | 16.0 | |
| 5 | 4.0 | 20.0 | 대학 수준까지 허용 |

- 범위가 넓은 이유: 단일 문장 문제에서 FK 지수의 신뢰도가 낮기 때문
- 기존 단어 수/평균 길이 체크와 함께 보조 지표로 사용
- `_count_syllables()`: 모음 그룹 휴리스틱 (silent-e 처리 포함)

---

## 5. 통합 테스트 인프라

### 5.1 구조

```
backend/tests/
├── conftest.py              # 기존 유닛 테스트 설정
├── test_quality_filter.py   # 기존 유닛 테스트 (41개)
├── fixtures/
│   └── golden_questions.json  # 골든 데이터셋 (5문항)
└── integration/
    ├── __init__.py
    ├── conftest.py            # API 키 스킵, LM fixtures
    └── test_smoke.py          # 5개 스모크 테스트
```

### 5.2 pytest 마커 (`backend/pyproject.toml`)

```toml
[tool.pytest.ini_options]
markers = [
    "integration: LLM API tests (require API keys)",
    "slow: tests taking >30s",
    "optimization: MIPROv2/GEPA optimization tests",
]
```

실행:
- `uv run pytest` — 유닛 테스트만 (46개, API 키 불필요)
- `uv run pytest -m integration` — 통합 테스트만
- `uv run pytest -m "not integration"` — 통합 제외

### 5.3 스모크 테스트 (API 키 필요)

| 테스트 | 검증 내용 |
|--------|----------|
| `test_generation_lm_connection` | GPT-5.2 연결 및 응답 |
| `test_evaluation_lm_connection` | Claude 4.6 연결 및 응답 |
| `test_single_question_generation` | 전체 파이프라인 MC 문제 생성 |
| `test_quality_filter_on_generated` | 생성된 문제에 품질 필터 적용 |
| `test_verification_catches_wrong_answer` | 검증기가 오답 감지 |

### 5.4 골든 데이터셋

5개 표준 문항 (phonics, elementary_low MC, elementary_mid fill-in-blank, middle grammar, high reading_comprehension)을 fixtures로 관리. 향후 40문항까지 확장 예정.

---

## 6. 검증 결과

모든 변경사항 적용 후 검증 완료:

| 검증 항목 | 결과 |
|----------|------|
| `ruff check` | All checks passed |
| `pytest` | 46 passed, 5 skipped (integration) |
| `biome check` | 25 files checked, no issues |
| `next build` | Compiled successfully |

---

## 7. 관련 문서

| 문서 | 설명 |
|------|------|
| `docs/ALGORITHM-REVIEW.md` | DSPy 파이프라인, 품질 필터, 스코어링 알고리즘 심층 리뷰 |
| `docs/PHASE-2-LLM-TEST-REQUIREMENTS.md` | LLM 통합 테스트 요구사항, 데이터셋, 비용 추정 |

---

## 8. 향후 계획 (Phase 3 로드맵)

### 즉시 적용 가능 (Phase 2A — API 키 설정 후)
- [ ] 통합 테스트 실행 및 결과 분석
- [ ] `dspy.Refine` 모듈 적용 (자체 피드백 루프)
- [ ] `dspy.JSONAdapter` + Pydantic 출력 전환

### 중기 개선 (Phase 2B)
- [ ] 골든 데이터셋 40문항 확장
- [ ] GEPA 옵티마이저 적용 (MIPROv2 대비 +13%)
- [ ] sentence-transformers 기반 시맨틱 중복 감지

### 장기 고도화 (Phase 3)
- [ ] CEFR 레벨 자동 감지 (어휘 빈도 프로파일링)
- [ ] 멀티모달 지원 (Gemini 3.1 Pro)
- [ ] 대시보드 분석 기능 (품질 트렌드, 모델 비교)

---

## 변경 파일 목록

### 신규 파일
- `backend/app/core/logging_config.py`
- `backend/tests/integration/__init__.py`
- `backend/tests/integration/conftest.py`
- `backend/tests/integration/test_smoke.py`
- `backend/tests/fixtures/golden_questions.json`
- `docs/ALGORITHM-REVIEW.md`
- `docs/PHASE-2-LLM-TEST-REQUIREMENTS.md`
- `docs/PHASE-2-IMPROVEMENTS.md` (이 문서)

### 수정 파일
- `backend/app/core/config.py` — CORS 설정, quality_threshold 조정
- `backend/app/main.py` — 로깅, 예외 핸들러, CORS 설정 참조
- `backend/app/services/dspy_modules.py` — 1-5 스코어링, 로깅, GEPA 메트릭
- `backend/app/services/quality_filter.py` — Flesch-Kincaid 가독성 체크
- `backend/pyproject.toml` — pytest 마커
- `AGENTS.md` — FastAPI 2026 컨벤션 섹션
