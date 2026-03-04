"""Unit tests for dspy_modules.py — no LLM required (all calls mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import dspy
import pytest

from app.services.dspy_modules import (
    ChoiceItemOutput,
    ExamPipeline,
    ExamQuestionOutput,
    QuestionGeneratorModule,
    QuestionScorerModule,
    _choices_to_str,
    question_quality_metric,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sample_question(**overrides) -> ExamQuestionOutput:
    defaults = dict(
        question_text="What is the correct form of the verb?",
        choices=[
            ChoiceItemOutput(label="A", text="runs"),
            ChoiceItemOutput(label="B", text="running"),
            ChoiceItemOutput(label="C", text="run"),
            ChoiceItemOutput(label="D", text="ran"),
        ],
        correct_answer="D",
        explanation="과거형 'ran'이 정답입니다.",
        passage=None,
    )
    defaults.update(overrides)
    return ExamQuestionOutput(**defaults)


def _sample_prediction(question=None, score=4, verified=True):
    return dspy.Prediction(
        best_question=question or _sample_question(),
        score=score,
        verified=verified,
    )


# ---------------------------------------------------------------------------
# _choices_to_str
# ---------------------------------------------------------------------------


class TestChoicesToStr:
    def test_none_returns_null(self):
        assert _choices_to_str(None) == "null"

    def test_empty_list_returns_null(self):
        assert _choices_to_str([]) == "null"

    def test_valid_choices_returns_json(self):
        choices = [
            ChoiceItemOutput(label="A", text="hello"),
            ChoiceItemOutput(label="B", text="world"),
        ]
        result = _choices_to_str(choices)
        assert '"label": "A"' in result
        assert '"text": "hello"' in result


# ---------------------------------------------------------------------------
# ExamQuestionOutput
# ---------------------------------------------------------------------------


class TestExamQuestionOutput:
    def test_required_fields(self):
        q = ExamQuestionOutput(
            question_text="Test?",
            correct_answer="A",
        )
        assert q.question_text == "Test?"
        assert q.choices is None
        assert q.passage is None
        assert q.explanation == ""

    def test_with_choices(self):
        q = _sample_question()
        assert len(q.choices) == 4
        assert q.choices[0].label == "A"

    def test_model_copy_update(self):
        q = _sample_question()
        updated = q.model_copy(update={"correct_answer": "A"})
        assert updated.correct_answer == "A"
        assert updated.question_text == q.question_text


# ---------------------------------------------------------------------------
# question_quality_metric
# ---------------------------------------------------------------------------


class TestQuestionQualityMetric:
    def test_no_question_returns_zero(self):
        pred = dspy.Prediction(best_question=None, score=0, verified=False)
        result = question_quality_metric(None, pred)
        assert result["score"] == 0.0
        assert "No question" in result["feedback"]

    def test_unexpected_type_returns_zero(self):
        pred = dspy.Prediction(best_question="raw string", score=0, verified=False)
        result = question_quality_metric(None, pred)
        assert result["score"] == 0.0
        assert "Unexpected output type" in result["feedback"]

    def test_valid_question_with_high_score(self):
        pred = _sample_prediction(score=5)
        result = question_quality_metric(None, pred)
        # 0.3 (required fields) + 0.1 (explanation) + 0.6 * (5/5) = 1.0
        assert result["score"] == pytest.approx(1.0)
        assert "meets quality" in result["feedback"]

    def test_valid_question_with_low_score(self):
        pred = _sample_prediction(score=1)
        result = question_quality_metric(None, pred)
        # 0.3 + 0.1 + 0.6 * (1/5) = 0.52
        assert result["score"] == pytest.approx(0.52)

    def test_missing_explanation_deducts(self):
        q = _sample_question(explanation="")
        pred = _sample_prediction(question=q, score=5)
        result = question_quality_metric(None, pred)
        # 0.3 + 0.0 + 0.6 = 0.9
        assert result["score"] == pytest.approx(0.9)
        assert "Missing explanation" in result["feedback"]

    def test_missing_required_fields(self):
        q = _sample_question(question_text="", correct_answer="")
        pred = _sample_prediction(question=q, score=5)
        result = question_quality_metric(None, pred)
        # 0.0 + 0.1 + 0.6 = 0.7 (explanation present but required fields missing)
        assert result["score"] == pytest.approx(0.7)
        assert "Missing required" in result["feedback"]

    def test_zero_pipeline_score(self):
        pred = _sample_prediction(score=0)
        result = question_quality_metric(None, pred)
        # 0.3 + 0.1 + 0.0 = 0.4
        assert result["score"] == pytest.approx(0.4)


# ---------------------------------------------------------------------------
# ExamPipeline — unit tests (mocked LLM calls)
# ---------------------------------------------------------------------------


class TestExamPipelineInit:
    def test_default_init(self):
        pipeline = ExamPipeline()
        assert pipeline.best_of_n == 3
        assert pipeline.quality_threshold == 3

    def test_custom_init(self):
        pipeline = ExamPipeline(best_of_n=5, quality_threshold=4)
        assert pipeline.best_of_n == 5
        assert pipeline.quality_threshold == 4

    def test_refine_fail_count_is_two(self):
        pipeline = ExamPipeline()
        assert pipeline.refine.fail_count == 2

    def test_refine_threshold(self):
        pipeline = ExamPipeline(quality_threshold=4)
        assert pipeline.refine.threshold == pytest.approx(4 / 5.0)


class TestExamPipelineReward:
    def setup_method(self):
        self.pipeline = ExamPipeline(best_of_n=2, quality_threshold=3)

    def test_empty_result_returns_zero(self):
        pred = MagicMock()
        pred.result = None
        assert self.pipeline._quality_reward(MagicMock(), pred) == 0.0

    def test_missing_question_text_returns_zero(self):
        pred = MagicMock()
        pred.result = _sample_question(question_text="")
        assert self.pipeline._quality_reward(MagicMock(), pred) == 0.0

    def test_missing_correct_answer_returns_zero(self):
        pred = MagicMock()
        pred.result = _sample_question(correct_answer="")
        assert self.pipeline._quality_reward(MagicMock(), pred) == 0.0

    @patch("app.services.dspy_modules.get_evaluation_lm")
    def test_incorrect_answer_penalized(self, mock_get_lm):
        mock_get_lm.return_value = MagicMock()
        pred = MagicMock()
        pred.result = _sample_question()

        example = MagicMock()
        example.grade_level = "middle"
        example.difficulty = 3

        # Mock verifier to say answer is wrong
        mock_verify = MagicMock()
        mock_verify.is_correct = False
        mock_verify.correct_answer = "A"
        self.pipeline.verifier = MagicMock(return_value=mock_verify)

        with patch("dspy.context"):
            reward = self.pipeline._quality_reward(example, pred)

        assert reward == 0.1

    @patch("app.services.dspy_modules.get_evaluation_lm")
    def test_correct_answer_scored(self, mock_get_lm):
        mock_get_lm.return_value = MagicMock()
        pred = MagicMock()
        pred.result = _sample_question()

        example = MagicMock()
        example.grade_level = "middle"
        example.difficulty = 3

        # Mock verifier: correct answer
        mock_verify = MagicMock()
        mock_verify.is_correct = True
        self.pipeline.verifier = MagicMock(return_value=mock_verify)

        # Mock scorer: overall_score = 4
        mock_score = MagicMock()
        mock_score.overall_score = 4
        self.pipeline.scorer = MagicMock(return_value=mock_score)

        with patch("dspy.context"):
            reward = self.pipeline._quality_reward(example, pred)

        assert reward == pytest.approx(4 / 5.0)

    @patch("app.services.dspy_modules.get_evaluation_lm")
    def test_evaluation_exception_returns_zero(self, mock_get_lm):
        mock_get_lm.side_effect = RuntimeError("API error")
        pred = MagicMock()
        pred.result = _sample_question()
        example = MagicMock()

        reward = self.pipeline._quality_reward(example, pred)
        assert reward == 0.0


class TestExamPipelineForward:
    """Test forward method with mocked Refine and fallback paths."""

    def setup_method(self):
        self.pipeline = ExamPipeline(best_of_n=2, quality_threshold=3)
        self.kwargs = dict(
            grade_level="middle",
            question_type="multiple_choice",
            topic="grammar",
            difficulty=3,
            grade_description="중학교 수준",
            type_instruction="Generate a 4-choice MC question.",
        )

    @patch("app.services.dspy_modules.get_evaluation_lm")
    @patch("app.services.dspy_modules.get_generation_lm")
    def test_refine_success_path(self, mock_get_lm, mock_get_eval_lm):
        mock_get_lm.return_value = MagicMock()
        mock_get_eval_lm.return_value = MagicMock()
        question = _sample_question()

        mock_refine_result = MagicMock()
        mock_refine_result.result = question
        self.pipeline.refine = MagicMock(return_value=mock_refine_result)

        # Mock verifier: answer is correct
        mock_verify = MagicMock()
        mock_verify.is_correct = True
        self.pipeline.verifier = MagicMock(return_value=mock_verify)

        # Mock scorer: overall_score = 4
        mock_score = MagicMock()
        mock_score.overall_score = 4
        self.pipeline.scorer = MagicMock(return_value=mock_score)

        with patch("dspy.context"):
            result = self.pipeline.forward(**self.kwargs)

        assert result.best_question == question
        assert result.verified is True
        assert result.score == 4

    @patch("app.services.dspy_modules.get_generation_lm")
    def test_refine_returns_no_question(self, mock_get_lm):
        mock_get_lm.return_value = MagicMock()

        mock_refine_result = MagicMock()
        mock_refine_result.result = None
        self.pipeline.refine = MagicMock(return_value=mock_refine_result)

        with patch("dspy.context"):
            result = self.pipeline.forward(**self.kwargs)

        assert result.best_question is None
        assert result.score == 0

    @patch("app.services.dspy_modules.get_fallback_lm")
    @patch("app.services.dspy_modules.get_evaluation_lm")
    @patch("app.services.dspy_modules.get_generation_lm")
    def test_fallback_path_on_refine_failure(self, mock_gen_lm, mock_eval_lm, mock_fallback_lm):
        mock_gen_lm.return_value = MagicMock()
        mock_eval_lm.return_value = MagicMock()
        mock_fallback_lm.return_value = MagicMock()

        # Refine raises
        self.pipeline.refine = MagicMock(side_effect=RuntimeError("Refine failed"))

        # Fallback generator returns valid question
        question = _sample_question()
        mock_gen_result = MagicMock()
        mock_gen_result.result = question
        self.pipeline.generator = MagicMock(return_value=mock_gen_result)

        # Mock verifier for fallback path
        mock_verify = MagicMock()
        mock_verify.is_correct = True
        self.pipeline.verifier = MagicMock(return_value=mock_verify)

        # Mock scorer for fallback path
        mock_score = MagicMock()
        mock_score.overall_score = 4
        self.pipeline.scorer = MagicMock(return_value=mock_score)

        with patch("dspy.context"):
            result = self.pipeline.forward(**self.kwargs)

        assert result.best_question == question
        assert result.verified is True
        assert result.score == 4

    @patch("app.services.dspy_modules.get_fallback_lm")
    @patch("app.services.dspy_modules.get_generation_lm")
    def test_both_paths_fail_returns_none(self, mock_gen_lm, mock_fallback_lm):
        mock_gen_lm.return_value = MagicMock()
        mock_fallback_lm.return_value = MagicMock()

        self.pipeline.refine = MagicMock(side_effect=RuntimeError("Refine failed"))
        self.pipeline.generator = MagicMock(side_effect=RuntimeError("Fallback failed"))

        with patch("dspy.context"):
            result = self.pipeline.forward(**self.kwargs)

        assert result.best_question is None
        assert result.score == 0
        assert result.verified is False

    @patch("app.services.dspy_modules.get_fallback_lm")
    @patch("app.services.dspy_modules.get_evaluation_lm")
    @patch("app.services.dspy_modules.get_generation_lm")
    def test_fallback_verifier_corrects_answer(self, mock_gen_lm, mock_eval_lm, mock_fallback_lm):
        mock_gen_lm.return_value = MagicMock()
        mock_eval_lm.return_value = MagicMock()
        mock_fallback_lm.return_value = MagicMock()

        self.pipeline.refine = MagicMock(side_effect=RuntimeError("Refine failed"))

        question = _sample_question(correct_answer="B")
        mock_gen_result = MagicMock()
        mock_gen_result.result = question
        self.pipeline.generator = MagicMock(return_value=mock_gen_result)

        # Verifier says B is wrong, D is correct
        mock_verify = MagicMock()
        mock_verify.is_correct = False
        mock_verify.correct_answer = "D"
        mock_verify.reasoning = "D는 과거형이 맞습니다."
        self.pipeline.verifier = MagicMock(return_value=mock_verify)

        mock_score = MagicMock()
        mock_score.overall_score = 3
        self.pipeline.scorer = MagicMock(return_value=mock_score)

        with patch("dspy.context"):
            result = self.pipeline.forward(**self.kwargs)

        assert result.best_question.correct_answer == "D"
        assert result.best_question.explanation == "D는 과거형이 맞습니다."
        assert result.verified is True
