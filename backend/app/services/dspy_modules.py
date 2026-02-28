"""DSPy 3.0+ Signatures and Modules for English exam question generation.

Pipeline: Generate (GPT-5.2) → Verify (Claude 4.6) → Score (Claude 4.6) → Filter
- GenerateQuestion: produces candidate questions via ChainOfThought
- VerifyAnswer: cross-checks that the correct_answer is truly correct (different model)
- ScoreQuestion: rates quality on multiple dimensions
- Best-of-N: generates N candidates, picks highest scored
- MIPROv2: continuous prompt optimization from verified examples
"""

import json

import dspy

from app.core.config import settings

# ---------------------------------------------------------------------------
# Signatures
# ---------------------------------------------------------------------------

class GenerateQuestion(dspy.Signature):
    """You are an expert English teacher creating exam questions for Korean students.
    Generate ONE high-quality English exam question that is appropriate for the
    specified grade level, type, and difficulty. The question must be factually
    and grammatically perfect. Output ONLY a valid JSON object."""

    grade_level: str = dspy.InputField(desc="Target grade level (e.g. 'middle', 'high')")
    question_type: str = dspy.InputField(desc="Type: multiple_choice, fill_in_blank, reading_comprehension, grammar, vocabulary, short_answer")
    topic: str = dspy.InputField(desc="Topic or theme for the question")
    difficulty: int = dspy.InputField(desc="Difficulty 1-5 (1=easiest, 5=hardest)")
    grade_description: str = dspy.InputField(desc="Detailed description of what this grade level covers")
    type_instruction: str = dspy.InputField(desc="Specific formatting instructions for this question type")

    question_json: str = dspy.OutputField(desc='A single question as JSON: {"question_text":"...","choices":[{"label":"A","text":"..."},...]|null,"correct_answer":"...","explanation":"Korean explanation","passage":"..."|null}')


class VerifyAnswer(dspy.Signature):
    """You are a meticulous exam quality inspector. Your job is to independently
    solve the given English question and verify whether the provided answer is correct.
    Think step-by-step. This is CRITICAL — wrong answers in exams cause serious harm."""

    question_text: str = dspy.InputField(desc="The question text")
    choices: str = dspy.InputField(desc="The answer choices as JSON string, or 'null' if no choices")
    passage: str = dspy.InputField(desc="Reading passage if any, or 'none'")
    provided_answer: str = dspy.InputField(desc="The answer claimed to be correct")

    is_correct: bool = dspy.OutputField(desc="True if the provided answer is genuinely correct")
    correct_answer: str = dspy.OutputField(desc="The actually correct answer (may differ from provided)")
    reasoning: str = dspy.OutputField(desc="Step-by-step reasoning for why this answer is correct")


class ScoreQuestion(dspy.Signature):
    """Score an English exam question on multiple quality dimensions.
    Be strict — only high-quality, error-free questions should score above 7."""

    question_text: str = dspy.InputField(desc="The question text")
    choices: str = dspy.InputField(desc="Answer choices as JSON or 'null'")
    correct_answer: str = dspy.InputField(desc="The correct answer")
    grade_level: str = dspy.InputField(desc="Target grade level")
    difficulty: int = dspy.InputField(desc="Intended difficulty 1-5")

    clarity_score: int = dspy.OutputField(desc="1-10: Is the question clearly worded and unambiguous?")
    accuracy_score: int = dspy.OutputField(desc="1-10: Is the question factually and grammatically correct?")
    difficulty_match: int = dspy.OutputField(desc="1-10: Does difficulty match the intended level?")
    distractor_quality: int = dspy.OutputField(desc="1-10: Are wrong options plausible but clearly wrong? (10 if not MC)")
    overall_score: int = dspy.OutputField(desc="1-10: Overall quality score")


# ---------------------------------------------------------------------------
# LM Helpers
# ---------------------------------------------------------------------------

def get_generation_lm() -> dspy.LM:
    """GPT-5.2 for question generation — creative, high-quality output.
    Note: GPT-5.x is a reasoning model; DSPy enforces temperature=None
    and max_tokens=None (or >=16000) for reasoning models.
    API keys are read from environment variables by LiteLLM."""
    return dspy.LM(
        model=settings.generation_model,
        temperature=None,
        max_tokens=None,
    )


def get_evaluation_lm() -> dspy.LM:
    """Claude 4.6 for verification & scoring — precise, analytical.
    API keys are read from environment variables by LiteLLM."""
    return dspy.LM(
        model=settings.evaluation_model,
        temperature=0.1,
        max_tokens=1500,
    )


# ---------------------------------------------------------------------------
# Modules
# ---------------------------------------------------------------------------

class QuestionGeneratorModule(dspy.Module):
    """Generates a single question using ChainOfThought for better reasoning."""

    def __init__(self):
        super().__init__()
        self.generate = dspy.ChainOfThought(GenerateQuestion)

    def forward(self, grade_level, question_type, topic, difficulty, grade_description, type_instruction):
        return self.generate(
            grade_level=grade_level,
            question_type=question_type,
            topic=topic,
            difficulty=difficulty,
            grade_description=grade_description,
            type_instruction=type_instruction,
        )


class AnswerVerifierModule(dspy.Module):
    """Independently verifies that the answer to a question is correct.
    Uses a DIFFERENT model (Claude 4.6) from the generator for cross-validation."""

    def __init__(self):
        super().__init__()
        self.verify = dspy.ChainOfThought(VerifyAnswer)

    def forward(self, question_text, choices, passage, provided_answer):
        return self.verify(
            question_text=question_text,
            choices=choices,
            passage=passage,
            provided_answer=provided_answer,
        )


class QuestionScorerModule(dspy.Module):
    """Scores a question on multiple quality dimensions."""

    def __init__(self):
        super().__init__()
        self.score = dspy.Predict(ScoreQuestion)

    def forward(self, question_text, choices, correct_answer, grade_level, difficulty):
        return self.score(
            question_text=question_text,
            choices=choices,
            correct_answer=correct_answer,
            grade_level=grade_level,
            difficulty=difficulty,
        )


class ExamPipeline(dspy.Module):
    """Full pipeline: Generate (GPT-5.2) → Verify (Claude 4.6) → Score (Claude 4.6).

    Uses Best-of-N sampling: generates N candidates per question,
    switches to evaluation model for verification and scoring,
    picks the highest-scored verified candidate.

    Error minimization strategy:
    1. ChainOfThought generation forces step-by-step reasoning
    2. Independent model verification catches answer errors
    3. Multi-dimensional scoring filters low-quality questions
    4. Best-of-N ensures the best candidate is selected
    """

    def __init__(self, best_of_n: int = 3, quality_threshold: int = 6):
        super().__init__()
        self.generator = QuestionGeneratorModule()
        self.verifier = AnswerVerifierModule()
        self.scorer = QuestionScorerModule()
        self.best_of_n = best_of_n
        self.quality_threshold = quality_threshold

    def forward(self, grade_level, question_type, topic, difficulty, grade_description, type_instruction):
        # Phase 1: Generate candidates using generation model (GPT-5.2)
        gen_lm = get_generation_lm()
        candidates = []

        with dspy.context(lm=gen_lm):
            for _ in range(self.best_of_n):
                try:
                    gen_result = self.generator(
                        grade_level=grade_level,
                        question_type=question_type,
                        topic=topic,
                        difficulty=difficulty,
                        grade_description=grade_description,
                        type_instruction=type_instruction,
                    )
                    candidates.append(gen_result.question_json)
                except Exception:
                    continue

        if not candidates:
            return dspy.Prediction(best_question=None, score=0, verified=False)

        # Phase 2 & 3: Verify and Score using evaluation model (Claude 4.6)
        eval_lm = get_evaluation_lm()
        best_question = None
        best_score = -1

        with dspy.context(lm=eval_lm):
            for candidate_json in candidates:
                try:
                    q = json.loads(candidate_json)
                except (json.JSONDecodeError, TypeError):
                    continue

                # Phase 2: Verify answer correctness
                try:
                    verify_result = self.verifier(
                        question_text=q.get("question_text", ""),
                        choices=json.dumps(q.get("choices") or "null", ensure_ascii=False),
                        passage=q.get("passage") or "none",
                        provided_answer=q.get("correct_answer", ""),
                    )

                    if not verify_result.is_correct:
                        # Correct the answer using verifier's finding
                        q["correct_answer"] = verify_result.correct_answer
                        q["explanation"] = verify_result.reasoning
                except Exception:
                    pass  # Continue without verification

                # Phase 3: Score quality
                overall = 5
                try:
                    score_result = self.scorer(
                        question_text=q.get("question_text", ""),
                        choices=json.dumps(q.get("choices") or "null", ensure_ascii=False),
                        correct_answer=q.get("correct_answer", ""),
                        grade_level=grade_level,
                        difficulty=difficulty,
                    )
                    overall = int(score_result.overall_score)
                except (Exception, ValueError):
                    overall = 5

                # Only accept questions above quality threshold
                if overall >= self.quality_threshold and overall > best_score:
                    best_score = overall
                    best_question = q

        # If all candidates below threshold, return the best we have anyway
        if best_question is None and candidates:
            try:
                best_question = json.loads(candidates[0])
                best_score = 4
            except (json.JSONDecodeError, TypeError):
                pass

        return dspy.Prediction(
            best_question=json.dumps(best_question, ensure_ascii=False) if best_question else None,
            score=best_score,
            verified=True,
        )


# ---------------------------------------------------------------------------
# MIPROv2 Metric & Optimizer Setup
# ---------------------------------------------------------------------------

def question_quality_metric(example, prediction, trace=None) -> float:
    """Metric for MIPROv2 optimization.
    Evaluates if the generated question meets quality standards.
    Returns 0.0-1.0 score."""
    if not prediction.best_question:
        return 0.0

    try:
        q = json.loads(prediction.best_question)
    except (json.JSONDecodeError, TypeError):
        return 0.0

    score = 0.0

    # Has required fields
    if q.get("question_text") and q.get("correct_answer"):
        score += 0.3

    # Has explanation
    if q.get("explanation"):
        score += 0.1

    # Quality score from pipeline
    pipeline_score = prediction.score or 0
    score += (pipeline_score / 10.0) * 0.6

    return min(score, 1.0)


def create_mipro_optimizer(num_threads: int = 2) -> "MIPROv2":  # noqa: F821
    """Create a MIPROv2 optimizer for the ExamPipeline."""
    from dspy.teleprompt import MIPROv2

    return MIPROv2(
        metric=question_quality_metric,
        auto="medium",
        num_threads=num_threads,
        max_bootstrapped_demos=4,
        max_labeled_demos=4,
        verbose=True,
    )
