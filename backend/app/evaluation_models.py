"""Append-only evaluation artifacts, separate from production complaints."""
import time
from uuid import uuid4
from sqlalchemy import String, Text, Float, JSON, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


class EvaluationCase(Base):
    __tablename__ = 'evaluation_cases'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(String(64), index=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    dataset: Mapped[str] = mapped_column(String(80), index=True)
    model: Mapped[str] = mapped_column(String(120), index=True)
    provider: Mapped[str] = mapped_column(String(80))
    question: Mapped[str] = mapped_column(Text)
    response: Mapped[str] = mapped_column(Text)
    reference: Mapped[str | None] = mapped_column(Text)
    context: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
    __table_args__ = (UniqueConstraint('workspace_id', 'fingerprint', name='uq_eval_case_fingerprint'),)


class Evaluation(Base):
    __tablename__ = 'evaluations'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    case_id: Mapped[str] = mapped_column(ForeignKey('evaluation_cases.id'), index=True)
    status: Mapped[str] = mapped_column(String(20))
    expires_at: Mapped[float | None] = mapped_column(Float)
    deterministic: Mapped[dict] = mapped_column(JSON)
    judged: Mapped[dict] = mapped_column(JSON)
    rubric: Mapped[dict] = mapped_column(JSON)
    evaluator: Mapped[dict] = mapped_column(JSON)
    error_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
    __table_args__ = (CheckConstraint("status IN ('running','completed','failed')", name='ck_evaluation_status'),)


class EvaluationReview(Base):
    __tablename__ = 'evaluation_reviews'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    evaluation_id: Mapped[str] = mapped_column(ForeignKey('evaluations.id'), index=True)
    reviewer_id: Mapped[str] = mapped_column(String(80))
    decision: Mapped[str] = mapped_column(String(20))
    feedback: Mapped[str] = mapped_column(Text)
    corrections: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
    __table_args__ = (CheckConstraint("decision IN ('approve','reject','correct')", name='ck_evaluation_review_decision'),)


class EvaluationComparison(Base):
    __tablename__ = 'evaluation_comparisons'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(String(64), index=True)
    snapshot: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
