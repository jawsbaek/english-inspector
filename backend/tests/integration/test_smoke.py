"""Smoke tests for the full LLM pipeline.

All tests are marked @pytest.mark.integration and skip gracefully when
OPENAI_API_KEY or ANTHROPIC_API_KEY are not set.

Run: uv run pytest tests/integration/test_smoke.py -v
"""

from __future__ import annotations

import json

import dspy
import pytest

from app.models.question import GradeLevel, QuestionType
from app.schemas.question import ChoiceItem, QuestionResponse
from app.services.dspy_modules import ExamQuestionOutput
from app.services.quality_filter import QualityFilter


class _SimpleConnectivity(dspy.Signature):
    """Reply with exactly one word."""

    prompt: str = dspy.InputField()
    reply: str = dspy.OutputField()


@pytest.mark.integration
def test_generation_lm_connection(require_api_keys, generation_lm):
    """GPT generation model is reachable and returns a non-empty response."""
    predictor = dspy.Predict(_SimpleConnectivity)
    with dspy.context(lm=generation_lm):
        result = predictor(prompt="Say 'ok'")
    assert result.reply is not None
    assert len(result.reply.strip()) > 0


@pytest.mark.integration
def test_evaluation_lm_connection(require_api_keys, evaluation_lm):
    """Claude evaluation model is reachable and returns a non-empty response."""
    predictor = dspy.Predict(_SimpleConnectivity)
    with dspy.context(lm=evaluation_lm):
        result = predictor(prompt="Say 'ok'")
    assert result.reply is not None
    assert len(result.reply.strip()) > 0


@pytest.mark.integration
def test_single_question_generation(require_api_keys, pipeline):
    """Pipeline generates a valid question via dspy.Refine with structured output."""
    from app.services.generator import GRADE_DESCRIPTIONS, QUESTION_TYPE_INSTRUCTIONS

    result = pipeline(
        grade_level=GradeLevel.MIDDLE.value,
        question_type=QuestionType.MULTIPLE_CHOICE.value,
        topic="daily_life",
        difficulty=3,
        grade_description=GRADE_DESCRIPTIONS[GradeLevel.MIDDLE],
        type_instruction=QUESTION_TYPE_INSTRUCTIONS[QuestionType.MULTIPLE_CHOICE],
    )

    assert result.best_question is not None, "Pipeline returned no question"
    question = result.best_question
    assert isinstance(question, ExamQuestionOutput), (
        f"Expected ExamQuestionOutput, got {type(question).__name__}"
    )
    assert question.question_text, "Generated question has no question_text"
    assert question.correct_answer, "Generated question has no correct_answer"


@pytest.mark.integration
def test_quality_filter_on_generated(require_api_keys, pipeline):
    """Quality filter processes a real generated question without crashing."""
    from app.services.generator import GRADE_DESCRIPTIONS, QUESTION_TYPE_INSTRUCTIONS

    result = pipeline(
        grade_level=GradeLevel.MIDDLE.value,
        question_type=QuestionType.MULTIPLE_CHOICE.value,
        topic="school",
        difficulty=3,
        grade_description=GRADE_DESCRIPTIONS[GradeLevel.MIDDLE],
        type_instruction=QUESTION_TYPE_INSTRUCTIONS[QuestionType.MULTIPLE_CHOICE],
    )

    assert result.best_question is not None, "Pipeline returned no question"
    question = result.best_question  # ExamQuestionOutput

    choices = None
    if question.choices:
        choices = [ChoiceItem(label=c.label, text=c.text) for c in question.choices]

    qr = QuestionResponse(
        grade_level=GradeLevel.MIDDLE,
        question_type=QuestionType.MULTIPLE_CHOICE,
        topic="school",
        difficulty=3,
        question_text=question.question_text,
        choices=choices,
        correct_answer=question.correct_answer,
        explanation=question.explanation,
        passage=question.passage,
    )

    qf = QualityFilter()
    report = qf.filter([qr])
    assert report.total == 1, "Quality filter should process exactly 1 question"


@pytest.mark.integration
def test_verification_catches_wrong_answer(require_api_keys, evaluation_lm):
    """Verifier correctly identifies an obviously wrong answer."""
    from app.services.dspy_modules import AnswerVerifierModule

    verifier = AnswerVerifierModule()
    with dspy.context(lm=evaluation_lm):
        result = verifier(
            question_text="What is the plural of 'child'?",
            choices=json.dumps([
                {"label": "A", "text": "childs"},
                {"label": "B", "text": "childes"},
                {"label": "C", "text": "children"},
                {"label": "D", "text": "child's"},
            ]),
            passage="none",
            provided_answer="A",  # Intentionally wrong; correct answer is C
        )
    assert result.is_correct is False, (
        "Verifier should detect that 'childs' is not the correct plural of 'child'"
    )
