"""MIPROv2 optimizer service for continuous prompt improvement.

Workflow:
1. Collect verified question examples (human-approved or high-scoring)
2. Build training set from examples
3. Run MIPROv2 to optimize ExamPipeline prompts
4. Save optimized module for future use
"""

import json
import os
from pathlib import Path

import dspy

from app.core.config import settings
from app.services.dspy_modules import (
    ExamPipeline,
    create_mipro_optimizer,
    get_generation_lm,
)

OPTIMIZED_MODEL_DIR = Path(__file__).parent.parent.parent / "optimized_models"


def build_training_example(
    grade_level: str,
    question_type: str,
    topic: str,
    difficulty: int,
    grade_description: str,
    type_instruction: str,
    expected_question_json: str,
) -> dspy.Example:
    """Create a DSPy Example from a verified question for MIPROv2 training."""
    return dspy.Example(
        grade_level=grade_level,
        question_type=question_type,
        topic=topic,
        difficulty=difficulty,
        grade_description=grade_description,
        type_instruction=type_instruction,
        best_question=expected_question_json,
        score=9,
        verified=True,
    ).with_inputs(
        "grade_level", "question_type", "topic", "difficulty",
        "grade_description", "type_instruction",
    )


def optimize_pipeline(
    trainset: list[dspy.Example],
    num_trials: int = 15,
    save_path: str | None = None,
) -> ExamPipeline:
    """Run MIPROv2 optimization on the ExamPipeline.

    Args:
        trainset: List of verified training examples
        num_trials: Number of optimization trials
        save_path: Where to save the optimized model

    Returns:
        Optimized ExamPipeline module
    """
    dspy.configure(lm=get_generation_lm())

    student = ExamPipeline(best_of_n=settings.best_of_n)
    optimizer = create_mipro_optimizer()

    optimized = optimizer.compile(
        student=student,
        trainset=trainset,
        num_trials=num_trials,
    )

    if save_path:
        os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
        optimized.save(save_path)

    return optimized


def load_optimized_pipeline(path: str | None = None) -> ExamPipeline | None:
    """Load a previously optimized pipeline if available."""
    if path is None:
        path = str(OPTIMIZED_MODEL_DIR / "exam_pipeline_optimized.json")

    if not os.path.exists(path):
        return None

    pipeline = ExamPipeline(best_of_n=settings.best_of_n)
    try:
        pipeline.load(path)
        return pipeline
    except Exception:
        return None
