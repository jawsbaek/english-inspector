import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class GradeLevel(StrEnum):
    PHONICS = "phonics"
    ELEMENTARY_LOW = "elementary_low"  # 초등 1-2
    ELEMENTARY_MID = "elementary_mid"  # 초등 3-4
    ELEMENTARY_HIGH = "elementary_high"  # 초등 5-6
    MIDDLE = "middle"  # 중등
    HIGH = "high"  # 고등


class QuestionType(StrEnum):
    MULTIPLE_CHOICE = "multiple_choice"
    FILL_IN_BLANK = "fill_in_blank"
    READING_COMPREHENSION = "reading_comprehension"
    GRAMMAR = "grammar"
    VOCABULARY = "vocabulary"
    SHORT_ANSWER = "short_answer"


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    grade_level: Mapped[str] = mapped_column(Enum(GradeLevel), nullable=False)
    question_type: Mapped[str] = mapped_column(Enum(QuestionType), nullable=False)
    topic: Mapped[str] = mapped_column(String(200), nullable=False)
    difficulty: Mapped[int] = mapped_column(Integer, default=3)  # 1-5
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    choices: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string for MC
    correct_answer: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    passage: Mapped[str | None] = mapped_column(Text, nullable=True)  # For reading comprehension
    score: Mapped[float] = mapped_column(Float, default=0.0)  # Quality score
    validation_status: Mapped[str | None] = mapped_column(String(50), nullable=True)  # filter
    exam_set_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
