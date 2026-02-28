"""Quality filtering service for generated exam questions.

Components:
- DuplicateDetector: Jaccard similarity for near-duplicate detection
- FormatValidator: Structural validation per question type
- DifficultyCalibrator: Heuristic vocabulary/grammar complexity checks
- QualityFilter: Chains all components, returns filtered results with rejection reasons
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.models.question import QuestionType
from app.schemas.question import QuestionResponse


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    question: QuestionResponse
    passed: bool
    rejection_reasons: list[str] = field(default_factory=list)


@dataclass
class FilterReport:
    passed: list[ValidationResult]
    rejected: list[ValidationResult]

    @property
    def total(self) -> int:
        return len(self.passed) + len(self.rejected)

    @property
    def pass_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return len(self.passed) / self.total


# ---------------------------------------------------------------------------
# Duplicate Detector
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> set[str]:
    """Lowercase word-level tokenization."""
    return set(re.findall(r"\w+", text.lower()))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


class DuplicateDetector:
    """Detects near-duplicate questions using Jaccard similarity on word tokens.

    A question is considered a duplicate if its similarity to any previously
    seen question exceeds the threshold.
    """

    def __init__(self, threshold: float = 0.7) -> None:
        self.threshold = threshold
        self._seen: list[set[str]] = []

    def reset(self) -> None:
        self._seen.clear()

    def is_duplicate(self, question_text: str) -> bool:
        tokens = _tokenize(question_text)
        for seen_tokens in self._seen:
            if _jaccard(tokens, seen_tokens) >= self.threshold:
                return True
        self._seen.append(tokens)
        return False

    def check(self, question: QuestionResponse) -> list[str]:
        """Return list of rejection reasons (empty means passed)."""
        if self.is_duplicate(question.question_text):
            return ["Duplicate or near-duplicate question detected (Jaccard similarity >= threshold)"]
        return []


# ---------------------------------------------------------------------------
# Format Validator
# ---------------------------------------------------------------------------

# Expected choice labels for multiple-choice questions
_MC_LABELS = {"A", "B", "C", "D"}

# Question types that require exactly 4 choices
_CHOICE_TYPES = {
    QuestionType.MULTIPLE_CHOICE,
    QuestionType.READING_COMPREHENSION,
    QuestionType.GRAMMAR,
    QuestionType.VOCABULARY,
}

# Question types where choices must be None
_NO_CHOICE_TYPES = {
    QuestionType.FILL_IN_BLANK,
    QuestionType.SHORT_ANSWER,
}


class FormatValidator:
    """Validates structural constraints for each question type."""

    def check(self, question: QuestionResponse) -> list[str]:
        reasons: list[str] = []
        qtype = question.question_type

        # --- question_text must be non-empty ---
        if not question.question_text or not question.question_text.strip():
            reasons.append("question_text is empty")

        # --- correct_answer must be non-empty ---
        if not question.correct_answer or not question.correct_answer.strip():
            reasons.append("correct_answer is empty")

        # --- Choice-based types ---
        if qtype in _CHOICE_TYPES:
            if not question.choices:
                reasons.append(
                    f"{qtype.value} requires exactly 4 choices, but none provided"
                )
            else:
                labels = [c.label.strip().upper() for c in question.choices]
                if len(question.choices) != 4:
                    reasons.append(
                        f"{qtype.value} requires exactly 4 choices, got {len(question.choices)}"
                    )
                if set(labels) != _MC_LABELS:
                    reasons.append(
                        f"Choices must have labels A, B, C, D; got {sorted(labels)}"
                    )
                # correct_answer must match one of the choice labels
                if question.correct_answer.strip().upper() not in _MC_LABELS:
                    reasons.append(
                        f"correct_answer '{question.correct_answer}' is not a valid choice label (A/B/C/D)"
                    )
                elif question.correct_answer.strip().upper() not in {l.upper() for l in labels}:
                    reasons.append(
                        f"correct_answer '{question.correct_answer}' does not match any choice label"
                    )

        # --- Fill-in-blank ---
        if qtype == QuestionType.FILL_IN_BLANK:
            if question.choices is not None:
                reasons.append("fill_in_blank should not have choices")
            if "___" not in question.question_text:
                reasons.append("fill_in_blank question_text must contain '___' placeholder")

        # --- No-choice types ---
        if qtype in _NO_CHOICE_TYPES and question.choices is not None:
            reasons.append(f"{qtype.value} should not have choices")

        # --- Reading comprehension must have a passage ---
        if qtype == QuestionType.READING_COMPREHENSION:
            if not question.passage or not question.passage.strip():
                reasons.append("reading_comprehension requires a non-empty passage")

        return reasons


# ---------------------------------------------------------------------------
# Difficulty Calibrator
# ---------------------------------------------------------------------------

# (min_word_count, max_word_count, min_avg_word_len, max_avg_word_len)
_DIFFICULTY_THRESHOLDS: dict[int, dict[str, Any]] = {
    1: {"min_words": 3,  "max_words": 20,  "min_avg_len": 2.0, "max_avg_len": 5.5},
    2: {"min_words": 5,  "max_words": 30,  "min_avg_len": 3.0, "max_avg_len": 6.0},
    3: {"min_words": 8,  "max_words": 50,  "min_avg_len": 3.5, "max_avg_len": 7.0},
    4: {"min_words": 10, "max_words": 80,  "min_avg_len": 4.0, "max_avg_len": 8.5},
    5: {"min_words": 15, "max_words": 150, "min_avg_len": 4.5, "max_avg_len": 10.0},
}


def _text_stats(text: str) -> tuple[int, float, int]:
    """Return (word_count, avg_word_length, sentence_count)."""
    words = re.findall(r"\b[a-zA-Z]+\b", text)
    word_count = len(words)
    avg_len = sum(len(w) for w in words) / max(word_count, 1)
    sentences = len(re.findall(r"[.!?]+", text)) or 1
    return word_count, avg_len, sentences


class DifficultyCalibrator:
    """Checks whether question complexity roughly matches the declared difficulty.

    Uses word count and average word length as lightweight proxies for
    vocabulary and grammar complexity.
    """

    def check(self, question: QuestionResponse) -> list[str]:
        difficulty = question.difficulty
        if difficulty not in _DIFFICULTY_THRESHOLDS:
            return [f"Unknown difficulty level: {difficulty}"]

        thresholds = _DIFFICULTY_THRESHOLDS[difficulty]

        # Use question_text (plus passage if present) as the text to evaluate
        text = question.question_text
        if question.passage:
            text = question.passage + " " + text

        word_count, avg_len, _ = _text_stats(text)

        reasons: list[str] = []

        if word_count < thresholds["min_words"]:
            reasons.append(
                f"Text too short for difficulty {difficulty}: "
                f"{word_count} words (minimum {thresholds['min_words']})"
            )
        if word_count > thresholds["max_words"]:
            reasons.append(
                f"Text too long for difficulty {difficulty}: "
                f"{word_count} words (maximum {thresholds['max_words']})"
            )
        if avg_len < thresholds["min_avg_len"]:
            reasons.append(
                f"Vocabulary too simple for difficulty {difficulty}: "
                f"avg word length {avg_len:.1f} (minimum {thresholds['min_avg_len']})"
            )
        if avg_len > thresholds["max_avg_len"]:
            reasons.append(
                f"Vocabulary too complex for difficulty {difficulty}: "
                f"avg word length {avg_len:.1f} (maximum {thresholds['max_avg_len']})"
            )

        return reasons


# ---------------------------------------------------------------------------
# QualityFilter — chains all components
# ---------------------------------------------------------------------------


class QualityFilter:
    """Chains DuplicateDetector, FormatValidator, and DifficultyCalibrator.

    Usage:
        qf = QualityFilter()
        report = qf.filter(questions)
        # report.passed  -> list[ValidationResult] that passed all checks
        # report.rejected -> list[ValidationResult] with rejection_reasons
    """

    def __init__(
        self,
        duplicate_threshold: float = 0.7,
        check_duplicates: bool = True,
        check_format: bool = True,
        check_difficulty: bool = True,
    ) -> None:
        self.duplicate_detector = DuplicateDetector(threshold=duplicate_threshold)
        self.format_validator = FormatValidator()
        self.difficulty_calibrator = DifficultyCalibrator()
        self.check_duplicates = check_duplicates
        self.check_format = check_format
        self.check_difficulty = check_difficulty

    def validate_one(self, question: QuestionResponse) -> ValidationResult:
        """Validate a single question and return a ValidationResult."""
        reasons: list[str] = []

        if self.check_format:
            reasons.extend(self.format_validator.check(question))

        if self.check_difficulty:
            reasons.extend(self.difficulty_calibrator.check(question))

        # Duplicate check is stateful — run last so rejected questions
        # are not added to the seen-set.
        if self.check_duplicates and not reasons:
            reasons.extend(self.duplicate_detector.check(question))

        return ValidationResult(
            question=question,
            passed=len(reasons) == 0,
            rejection_reasons=reasons,
        )

    def filter(self, questions: list[QuestionResponse]) -> FilterReport:
        """Validate all questions and split into passed / rejected."""
        # Reset duplicate state for each batch so cross-batch comparisons
        # do not accumulate.
        self.duplicate_detector.reset()

        passed: list[ValidationResult] = []
        rejected: list[ValidationResult] = []

        for q in questions:
            result = self.validate_one(q)
            if result.passed:
                passed.append(result)
            else:
                rejected.append(result)

        return FilterReport(passed=passed, rejected=rejected)
