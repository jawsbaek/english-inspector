from pydantic import BaseModel, Field

from app.models.question import GradeLevel, QuestionType


class GenerateRequest(BaseModel):
    grade_level: GradeLevel
    question_types: list[QuestionType] = [QuestionType.MULTIPLE_CHOICE]
    topic: str = "general"
    count: int = Field(default=5, ge=1, le=30)
    difficulty: int = Field(default=3, ge=1, le=5)


class ChoiceItem(BaseModel):
    label: str  # "A", "B", "C", "D"
    text: str


class QuestionResponse(BaseModel):
    id: int | None = None
    grade_level: GradeLevel
    question_type: QuestionType
    topic: str
    difficulty: int
    question_text: str
    choices: list[ChoiceItem] | None = None
    correct_answer: str
    explanation: str | None = None
    passage: str | None = None

    model_config = {"from_attributes": True}


class GenerateResponse(BaseModel):
    questions: list[QuestionResponse]
    exam_set_id: str


class ExamExportRequest(BaseModel):
    title: str = "영어 시험"
    school_name: str = ""
    date: str = ""
    question_ids: list[int] = []
    exam_set_id: str | None = None
