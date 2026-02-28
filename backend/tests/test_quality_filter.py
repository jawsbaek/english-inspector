"""Unit tests for quality_filter.py — no LLM required."""

from __future__ import annotations

import pytest

from app.models.question import GradeLevel, QuestionType
from app.schemas.question import ChoiceItem, QuestionResponse
from app.services.quality_filter import (
    DifficultyCalibrator,
    DuplicateDetector,
    FilterReport,
    FormatValidator,
    QualityFilter,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MC_CHOICES = [
    ChoiceItem(label="A", text="option a"),
    ChoiceItem(label="B", text="option b"),
    ChoiceItem(label="C", text="option c"),
    ChoiceItem(label="D", text="option d"),
]


def _mc_question(
    text: str = "What is the capital of France? The country is in Europe.",
    difficulty: int = 3,
    correct_answer: str = "A",
) -> QuestionResponse:
    return QuestionResponse(
        grade_level=GradeLevel.MIDDLE,
        question_type=QuestionType.MULTIPLE_CHOICE,
        topic="geography",
        difficulty=difficulty,
        question_text=text,
        choices=_MC_CHOICES,
        correct_answer=correct_answer,
    )


def _fill_question(
    text: str = "The cat sat on the ___ mat carefully placed there.",
    difficulty: int = 2,
) -> QuestionResponse:
    return QuestionResponse(
        grade_level=GradeLevel.ELEMENTARY_MID,
        question_type=QuestionType.FILL_IN_BLANK,
        topic="grammar",
        difficulty=difficulty,
        question_text=text,
        choices=None,
        correct_answer="big",
    )


# ---------------------------------------------------------------------------
# DuplicateDetector
# ---------------------------------------------------------------------------


class TestDuplicateDetector:
    def test_same_text_is_duplicate(self):
        det = DuplicateDetector(threshold=0.7)
        q = _mc_question("What is the color of the sky on a clear day?")
        assert not det.is_duplicate(q.question_text)  # first — not duplicate
        assert det.is_duplicate(q.question_text)  # second — duplicate

    def test_different_text_not_duplicate(self):
        det = DuplicateDetector(threshold=0.7)
        det.is_duplicate("The quick brown fox jumps over the lazy dog.")
        assert not det.is_duplicate("She sells seashells by the seashore every morning.")

    def test_threshold_edge_below_not_duplicate(self):
        """Two very different questions should not be flagged."""
        det = DuplicateDetector(threshold=0.7)
        det.is_duplicate("apple banana cherry delicious fruit")
        # Completely different words → Jaccard ≈ 0
        assert not det.is_duplicate("elephant giraffe zebra safari jungle")

    def test_threshold_edge_above_is_duplicate(self):
        """Near-identical sentences exceed the threshold."""
        det = DuplicateDetector(threshold=0.7)
        base = "What is the correct answer to this grammar question here"
        det.is_duplicate(base)
        near = "What is the correct answer to this grammar question now"
        assert det.is_duplicate(near)

    def test_reset_clears_seen_list(self):
        det = DuplicateDetector(threshold=0.7)
        text = "unique repeated sentence about English grammar"
        det.is_duplicate(text)
        det.reset()
        assert not det.is_duplicate(text)  # after reset, not duplicate

    def test_check_returns_empty_on_first_occurrence(self):
        det = DuplicateDetector()
        q = _mc_question("The teacher wrote on the blackboard with chalk today.")
        assert det.check(q) == []

    def test_check_returns_reason_on_second_occurrence(self):
        det = DuplicateDetector()
        q = _mc_question("The teacher wrote on the blackboard with chalk today.")
        det.check(q)
        reasons = det.check(q)
        assert len(reasons) == 1
        assert "Duplicate" in reasons[0]


# ---------------------------------------------------------------------------
# FormatValidator
# ---------------------------------------------------------------------------


class TestFormatValidator:
    def setup_method(self):
        self.val = FormatValidator()

    def test_valid_mc_question_passes(self):
        assert self.val.check(_mc_question()) == []

    def test_mc_missing_choices_fails(self):
        q = _mc_question()
        q.choices = None
        reasons = self.val.check(q)
        assert any("4 choices" in r for r in reasons)

    def test_mc_wrong_number_of_choices_fails(self):
        q = _mc_question()
        q.choices = _MC_CHOICES[:2]  # only 2
        reasons = self.val.check(q)
        assert any("4 choices" in r for r in reasons)

    def test_mc_wrong_labels_fails(self):
        q = _mc_question()
        q.choices = [
            ChoiceItem(label="A", text="a"),
            ChoiceItem(label="B", text="b"),
            ChoiceItem(label="C", text="c"),
            ChoiceItem(label="X", text="x"),  # wrong label
        ]
        reasons = self.val.check(q)
        assert any("A, B, C, D" in r for r in reasons)

    def test_fill_in_blank_without_placeholder_fails(self):
        q = _fill_question(text="The cat sat on the mat carefully.")  # no ___
        reasons = self.val.check(q)
        assert any("___" in r for r in reasons)

    def test_fill_in_blank_with_placeholder_passes(self):
        assert self.val.check(_fill_question()) == []

    def test_fill_in_blank_with_choices_fails(self):
        q = _fill_question()
        q.choices = _MC_CHOICES
        reasons = self.val.check(q)
        assert any("should not have choices" in r for r in reasons)

    def test_empty_question_text_fails(self):
        q = _mc_question(text="   ")
        reasons = self.val.check(q)
        assert any("empty" in r for r in reasons)

    def test_invalid_correct_answer_label_fails(self):
        q = _mc_question(correct_answer="Z")
        reasons = self.val.check(q)
        assert any("valid choice label" in r for r in reasons)

    def test_reading_comprehension_without_passage_fails(self):
        q = QuestionResponse(
            grade_level=GradeLevel.HIGH,
            question_type=QuestionType.READING_COMPREHENSION,
            topic="reading",
            difficulty=4,
            question_text="What is the main idea of the passage presented above?",
            choices=_MC_CHOICES,
            correct_answer="A",
            passage=None,
        )
        reasons = self.val.check(q)
        assert any("passage" in r for r in reasons)


# ---------------------------------------------------------------------------
# DifficultyCalibrator
# ---------------------------------------------------------------------------


class TestDifficultyCalibrator:
    def setup_method(self):
        self.cal = DifficultyCalibrator()

    def test_valid_difficulty3_question_passes(self):
        # difficulty=3: min_words=8, max_words=50
        q = _mc_question(
            text="What is the best way to improve your English vocabulary skills daily?",
            difficulty=3,
        )
        assert self.cal.check(q) == []

    def test_text_too_short_for_difficulty_fails(self):
        # difficulty=3 needs min_words=8; "Hi" is 1 word
        q = _mc_question(text="Hi there", difficulty=3)
        reasons = self.cal.check(q)
        assert any("too short" in r for r in reasons)

    def test_text_too_long_for_difficulty_fails(self):
        # difficulty=1 max_words=20; give it 30+ words
        long_text = " ".join(["word"] * 25)
        q = _mc_question(text=long_text, difficulty=1)
        reasons = self.cal.check(q)
        assert any("too long" in r for r in reasons)

    def test_unknown_difficulty_returns_reason(self):
        q = _mc_question(difficulty=99)
        reasons = self.cal.check(q)
        assert any("Unknown difficulty" in r for r in reasons)


# ---------------------------------------------------------------------------
# QualityFilter (end-to-end)
# ---------------------------------------------------------------------------


class TestQualityFilter:
    def test_all_valid_questions_pass(self):
        qf = QualityFilter()
        questions = [
            _mc_question(
                text="Students practice reading comprehension to improve their language skills every day.",
                difficulty=3,
            ),
            _mc_question(
                text="The teacher explains grammar rules to help children learn proper sentence formation.",
                difficulty=3,
            ),
            _mc_question(
                text="How can students improve their writing by studying examples of clear prose?",
                difficulty=3,
            ),
        ]
        report = qf.filter(questions)
        assert report.total == 3
        assert len(report.passed) == 3
        assert len(report.rejected) == 0
        assert report.pass_rate == 1.0

    def test_duplicate_is_rejected(self):
        qf = QualityFilter()
        q1 = _mc_question("What is the capital city of France located in Europe today?")
        q2 = _mc_question("What is the capital city of France located in Europe today?")
        report = qf.filter([q1, q2])
        assert len(report.passed) == 1
        assert len(report.rejected) == 1
        assert any("Duplicate" in r for r in report.rejected[0].rejection_reasons)

    def test_invalid_format_is_rejected(self):
        qf = QualityFilter()
        bad = _mc_question()
        bad.choices = None  # invalid: MC needs choices
        # 10 words, avg len ≈ 6.6 → passes difficulty=3 thresholds
        valid = _mc_question("How does practice help students understand complex grammar rules effectively?")
        report = qf.filter([bad, valid])
        assert len(report.rejected) == 1
        assert report.rejected[0].question == bad

    def test_mixed_batch_splits_correctly(self):
        qf = QualityFilter()
        valid = _mc_question("What is the proper use of present perfect tense in English?")
        invalid_format = _mc_question()
        invalid_format.choices = None
        duplicate1 = _mc_question("The same identical question text repeated verbatim here again now.")
        duplicate2 = _mc_question("The same identical question text repeated verbatim here again now.")
        report = qf.filter([valid, invalid_format, duplicate1, duplicate2])
        # valid → pass, invalid_format → reject, duplicate1 → pass, duplicate2 → reject
        assert len(report.passed) == 2
        assert len(report.rejected) == 2

    def test_pass_rate_calculation(self):
        qf = QualityFilter()
        q_bad = _mc_question()
        q_bad.choices = None
        q_good = _mc_question("What does the word 'ubiquitous' mean in modern English context?")
        report = qf.filter([q_bad, q_good])
        assert report.pass_rate == pytest.approx(0.5)

    def test_empty_batch_returns_zero_pass_rate(self):
        qf = QualityFilter()
        report = qf.filter([])
        assert report.total == 0
        assert report.pass_rate == 0.0
