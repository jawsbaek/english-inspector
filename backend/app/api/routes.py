import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.question import Question
from app.schemas.question import GenerateRequest, GenerateResponse, QuestionResponse
from app.services.generator import generate_questions
from app.services.quality_filter import QualityFilter

router = APIRouter(prefix="/api", tags=["questions"])


@router.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest, db: AsyncSession = Depends(get_db)):
    try:
        questions, exam_set_id = await generate_questions(
            grade_level=req.grade_level,
            question_types=req.question_types,
            topic=req.topic,
            count=req.count,
            difficulty=req.difficulty,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {e}") from e

    # Auto-filter generated questions
    quality_filter = QualityFilter()
    report = quality_filter.filter(questions)

    # Save to database (all questions, with validation_status recorded)
    saved_questions = []
    all_results = report.passed + report.rejected
    for vr in all_results:
        q = vr.question
        validation_status = "passed" if vr.passed else "rejected"
        db_question = Question(
            grade_level=q.grade_level,
            question_type=q.question_type,
            topic=q.topic,
            difficulty=q.difficulty,
            question_text=q.question_text,
            choices=json.dumps([c.model_dump() for c in q.choices], ensure_ascii=False)
            if q.choices
            else None,
            correct_answer=q.correct_answer,
            explanation=q.explanation,
            passage=q.passage,
            exam_set_id=exam_set_id,
            validation_status=validation_status,
        )
        db.add(db_question)
        await db.flush()

        q.id = db_question.id
        if vr.passed:
            saved_questions.append(q)

    await db.commit()
    # Return only questions that passed quality filtering
    return GenerateResponse(questions=saved_questions, exam_set_id=exam_set_id)


# ---------------------------------------------------------------------------
# Validation endpoint
# ---------------------------------------------------------------------------


class ValidateRequest(BaseModel):
    questions: list[QuestionResponse]
    duplicate_threshold: float = 0.7


class ValidationResultResponse(BaseModel):
    question: QuestionResponse
    passed: bool
    rejection_reasons: list[str]


class ValidateResponse(BaseModel):
    results: list[ValidationResultResponse]
    total: int
    passed_count: int
    rejected_count: int
    pass_rate: float


@router.post("/validate", response_model=ValidateResponse)
async def validate_questions(req: ValidateRequest) -> ValidateResponse:
    """Validate a list of questions through the quality filter pipeline.

    Returns per-question validation results with rejection reasons.
    Does not persist anything to the database.
    """
    quality_filter = QualityFilter(duplicate_threshold=req.duplicate_threshold)
    report = quality_filter.filter(req.questions)

    results: list[ValidationResultResponse] = []
    for vr in report.passed + report.rejected:
        results.append(
            ValidationResultResponse(
                question=vr.question,
                passed=vr.passed,
                rejection_reasons=vr.rejection_reasons,
            )
        )

    return ValidateResponse(
        results=results,
        total=report.total,
        passed_count=len(report.passed),
        rejected_count=len(report.rejected),
        pass_rate=report.pass_rate,
    )


@router.get("/questions", response_model=list[QuestionResponse])
async def list_questions(
    exam_set_id: str | None = None,
    grade_level: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Question).order_by(Question.created_at.desc()).limit(limit)
    if exam_set_id:
        stmt = stmt.where(Question.exam_set_id == exam_set_id)
    if grade_level:
        stmt = stmt.where(Question.grade_level == grade_level)

    result = await db.execute(stmt)
    rows = result.scalars().all()

    questions = []
    for row in rows:
        choices = None
        if row.choices:
            try:
                raw_choices = json.loads(row.choices)
                choices = [{"label": c["label"], "text": c["text"]} for c in raw_choices]
            except (json.JSONDecodeError, KeyError):
                choices = None

        questions.append(
            QuestionResponse(
                id=row.id,
                grade_level=row.grade_level,
                question_type=row.question_type,
                topic=row.topic,
                difficulty=row.difficulty,
                question_text=row.question_text,
                choices=choices,
                correct_answer=row.correct_answer,
                explanation=row.explanation,
                passage=row.passage,
            )
        )
    return questions


@router.get("/questions/{question_id}", response_model=QuestionResponse)
async def get_question(question_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Question).where(Question.id == question_id))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Question not found")

    choices = None
    if row.choices:
        try:
            choices = json.loads(row.choices)
        except json.JSONDecodeError:
            choices = None

    return QuestionResponse(
        id=row.id,
        grade_level=row.grade_level,
        question_type=row.question_type,
        topic=row.topic,
        difficulty=row.difficulty,
        question_text=row.question_text,
        choices=choices,
        correct_answer=row.correct_answer,
        explanation=row.explanation,
        passage=row.passage,
    )


@router.delete("/questions/{question_id}")
async def delete_question(question_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Question).where(Question.id == question_id))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Question not found")
    await db.delete(row)
    await db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# MIPROv2 Optimization Endpoints
# ---------------------------------------------------------------------------

class OptimizeRequest(BaseModel):
    num_trials: int = 15
    min_score: int = 7


@router.post("/optimize")
async def trigger_optimization(
    req: OptimizeRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Trigger MIPROv2 optimization using high-quality verified questions as training data."""
    from app.services.generator import GRADE_DESCRIPTIONS, QUESTION_TYPE_INSTRUCTIONS
    from app.services.optimizer import build_training_example, optimize_pipeline

    # Collect high-scoring questions as training examples
    stmt = select(Question).where(Question.score >= req.min_score).limit(50)
    result = await db.execute(stmt)
    rows = result.scalars().all()

    if len(rows) < 5:
        raise HTTPException(
            status_code=400,
            detail=f"Need at least 5 high-quality questions for optimization, found {len(rows)}",
        )

    trainset = []
    for row in rows:
        grade_desc = GRADE_DESCRIPTIONS.get(row.grade_level, "")
        type_inst = QUESTION_TYPE_INSTRUCTIONS.get(row.question_type, "")
        q_json = json.dumps({
            "question_text": row.question_text,
            "choices": json.loads(row.choices) if row.choices else None,
            "correct_answer": row.correct_answer,
            "explanation": row.explanation,
            "passage": row.passage,
        }, ensure_ascii=False)

        trainset.append(build_training_example(
            grade_level=row.grade_level,
            question_type=row.question_type,
            topic=row.topic,
            difficulty=row.difficulty,
            grade_description=grade_desc,
            type_instruction=type_inst,
            expected_question_json=q_json,
        ))

    def run_optimization():
        optimize_pipeline(
            trainset=trainset,
            num_trials=req.num_trials,
            save_path="optimized_models/exam_pipeline_optimized.json",
        )

    background_tasks.add_task(run_optimization)

    return {"status": "optimization_started", "training_examples": len(trainset)}
