"""DSPy 3.1+ Signatures and Modules for English exam question generation.

Pipeline: Generate (GPT-5.2) → Verify (Claude 4.6) → Score (Claude 4.6) → Filter
- GenerateQuestion: produces candidate questions via ChainOfThought
- VerifyAnswer: cross-checks that the correct_answer is truly correct (different model)
- ScoreQuestion: rates quality on multiple dimensions
- dspy.Refine: generates N candidates with feedback-based refinement, picks highest scored
- MIPROv2: continuous prompt optimization from verified examples

Key design decisions (see docs/ALGORITHM-REVIEW.md):
- Pydantic output model + dspy.JSONAdapter → guaranteed valid structured output
- dspy.Refine → feedback-aware retry replaces blind Best-of-N for loop
- Layered error handling → no silent failures; fallback model on pipeline errors
"""

import json
import logging

import dspy
import pydantic

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic Models for Structured Output (used with dspy.JSONAdapter)
# ---------------------------------------------------------------------------


class ChoiceItemOutput(pydantic.BaseModel):
    """A single answer choice for multiple-choice questions."""

    label: str  # "A", "B", "C", "D"
    text: str


class ExamQuestionOutput(pydantic.BaseModel):
    """Structured output for a generated exam question.

    Used as the output type for GenerateQuestion signature.
    dspy.JSONAdapter automatically validates LLM output against this schema.
    """

    question_text: str
    choices: list[ChoiceItemOutput] | None = None
    correct_answer: str
    explanation: str = ""  # Korean explanation
    passage: str | None = None


# ---------------------------------------------------------------------------
# Signatures
# ---------------------------------------------------------------------------


class GenerateQuestion(dspy.Signature):
    """You are an expert English teacher creating exam questions for Korean students.
    Generate ONE high-quality English exam question that is appropriate for the
    specified grade level, type, and difficulty. The question must be factually
    and grammatically perfect."""

    grade_level: str = dspy.InputField(desc="Target grade level (e.g. 'middle', 'high')")
    question_type: str = dspy.InputField(desc="Type: multiple_choice, fill_in_blank, reading_comprehension, grammar, vocabulary, short_answer")
    topic: str = dspy.InputField(desc="Topic or theme for the question")
    difficulty: int = dspy.InputField(desc="Difficulty 1-5 (1=easiest, 5=hardest)")
    grade_description: str = dspy.InputField(desc="Detailed description of what this grade level covers")
    type_instruction: str = dspy.InputField(desc="Specific formatting instructions for this question type")

    result: ExamQuestionOutput = dspy.OutputField(desc="The generated exam question with all required fields")


class VerifyAnswer(dspy.Signature):
    """You are a meticulous exam quality inspector. Your job is to independently
    solve the given English question and verify whether the provided answer is correct.
    Think step-by-step. This is CRITICAL — wrong answers in exams cause serious harm."""

    question_text: str = dspy.InputField(desc="The question text")
    choices: str = dspy.InputField(desc="The answer choices as JSON string, or 'null' if no choices")
    passage: str | None = dspy.InputField(desc="Reading passage for comprehension questions", default=None)
    provided_answer: str = dspy.InputField(desc="The answer claimed to be correct")

    is_correct: bool = dspy.OutputField(desc="True if the provided answer is genuinely correct")
    correct_answer: str = dspy.OutputField(desc="The actually correct answer (may differ from provided)")
    reasoning: str = dspy.OutputField(desc="Step-by-step reasoning for why this answer is correct")


class ScoreQuestion(dspy.Signature):
    """Score an English exam question using specific rubric criteria.
    Rate each dimension 1-5:
    1=Poor (major errors/issues), 2=Below Average, 3=Acceptable (meets minimum bar),
    4=Good (minor issues only), 5=Excellent (no issues)."""

    question_text: str = dspy.InputField(desc="The question text")
    choices: str = dspy.InputField(desc="Answer choices as JSON or 'null'")
    correct_answer: str = dspy.InputField(desc="The correct answer")
    passage: str | None = dspy.InputField(desc="Reading passage for comprehension questions", default=None)
    grade_level: str = dspy.InputField(desc="Target grade level")
    difficulty: int = dspy.InputField(desc="Intended difficulty 1-5")

    clarity_score: int = dspy.OutputField(desc="1-5: Is the question clearly worded and unambiguous? 1=Very unclear, 3=Acceptable, 5=Crystal clear")
    accuracy_score: int = dspy.OutputField(desc="1-5: Is the question factually and grammatically correct? 1=Major errors, 3=Acceptable, 5=Perfectly correct")
    difficulty_match: int = dspy.OutputField(desc="1-5: Does difficulty match the intended level? 1=Completely mismatched, 3=Roughly aligned, 5=Perfect match")
    distractor_quality: int = dspy.OutputField(desc="1-5: Are wrong options plausible but clearly wrong? 1=All trivially obvious, 3=Acceptable, 5=Excellent. Rate 5 if not MC.")
    overall_score: int = dspy.OutputField(desc="1-5: Overall quality. 1=Reject, 2=Below average, 3=Acceptable, 4=Good, 5=Excellent")
    verdict: str = dspy.OutputField(desc="PASS if overall_score >= 3 and no individual score is 1, else FAIL")


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


def get_fallback_lm() -> dspy.LM:
    """Fallback model used when primary generation pipeline fails.
    Typically a different provider to avoid correlated outages."""
    return dspy.LM(
        model=settings.fallback_model,
        temperature=0.3,
        max_tokens=4000,
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

    def forward(self, question_text, choices, correct_answer, passage, grade_level, difficulty):
        return self.score(
            question_text=question_text,
            choices=choices,
            correct_answer=correct_answer,
            passage=passage,
            grade_level=grade_level,
            difficulty=difficulty,
        )


def _choices_to_str(choices: list[ChoiceItemOutput] | None) -> str:
    """Convert choices list to JSON string for verifier/scorer input."""
    if not choices:
        return "null"
    return json.dumps([c.model_dump() for c in choices], ensure_ascii=False)


class ExamPipeline(dspy.Module):
    """Full pipeline: Generate (GPT-5.2) → Verify (Claude 4.6) → Score (Claude 4.6).

    Uses dspy.Refine for generation: generates up to N candidates with
    feedback-based refinement. Each candidate is evaluated by a reward function
    that scores quality. Failed attempts feed back context to improve subsequent
    generations.

    Error handling strategy:
    1. dspy.Refine handles retry with feedback on format/quality issues
    2. Fallback model used when primary generation pipeline fails entirely
    3. Verification and scoring failures are logged and flagged (never silently ignored)
    """

    def __init__(self, best_of_n: int = 3, quality_threshold: int = 3):
        super().__init__()
        self.generator = QuestionGeneratorModule()
        self.verifier = AnswerVerifierModule()
        self.scorer = QuestionScorerModule()
        self.best_of_n = best_of_n
        self.quality_threshold = quality_threshold
        self.refine = dspy.Refine(
            module=self.generator,
            N=best_of_n,
            reward_fn=self._quality_reward,
            threshold=quality_threshold / 5.0,
            fail_count=2,
        )

    def _quality_reward(self, example, prediction, trace=None):
        """Reward function for dspy.Refine — evaluates each candidate's quality.

        Called by Refine after each generation attempt. Returns a float 0.0-1.0.
        If the reward exceeds the threshold, the candidate is accepted immediately.
        Otherwise, Refine retries with feedback about why the candidate failed.

        Includes both verification and scoring so that wrong-answer candidates
        are penalized and Refine retries with feedback rather than accepting them.
        """
        result = prediction.result
        if not result or not result.question_text or not result.correct_answer:
            return 0.0

        try:
            choices_str = _choices_to_str(result.choices)
            eval_lm = get_evaluation_lm()

            with dspy.context(lm=eval_lm):
                # Verify answer correctness first
                verify_result = self.verifier(
                    question_text=result.question_text,
                    choices=choices_str,
                    passage=result.passage,
                    provided_answer=result.correct_answer,
                )
                if not verify_result.is_correct:
                    logger.info(
                        "Reward: answer incorrect ('%s' -> '%s'), penalizing candidate",
                        result.correct_answer,
                        verify_result.correct_answer,
                    )
                    return 0.1  # Heavily penalize wrong answers

                # Score quality
                score_result = self.scorer(
                    question_text=result.question_text,
                    choices=choices_str,
                    correct_answer=result.correct_answer,
                    passage=result.passage,
                    grade_level=str(getattr(example, "grade_level", "")),
                    difficulty=int(getattr(example, "difficulty", 3)),
                )
                return int(score_result.overall_score) / 5.0
        except Exception as e:
            logger.warning("Reward evaluation failed: %s", e)
            return 0.0  # Force retry on evaluation failure

    def forward(self, grade_level, question_type, topic, difficulty, grade_description, type_instruction):
        gen_lm = get_generation_lm()

        # Phase 1: Generate with dspy.Refine (feedback-based refinement)
        # Refine's reward function scores candidates for selection, but the
        # final verification + answer correction happens in Phase 2 below.
        gen_result = None
        used_fallback = False
        try:
            with dspy.context(lm=gen_lm):
                gen_result = self.refine(
                    grade_level=grade_level,
                    question_type=question_type,
                    topic=topic,
                    difficulty=difficulty,
                    grade_description=grade_description,
                    type_instruction=type_instruction,
                )
        except Exception as e:
            logger.error("Primary generation pipeline failed: %s", e)
            # Fallback to single attempt with fallback model (no Refine)
            try:
                with dspy.context(lm=get_fallback_lm()):
                    gen_result = self.generator(
                        grade_level=grade_level,
                        question_type=question_type,
                        topic=topic,
                        difficulty=difficulty,
                        grade_description=grade_description,
                        type_instruction=type_instruction,
                    )
                    used_fallback = True
            except Exception as fallback_err:
                logger.error("Fallback generation also failed: %s", fallback_err)
                return dspy.Prediction(best_question=None, score=0, verified=False)

        question = gen_result.result  # ExamQuestionOutput
        if not question or not question.question_text:
            return dspy.Prediction(best_question=None, score=0, verified=False)

        # Phase 2: Verify + score for ALL paths
        # Even the Refine path needs final verification because Refine may
        # return a low-reward candidate (e.g. wrong answer) when all attempts
        # fail to meet the threshold. The reward function penalizes but does
        # not correct answers, so we must do that here.
        verified = False
        overall = self.quality_threshold

        eval_lm = get_evaluation_lm()
        choices_str = _choices_to_str(question.choices)

        try:
            with dspy.context(lm=eval_lm):
                verify_result = self.verifier(
                    question_text=question.question_text,
                    choices=choices_str,
                    passage=question.passage,
                    provided_answer=question.correct_answer,
                )
                if not verify_result.is_correct:
                    logger.info(
                        "Answer corrected: '%s' -> '%s'",
                        question.correct_answer,
                        verify_result.correct_answer,
                    )
                    question = question.model_copy(
                        update={
                            "correct_answer": verify_result.correct_answer,
                            "explanation": verify_result.reasoning,
                        }
                    )
                verified = True
        except Exception as e:
            logger.warning("Answer verification failed: %s", e)

        try:
            choices_str = _choices_to_str(question.choices)
            with dspy.context(lm=eval_lm):
                score_result = self.scorer(
                    question_text=question.question_text,
                    choices=choices_str,
                    correct_answer=question.correct_answer,
                    passage=question.passage,
                    grade_level=grade_level,
                    difficulty=difficulty,
                )
                overall = int(score_result.overall_score)
        except Exception as e:
            logger.warning("Quality scoring failed: %s", e)

        return dspy.Prediction(
            best_question=question,
            score=overall,
            verified=verified,
        )


# ---------------------------------------------------------------------------
# MIPROv2 Metric & Optimizer Setup
# ---------------------------------------------------------------------------

def question_quality_metric(example, prediction, trace=None):
    """Metric for MIPROv2/GEPA optimization.
    Returns a dict with 'score' (0.0-1.0) and 'feedback' string.
    MIPROv2 reads the 'score' key; GEPA also uses 'feedback' for reflective optimization.
    """
    question = prediction.best_question
    if not question:
        return {"score": 0.0, "feedback": "No question generated"}

    if not isinstance(question, ExamQuestionOutput):
        return {"score": 0.0, "feedback": f"Unexpected output type: {type(question).__name__}"}

    question_text = question.question_text
    correct_answer = question.correct_answer
    explanation = question.explanation

    score = 0.0
    issues = []

    # Has required fields
    if question_text and correct_answer:
        score += 0.3
    else:
        issues.append("Missing required fields (question_text or correct_answer)")

    # Has explanation
    if explanation:
        score += 0.1
    else:
        issues.append("Missing explanation field")

    # Quality score from pipeline (1-5 scale)
    pipeline_score = prediction.score or 0
    score += (pipeline_score / 5.0) * 0.6

    final_score = min(score, 1.0)
    feedback = "; ".join(issues) if issues else "Question meets quality standards"
    return {"score": final_score, "feedback": feedback}


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
