"""Question generation service using DSPy 3.0+ pipeline.

Pipeline stages:
1. Load optimized pipeline (MIPROv2) if available, else use default
2. DSPy ExamPipeline (Generate → Verify → Score) with Best-of-N sampling
3. Multi-model routing: GPT-5.2 for generation, Claude 4.6 for evaluation
4. Results parsed and returned as QuestionResponse objects
"""

import asyncio
import json
import uuid
from functools import partial

import dspy

from app.core.config import settings
from app.models.question import GradeLevel, QuestionType
from app.schemas.question import ChoiceItem, QuestionResponse
from app.services.dspy_modules import ExamPipeline, get_generation_lm
from app.services.optimizer import load_optimized_pipeline

GRADE_DESCRIPTIONS = {
    GradeLevel.PHONICS: "파닉스 단계 (알파벳, 기본 발음 규칙, 간단한 단어)",
    GradeLevel.ELEMENTARY_LOW: "초등 1-2학년 (기초 인사, 색상, 숫자, 가족)",
    GradeLevel.ELEMENTARY_MID: "초등 3-4학년 (간단한 문장, 일상 대화, 현재시제)",
    GradeLevel.ELEMENTARY_HIGH: "초등 5-6학년 (문단 읽기, 과거시제, 비교급)",
    GradeLevel.MIDDLE: "중학교 (문법 체계, 독해, 작문 기초, 다양한 시제)",
    GradeLevel.HIGH: "고등학교 (수능 수준, 고급 독해, 복잡한 문법, 추론)",
}

QUESTION_TYPE_INSTRUCTIONS = {
    QuestionType.MULTIPLE_CHOICE: (
        'Generate a 4-choice multiple choice question. Output JSON with: '
        '"question_text", "choices" (array of {"label":"A/B/C/D","text":"..."}), '
        '"correct_answer" (label), "explanation" (Korean), "passage" (null unless reading).'
    ),
    QuestionType.FILL_IN_BLANK: (
        'Generate a fill-in-the-blank question. Output JSON with: '
        '"question_text" (sentence with ___ blank), "choices": null, '
        '"correct_answer" (the word/phrase), "explanation" (Korean), "passage": null.'
    ),
    QuestionType.READING_COMPREHENSION: (
        'Generate a reading comprehension question with passage. Output JSON with: '
        '"passage" (English text appropriate for grade), "question_text", '
        '"choices" (4 options), "correct_answer" (label), "explanation" (Korean).'
    ),
    QuestionType.GRAMMAR: (
        'Generate a grammar question. Output JSON with: '
        '"question_text", "choices" (4 options), "correct_answer" (label), '
        '"explanation" (Korean grammar rule), "passage": null.'
    ),
    QuestionType.VOCABULARY: (
        'Generate a vocabulary question. Output JSON with: '
        '"question_text", "choices" (4 options), "correct_answer" (label), '
        '"explanation" (Korean), "passage": null.'
    ),
    QuestionType.SHORT_ANSWER: (
        'Generate a short answer question. Output JSON with: '
        '"question_text", "choices": null, "correct_answer" (model answer), '
        '"explanation" (Korean), "passage": null.'
    ),
}


def _get_pipeline() -> ExamPipeline:
    """Load MIPROv2-optimized pipeline if available, else create default."""
    optimized = load_optimized_pipeline()
    if optimized:
        return optimized
    return ExamPipeline(best_of_n=settings.best_of_n)


def _generate_single_question(
    pipeline: ExamPipeline,
    grade_level: GradeLevel,
    question_type: QuestionType,
    topic: str,
    difficulty: int,
) -> QuestionResponse | None:
    """Generate and verify a single question through the DSPy pipeline."""
    grade_desc = GRADE_DESCRIPTIONS[grade_level]
    type_inst = QUESTION_TYPE_INSTRUCTIONS[question_type]

    result = pipeline(
        grade_level=grade_level.value,
        question_type=question_type.value,
        topic=topic,
        difficulty=difficulty,
        grade_description=grade_desc,
        type_instruction=type_inst,
    )

    if not result.best_question:
        return None

    try:
        q = json.loads(result.best_question)
    except (json.JSONDecodeError, TypeError):
        return None

    choices = None
    if q.get("choices") and isinstance(q["choices"], list):
        try:
            choices = [ChoiceItem(label=c["label"], text=c["text"]) for c in q["choices"]]
        except (KeyError, TypeError):
            choices = None

    return QuestionResponse(
        grade_level=grade_level,
        question_type=question_type,
        topic=topic,
        difficulty=difficulty,
        question_text=q.get("question_text", ""),
        choices=choices,
        correct_answer=q.get("correct_answer", ""),
        explanation=q.get("explanation"),
        passage=q.get("passage"),
    )


async def generate_questions(
    grade_level: GradeLevel,
    question_types: list[QuestionType],
    topic: str,
    count: int,
    difficulty: int,
) -> tuple[list[QuestionResponse], str]:
    """Generate exam questions using DSPy 3.0+ pipeline with Best-of-N sampling.

    Steps:
    1. Load MIPROv2-optimized pipeline if available
    2. Configure default DSPy LM for generation
    3. For each question type, run ExamPipeline concurrently
       (pipeline internally handles model switching: GPT-5.2 → Claude 4.6)
    4. Return verified, scored questions
    """
    exam_set_id = str(uuid.uuid4())[:8]

    # Set default LM for the session
    dspy.configure(lm=get_generation_lm())

    pipeline = _get_pipeline()

    per_type_count = max(1, count // len(question_types))
    remainder = count - per_type_count * len(question_types)

    all_questions: list[QuestionResponse] = []
    loop = asyncio.get_running_loop()

    for i, qtype in enumerate(question_types):
        n = per_type_count + (1 if i < remainder else 0)

        # Run generation concurrently in thread pool (DSPy is sync)
        tasks = [
            loop.run_in_executor(
                None,
                partial(
                    _generate_single_question,
                    pipeline, grade_level, qtype, topic, difficulty,
                ),
            )
            for _ in range(n)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, QuestionResponse):
                all_questions.append(result)

    return all_questions, exam_set_id
