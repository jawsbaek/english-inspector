from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.user import ExamSet, User

router = APIRouter(prefix="/api/exams", tags=["exams"])


class ExamSetCreate(BaseModel):
    title: str
    grade_level: str
    question_count: int = 0


class ExamSetResponse(BaseModel):
    id: int
    title: str
    grade_level: str
    question_count: int
    user_id: int

    model_config = {"from_attributes": True}


@router.get("", response_model=list[ExamSetResponse])
async def list_exams(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ExamSet)
        .where(ExamSet.user_id == current_user.id)
        .order_by(ExamSet.created_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=ExamSetResponse, status_code=status.HTTP_201_CREATED)
async def create_exam(
    req: ExamSetCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    exam_set = ExamSet(
        title=req.title,
        grade_level=req.grade_level,
        question_count=req.question_count,
        user_id=current_user.id,
    )
    db.add(exam_set)
    await db.commit()
    await db.refresh(exam_set)
    return exam_set


@router.get("/{exam_id}", response_model=ExamSetResponse)
async def get_exam(
    exam_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ExamSet).where(ExamSet.id == exam_id))
    exam_set = result.scalar_one_or_none()
    if not exam_set:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam set not found")
    if exam_set.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return exam_set


@router.delete("/{exam_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exam(
    exam_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ExamSet).where(ExamSet.id == exam_id))
    exam_set = result.scalar_one_or_none()
    if not exam_set:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam set not found")
    if exam_set.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    await db.delete(exam_set)
    await db.commit()
