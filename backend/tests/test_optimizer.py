"""Unit tests for optimizer.py — no LLM required."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import dspy
import pytest

from app.services.dspy_modules import ChoiceItemOutput, ExamQuestionOutput
from app.services.optimizer import build_training_example, load_optimized_pipeline


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sample_question() -> ExamQuestionOutput:
    return ExamQuestionOutput(
        question_text="Which word is the past tense of 'go'?",
        choices=[
            ChoiceItemOutput(label="A", text="goes"),
            ChoiceItemOutput(label="B", text="gone"),
            ChoiceItemOutput(label="C", text="went"),
            ChoiceItemOutput(label="D", text="going"),
        ],
        correct_answer="C",
        explanation="'went'는 'go'의 과거형입니다.",
        passage=None,
    )


# ---------------------------------------------------------------------------
# build_training_example
# ---------------------------------------------------------------------------


class TestBuildTrainingExample:
    def test_returns_dspy_example(self):
        example = build_training_example(
            grade_level="middle",
            question_type="multiple_choice",
            topic="grammar",
            difficulty=3,
            grade_description="중학교 수준",
            type_instruction="Generate a 4-choice MC question.",
            expected_question=_sample_question(),
        )
        assert isinstance(example, dspy.Example)

    def test_input_fields_set_correctly(self):
        example = build_training_example(
            grade_level="high",
            question_type="vocabulary",
            topic="science",
            difficulty=4,
            grade_description="고등학교 수준",
            type_instruction="Generate a vocabulary question.",
            expected_question=_sample_question(),
        )
        assert example.grade_level == "high"
        assert example.question_type == "vocabulary"
        assert example.topic == "science"
        assert example.difficulty == 4

    def test_output_fields_set_correctly(self):
        q = _sample_question()
        example = build_training_example(
            grade_level="middle",
            question_type="multiple_choice",
            topic="grammar",
            difficulty=3,
            grade_description="중학교 수준",
            type_instruction="Generate a MC question.",
            expected_question=q,
        )
        assert example.best_question is q
        assert example.score == 5
        assert example.verified is True

    def test_input_keys_marked(self):
        example = build_training_example(
            grade_level="middle",
            question_type="grammar",
            topic="verbs",
            difficulty=2,
            grade_description="desc",
            type_instruction="inst",
            expected_question=_sample_question(),
        )
        input_keys = example.inputs().keys()
        assert "grade_level" in input_keys
        assert "question_type" in input_keys
        assert "topic" in input_keys
        assert "difficulty" in input_keys
        assert "grade_description" in input_keys
        assert "type_instruction" in input_keys
        # Output fields should not be in inputs
        assert "best_question" not in input_keys
        assert "score" not in input_keys


# ---------------------------------------------------------------------------
# load_optimized_pipeline
# ---------------------------------------------------------------------------


class TestLoadOptimizedPipeline:
    def test_returns_none_when_file_missing(self, tmp_path):
        result = load_optimized_pipeline(str(tmp_path / "nonexistent.json"))
        assert result is None

    def test_returns_none_on_corrupted_file(self, tmp_path):
        bad_file = tmp_path / "bad_model.json"
        bad_file.write_text("not valid json {{{")
        result = load_optimized_pipeline(str(bad_file))
        assert result is None

    def test_default_path_uses_optimized_model_dir(self):
        """When path is None, it uses the default OPTIMIZED_MODEL_DIR."""
        # The default path won't exist in test env, so should return None
        result = load_optimized_pipeline(None)
        assert result is None
