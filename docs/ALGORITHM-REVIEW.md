# 백엔드 알고리즘 리뷰 (2025-2026 기준)

> **작성일**: 2026-02-28
> **범위**: DSPy 파이프라인, Quality Filter, Optimizer, 모델 라우팅
> **결론**: 현재 구조는 동작하나, DSPy 3.1.3의 최신 기능을 활용하지 못하는 부분이 다수 존재

---

## 요약: 현재 구조 vs 권장 구조

| 영역 | 현재 구현 | 권장 변경 | 우선순위 |
|------|----------|----------|---------|
| Best-of-N 샘플링 | 수동 for 루프 | `dspy.Refine` 또는 `dspy.BestOfN` 내장 모듈 | **높음** |
| JSON 출력 | 문자열 OutputField + `json.loads` 파싱 | Pydantic 모델 + `dspy.JSONAdapter` | **높음** |
| 중복 감지 | Jaccard 유사도 (단어 토큰) | 임베딩 기반 의미론적 유사도 (sentence-transformers) | **중간** |
| 난이도 측정 | 단어 수 + 평균 단어 길이 | CEFR 레벨 분류 + 어휘 빈도 리스트 (AWL/GSL) | **중간** |
| 품질 채점 | 단일 overall_score (1-10) | 분해된 루브릭 기반 채점 (G-Eval 패턴) | **중간** |
| 옵티마이저 | MIPROv2 | GEPA (소규모 데이터) 또는 MIPROv2 + GEPA 조합 | **낮음** (데이터 확보 후) |
| 에러 처리 | try/except + silent pass | `dspy.Refine(fail_count=N)` + 폴백 모델 | **높음** |

---

## 1. DSPy 파이프라인 구조

### 1.1 현재: 수동 Best-of-N 루프

**파일**: `backend/app/services/dspy_modules.py:173-255`

```python
# 현재 코드 — 수동 Best-of-N
for _ in range(self.best_of_n):
    try:
        gen_result = self.generator(...)
        candidates.append(gen_result.question_json)
    except Exception:
        continue  # 에러 무시
```

**문제점**:
1. DSPy 3.1.3에 내장된 `dspy.BestOfN`과 `dspy.Refine`을 사용하지 않음
2. 실패한 생성의 원인이 다음 시도에 전달되지 않음 (blind re-sampling)
3. `except Exception: continue` — 모든 예외를 무시하여 디버깅 불가
4. 병렬 생성 불가 (순차 루프)

### 권장: `dspy.Refine` 사용

```python
import dspy

class ExamPipeline(dspy.Module):
    def __init__(self, best_of_n: int = 3, quality_threshold: float = 0.80):
        super().__init__()
        self.generate = dspy.Refine(
            module=dspy.ChainOfThought(GenerateQuestion),
            N=best_of_n,
            reward_fn=self._quality_reward,
            threshold=quality_threshold,
            fail_count=1,  # 1회 형식 오류 허용
        )
        self.verifier = dspy.ChainOfThought(VerifyAnswer)

    def _quality_reward(self, example, prediction, trace=None):
        """Refine이 각 후보를 평가하는 reward 함수."""
        # 검증 + 채점을 reward_fn 안에서 수행
        with dspy.context(lm=get_evaluation_lm()):
            verify = self.verifier(...)
            score = self.scorer(...)
        return score.overall_score / 10.0

    def forward(self, **kwargs):
        return self.generate(**kwargs)
```

**`dspy.Refine` vs `dspy.BestOfN` 선택 기준**:

| | `BestOfN` | `Refine` |
|---|---|---|
| 생성 방식 | N개 독립 병렬 생성 | 순차, 실패 피드백 반영 |
| 지연 시간 | 낮음 (병렬 가능) | 높음 (순차) |
| 품질 | 좋음 | 더 좋음 (피드백 루프) |
| 추천 상황 | 속도 중시 | 품질 중시 |

**시험 문항 생성은 품질이 최우선이므로 `dspy.Refine` 권장.**

> 출처: [DSPy Output Refinement](https://dspy.ai/tutorials/output_refinement/best-of-n-and-refine/), [DSPy Modules](https://dspy.ai/learn/programming/modules/)

---

### 1.2 현재: 문자열 기반 JSON 출력

**파일**: `backend/app/services/dspy_modules.py:21-35`

```python
# 현재 코드 — 문자열로 JSON을 받아 수동 파싱
class GenerateQuestion(dspy.Signature):
    question_json: str = dspy.OutputField(
        desc='A single question as JSON: {"question_text":"...", ...}'
    )

# 사용 시 매번 json.loads + try/except 필요
q = json.loads(candidate_json)  # 파싱 실패 가능
```

**문제점**:
1. LLM이 유효하지 않은 JSON을 생성할 가능성 (파싱 실패)
2. 필드 누락을 런타임에서야 발견
3. DSPy의 Pydantic 네이티브 통합을 사용하지 않음
4. 프롬프트에 JSON 스키마를 수동으로 설명해야 함

### 권장: Pydantic 모델 + JSONAdapter

```python
import pydantic
import dspy

class ChoiceItem(pydantic.BaseModel):
    label: str  # "A", "B", "C", "D"
    text: str

class ExamQuestion(pydantic.BaseModel):
    question_text: str
    choices: list[ChoiceItem] | None = None
    correct_answer: str
    explanation: str  # 한국어 해설
    passage: str | None = None

class GenerateQuestion(dspy.Signature):
    """Generate ONE high-quality English exam question."""
    grade_level: str = dspy.InputField()
    question_type: str = dspy.InputField()
    topic: str = dspy.InputField()
    difficulty: int = dspy.InputField()
    grade_description: str = dspy.InputField()
    type_instruction: str = dspy.InputField()
    result: ExamQuestion = dspy.OutputField()  # Pydantic 모델 직접 사용

# JSONAdapter로 구조화된 출력 보장
dspy.configure(lm=gpt5, adapter=dspy.JSONAdapter())

# 사용 시 — 자동 파싱, 타입 검증
gen = dspy.ChainOfThought(GenerateQuestion)
output = gen(grade_level="middle", ...)
question = output.result  # ExamQuestion 타입, json.loads 불필요
```

**이점**:
- GPT-5.2의 `response_format` 기능으로 100% 유효한 JSON 보장
- Pydantic 자동 검증 (필드 누락, 타입 오류 즉시 감지)
- 프롬프트 토큰 절약 (스키마를 자연어로 설명할 필요 없음)

> 출처: [DSPy Adapters](https://dspy.ai/learn/programming/adapters/), [DSPy Signatures](https://dspy.ai/learn/programming/signatures/)

---

### 1.3 현재: 에러 처리 — Silent Pass

**파일**: `backend/app/services/dspy_modules.py:190-222`

```python
# 현재 코드 — 예외를 모두 무시
except Exception:
    continue  # 생성 실패 원인 불명

except Exception:
    pass  # 검증 실패 시 검증 없이 진행
```

**문제점**:
1. API 키 오류, 모델 변경, 응답 형식 변경 등을 감지 불가
2. 검증 실패 시 미검증 문항이 "검증됨"으로 표시될 수 있음
3. 프로덕션에서 silent failure는 가장 위험한 버그 패턴

### 권장: 계층화된 에러 처리

```python
import logging
logger = logging.getLogger(__name__)

class ExamPipeline(dspy.Module):
    def forward(self, **kwargs):
        # Layer 1: Refine이 자체 재시도 관리
        try:
            result = self.generate(**kwargs)
        except dspy.DSPyError as e:
            logger.error(f"DSPy pipeline error: {e}")
            # Layer 2: 폴백 모델
            with dspy.context(lm=get_fallback_lm()):
                result = self.generate(**kwargs)

        # Layer 3: 검증 실패는 명시적으로 기록
        try:
            verification = self.verify(result)
        except Exception as e:
            logger.warning(f"Verification failed: {e}")
            result.verified = False  # 미검증 상태 명시
            result.verification_error = str(e)

        return result
```

---

## 2. Quality Filter

### 2.1 현재: Jaccard 유사도 중복 감지

**파일**: `backend/app/services/quality_filter.py:52-92`

```python
# 현재 — 단어 토큰 기반 Jaccard
def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.lower()))

def _jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b)
```

**문제점**:
1. **의미론적 중복을 감지하지 못함**: "What is the capital of France?" vs "Which city serves as France's capital?"은 Jaccard 유사도가 낮지만 의미적으로 동일
2. **어순 무시**: 완전히 다른 의미의 문장도 같은 단어를 사용하면 중복으로 분류
3. O(n²) 복잡도: 문항 수 증가 시 성능 저하

### 권장: 의미론적 유사도 (sentence-transformers)

```python
from sentence_transformers import SentenceTransformer
import numpy as np

class SemanticDuplicateDetector:
    """임베딩 기반 의미론적 중복 감지.

    all-MiniLM-L6-v2: 384차원, ~22MB, CPU에서도 빠름.
    """
    def __init__(self, threshold: float = 0.85):
        self.threshold = threshold
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self._embeddings: list[np.ndarray] = []

    def is_duplicate(self, question_text: str) -> bool:
        embedding = self.model.encode(question_text, normalize_embeddings=True)
        for seen in self._embeddings:
            similarity = float(np.dot(embedding, seen))
            if similarity >= self.threshold:
                return True
        self._embeddings.append(embedding)
        return False
```

**추가 의존성**: `sentence-transformers>=3.0.0` (약 50MB, CPU 전용 모드 가능)

**단계적 적용 방안**:
1. Phase 1 (현재): Jaccard 유지 (LLM 없이 동작)
2. Phase 2: `sentence-transformers` 추가, 두 방식 병렬 실행하여 결과 비교
3. Phase 3: 의미론적 감지가 우수하면 Jaccard 제거

> 출처: [Sentence Transformers Docs](https://sbert.net/docs/sentence_transformer/usage/semantic_textual_similarity.html), [SemHash](https://github.com/MinishLab/semhash)

---

### 2.2 현재: 난이도 캘리브레이션 — 단어 수/길이 기반

**파일**: `backend/app/services/quality_filter.py:183-245`

```python
# 현재 — 단어 수와 평균 단어 길이만 사용
_DIFFICULTY_THRESHOLDS = {
    1: {"min_words": 3, "max_words": 20, "min_avg_len": 2.0, "max_avg_len": 5.5},
    # ...
}
```

**문제점**:
1. **어휘 빈도를 고려하지 않음**: "ubiquitous"(고급)와 "big"(기초)를 동일하게 취급
2. **문법 복잡도 무시**: 단문 vs 복합문, 수동태, 관계절 등 미반영
3. **CEFR/수능 기준과 괴리**: 한국 영어 교육과정의 실제 난이도 기준과 무관한 휴리스틱

### 권장: CEFR 기반 다차원 난이도 평가

```python
import re
from collections import Counter

# CEFR 어휘 수준 분류 (GSL = A1-A2, AWL = B1-B2, Off-list = C1-C2)
# 실제 구현 시 외부 데이터 파일 로드
GSL_WORDS: set[str] = set()   # General Service List (~2,000 단어)
AWL_WORDS: set[str] = set()   # Academic Word List (~570 word families)

class CEFRDifficultyCalibrator:
    """CEFR 기반 다차원 난이도 평가.

    차원:
    1. 어휘 프로파일 (GSL/AWL/Off-list 비율)
    2. 문장 복잡도 (평균 문장 길이, 종속절 수)
    3. Flesch-Kincaid 가독성 지수
    """

    # 등급별 CEFR 매핑
    GRADE_CEFR_MAP = {
        "phonics": "pre-A1",
        "elementary_low": "A1",
        "elementary_mid": "A1-A2",
        "elementary_high": "A2",
        "middle": "B1",
        "high": "B2",
    }

    def check(self, question) -> list[str]:
        text = (question.passage or "") + " " + question.question_text
        words = re.findall(r"\b[a-zA-Z]+\b", text.lower())

        reasons = []

        # 1. 어휘 프로파일
        vocab_profile = self._vocab_profile(words)
        reasons.extend(self._check_vocab_level(
            vocab_profile, question.difficulty, question.grade_level
        ))

        # 2. Flesch-Kincaid
        fk_grade = self._flesch_kincaid(text)
        reasons.extend(self._check_readability(
            fk_grade, question.difficulty
        ))

        # 3. 문장 복잡도
        complexity = self._sentence_complexity(text)
        reasons.extend(self._check_complexity(
            complexity, question.difficulty
        ))

        return reasons

    def _vocab_profile(self, words: list[str]) -> dict:
        total = len(words) or 1
        gsl_count = sum(1 for w in words if w in GSL_WORDS)
        awl_count = sum(1 for w in words if w in AWL_WORDS)
        off_list = total - gsl_count - awl_count
        return {
            "gsl_ratio": gsl_count / total,
            "awl_ratio": awl_count / total,
            "off_list_ratio": off_list / total,
        }

    def _flesch_kincaid(self, text: str) -> float:
        """Flesch-Kincaid Grade Level."""
        sentences = len(re.findall(r"[.!?]+", text)) or 1
        words = re.findall(r"\b[a-zA-Z]+\b", text)
        word_count = len(words) or 1
        syllables = sum(self._count_syllables(w) for w in words)
        return 0.39 * (word_count / sentences) + 11.8 * (syllables / word_count) - 15.59

    @staticmethod
    def _count_syllables(word: str) -> int:
        word = word.lower()
        count = len(re.findall(r"[aeiouy]+", word))
        if word.endswith("e"):
            count -= 1
        return max(count, 1)
```

**추가 데이터 필요**:
- `data/gsl_words.txt` — General Service List (~2,000 단어)
- `data/awl_words.txt` — Academic Word List (~570 word families)
- 출처: [GSL by Frequency](https://www.eapfoundation.com/vocab/general/gsl/frequency/), [AWL](https://www.eapfoundation.com/vocab/academic/awllists/)

**단계적 적용**:
1. Flesch-Kincaid 지수 추가 (외부 의존성 없음)
2. GSL/AWL 어휘 프로파일 추가 (데이터 파일 필요)
3. CEFR 레벨 자동 분류 (선택: `cefr-english-level-predictor` 모델)

> 출처: [CEFR-SP Corpus (EMNLP 2022)](https://aclanthology.org/2022.emnlp-main.416.pdf), [CEFR Level Predictor](https://github.com/AMontgomerie/CEFR-English-Level-Predictor), [Ace-CEFR Dataset (2025)](https://www.arxiv.org/pdf/2506.14046)

---

## 3. 옵티마이저: MIPROv2 vs GEPA

### 현재: MIPROv2

**파일**: `backend/app/services/dspy_modules.py:291-302`

```python
MIPROv2(
    metric=question_quality_metric,
    auto="medium",
    num_threads=2,
    max_bootstrapped_demos=4,
    max_labeled_demos=4,
)
```

### 최신 비교 (2025-2026)

| | MIPROv2 | GEPA | SIMBA |
|---|---|---|---|
| **원리** | Bayesian 탐색 + 부트스트랩 | LLM 반성적 프롬프트 진화 | 확률적 미니배치 + 규칙 생성 |
| **필요 데이터** | 40+ 예제 권장 | 3-10 예제 가능 | 50+ 예제 |
| **MIPROv2 대비 성능** | 기준 | +13% (aggregate) | 대규모에서 우위 |
| **비용** | 높음 (Bayesian 탐색) | 낮음 (적은 rollout) | 중간 |
| **피드백 활용** | 숫자 점수만 | 텍스트 피드백 + 점수 | 숫자 점수 |
| **강점** | 범용, 안정적 | 소규모 데이터, 도메인 피드백 | 대규모, 안정적 |

### 권장 전략

1. **초기 (데이터 <20개)**: GEPA — 소규모에서 MIPROv2보다 월등
2. **중기 (데이터 50+)**: MIPROv2 `auto="medium"` — 현재 코드 유지
3. **고도화**: `BetterTogether` — MIPROv2 + BootstrapFinetune 조합

```python
# GEPA 사용 예시 (현재 metric 함수에 feedback 추가 필요)
def question_quality_metric(example, prediction, trace=None, pred_name=None, pred_trace=None):
    if not prediction.best_question:
        return {"score": 0.0, "feedback": "No question generated"}

    q = json.loads(prediction.best_question)
    issues = []
    score = 0.0

    if q.get("question_text") and q.get("correct_answer"):
        score += 0.3
    else:
        issues.append("Missing required fields")

    # ... 채점 로직 ...

    feedback = "; ".join(issues) if issues else "Question meets quality standards"
    return {"score": min(score, 1.0), "feedback": feedback}

optimizer = dspy.GEPA(
    metric=question_quality_metric,
    reflection_lm=dspy.LM("openai/gpt-5.2", temperature=1.0),
    auto="medium",
)
```

> 출처: [GEPA (ICLR 2026 Oral)](https://arxiv.org/abs/2507.19457), [DSPy Optimizers](https://dspy.ai/learn/optimization/optimizers/), [GEPA API](https://dspy.ai/api/optimizers/GEPA/overview/)

---

## 4. 채점 모듈 개선

### 현재: 단일 모델 단일 호출

**파일**: `backend/app/services/dspy_modules.py:52-67`

```python
class ScoreQuestion(dspy.Signature):
    clarity_score: int = dspy.OutputField(desc="1-10")
    accuracy_score: int = dspy.OutputField(desc="1-10")
    difficulty_match: int = dspy.OutputField(desc="1-10")
    distractor_quality: int = dspy.OutputField(desc="1-10")
    overall_score: int = dspy.OutputField(desc="1-10")
```

**문제점**:
1. 1-10 스케일은 LLM이 일관되게 사용하기 어려움 (5-8에 편중 경향)
2. `overall_score`가 서브 점수의 가중 평균인지 독립 평가인지 불명확
3. 구체적인 루브릭 없이 추상적 기준만 제시

### 권장: G-Eval 패턴 — 분해된 루브릭 + 1-5 스케일

```python
class ScoreQuestion(dspy.Signature):
    """Score an exam question using specific rubric criteria.
    Rate each dimension 1-5:
    1=Poor, 2=Below Average, 3=Acceptable, 4=Good, 5=Excellent."""

    question_text: str = dspy.InputField()
    choices: str = dspy.InputField()
    correct_answer: str = dspy.InputField()
    grade_level: str = dspy.InputField()
    difficulty: int = dspy.InputField()

    # 1-5 스케일 (LLM이 더 일관되게 사용)
    grammar_accuracy: int = dspy.OutputField(
        desc="1-5: Is every sentence grammatically correct with no errors?"
    )
    answer_unambiguity: int = dspy.OutputField(
        desc="1-5: Is exactly ONE option clearly and unambiguously correct?"
    )
    distractor_plausibility: int = dspy.OutputField(
        desc="1-5: Are wrong options plausible enough to test knowledge, not trick?"
    )
    difficulty_alignment: int = dspy.OutputField(
        desc="1-5: Does the question complexity match the intended difficulty level?"
    )
    educational_value: int = dspy.OutputField(
        desc="1-5: Does this question test meaningful English knowledge?"
    )
    verdict: str = dspy.OutputField(
        desc="PASS if all scores >= 3 and total >= 18, else FAIL"
    )
```

**변경 포인트**:
- 10점 → 5점 스케일 (연구에서 LLM 평가의 일관성 향상 입증)
- 명확한 합격 기준: 모든 항목 3점 이상 AND 합계 18점 이상
- `educational_value` 추가 — 시험 문항으로서의 교육적 가치 판단

> 출처: [G-Eval (NeurIPS 2023)](https://arxiv.org/abs/2303.16634), [LLM-as-Judge Best Practices](https://www.montecarlodata.com/blog-llm-as-judge/)

---

## 5. MultiChainComparison — 합의 기반 검증

### 현재: 단일 검증

```python
# 현재 — Claude 1회 호출로 검증
verify_result = self.verifier(question_text=..., provided_answer=...)
if not verify_result.is_correct:
    q["correct_answer"] = verify_result.correct_answer
```

### 권장: `dspy.MultiChainComparison` 또는 다중 검증

```python
# 방법 1: MultiChainComparison — N개 추론 경로 비교
verifier = dspy.MultiChainComparison(VerifyAnswer, M=3)
# 내부적으로 3번 CoT 실행 후 최종 답 도출

# 방법 2: 2-모델 합의 (더 강력)
class ConsensusVerifier(dspy.Module):
    def __init__(self):
        self.verify_claude = dspy.ChainOfThought(VerifyAnswer)
        self.verify_gpt = dspy.ChainOfThought(VerifyAnswer)

    def forward(self, **kwargs):
        with dspy.context(lm=claude):
            result_1 = self.verify_claude(**kwargs)
        with dspy.context(lm=gpt5):
            result_2 = self.verify_gpt(**kwargs)

        # 두 모델이 동의하면 높은 신뢰도
        if result_1.is_correct == result_2.is_correct:
            return result_1  # 합의 도달
        else:
            # 불일치 시 제3 모델 또는 사람 검토 필요 플래그
            return dspy.Prediction(
                is_correct=False,
                needs_human_review=True,
                disagreement=f"Model 1: {result_1.correct_answer}, Model 2: {result_2.correct_answer}"
            )
```

**비용 대비 효과**:
- 단일 검증 → 2-모델 합의: API 비용 2배, 하지만 오답 통과율 대폭 감소
- 시험 문항에서 오답은 학생에게 직접적 피해 — 비용 대비 가치 높음

---

## 6. 프레임워크 변경 검토

### DSPy vs 대안 프레임워크

| 프레임워크 | 장점 | 단점 | 추천 |
|-----------|------|------|------|
| **DSPy 3.x** (현재) | 프롬프트 최적화, 모듈화, 멀티모델 | 학습 곡선, 디버깅 어려움 | **유지** |
| LangChain | 광범위 통합, RAG 강점 | 프롬프트 최적화 없음, 추상화 과다 | 불필요 |
| Instructor | Pydantic 구조화 출력 특화 | 최적화 없음, 파이프라인 미약 | 부분 참고 |
| Haystack | 파이프라인 + RAG | 프롬프트 최적화 없음 | 불필요 |

**결론**: DSPy 유지 권장. `dspy.Refine`, `dspy.JSONAdapter`, `GEPA` 등 최신 기능 활용으로 충분.

### 모델 선택 재평가

| 역할 | 현재 모델 | 대안 | 권장 |
|------|----------|------|------|
| 생성 | GPT-5.2 | Claude Opus 4.6, Gemini 3.1 Pro | GPT-5.2 유지 (reasoning 모델 적합) |
| 검증/채점 | Claude Sonnet 4.6 | GPT-5.2, Gemini 3.1 Pro | Claude Sonnet 4.6 유지 (분석 정확도 높음) |
| 장문맥 (지문) | 미사용 | Gemini 3.1 Pro (1M context) | 향후 reading_comprehension에 활용 고려 |

---

## 7. 구현 로드맵

### Phase 2A: 즉시 적용 가능 (코드 변경만)

| 변경 | 난이도 | 영향도 | 의존성 |
|------|--------|-------|--------|
| `dspy.JSONAdapter` + Pydantic 출력 모델 | 낮음 | 높음 | 없음 |
| `dspy.Refine` 적용 (수동 루프 교체) | 중간 | 높음 | 없음 |
| Silent catch 제거 + 로깅 추가 | 낮음 | 중간 | 없음 |
| 채점 스케일 1-10 → 1-5 + 루브릭 | 낮음 | 중간 | 없음 |
| Flesch-Kincaid 가독성 지수 추가 | 낮음 | 중간 | 없음 |

### Phase 2B: 데이터/의존성 필요

| 변경 | 난이도 | 영향도 | 의존성 |
|------|--------|-------|--------|
| GSL/AWL 어휘 프로파일 | 중간 | 높음 | 데이터 파일 |
| sentence-transformers 중복 감지 | 중간 | 중간 | `sentence-transformers` 패키지 |
| GEPA 옵티마이저 도입 | 중간 | 높음 | 검증된 문항 데이터 |

### Phase 3: 고도화

| 변경 | 난이도 | 영향도 | 의존성 |
|------|--------|-------|--------|
| 2-모델 합의 검증 | 높음 | 높음 | 추가 API 비용 |
| CEFR 자동 분류 모델 | 높음 | 높음 | 학습된 분류기 |
| BetterTogether 옵티마이저 | 높음 | 높음 | 대량 학습 데이터 |

---

## 참고 자료

- [DSPy 공식 문서](https://dspy.ai/)
- [DSPy Modules](https://dspy.ai/learn/programming/modules/)
- [DSPy Optimizers](https://dspy.ai/learn/optimization/optimizers/)
- [GEPA: Reflective Prompt Optimizer (ICLR 2026 Oral)](https://arxiv.org/abs/2507.19457)
- [DSPy Output Refinement: BestOfN and Refine](https://dspy.ai/tutorials/output_refinement/best-of-n-and-refine/)
- [DSPy Adapters (JSON/Chat)](https://dspy.ai/learn/programming/adapters/)
- [G-Eval: NLG Evaluation using LLMs (NeurIPS 2023)](https://arxiv.org/abs/2303.16634)
- [CEFR-SP Sentence Difficulty (EMNLP 2022)](https://aclanthology.org/2022.emnlp-main.416.pdf)
- [Ace-CEFR Dataset (2025)](https://www.arxiv.org/pdf/2506.14046)
- [Sentence Transformers](https://sbert.net/)
- [SemHash: Semantic Deduplication](https://github.com/MinishLab/semhash)
- [GSL/AWL Vocabulary Lists](https://www.eapfoundation.com/vocab/)
- [MCQ Generation with LLMs (COLING 2025)](https://aclanthology.org/2025.coling-main.154/)
- [MCQ Generation Methodology (arXiv 2025)](https://arxiv.org/abs/2506.04851)
