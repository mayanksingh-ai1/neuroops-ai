"""Database constraints protect records even when writes bypass the API."""
from datetime import date, datetime
from sqlalchemy import CheckConstraint, Date, DateTime, String, Text, JSON, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


class Complaint(Base):
    __tablename__ = 'complaints'
    __table_args__ = (
        CheckConstraint("status IN ('open', 'in_progress', 'resolved')", name='ck_complaint_status'),
        CheckConstraint("priority IN ('low', 'medium', 'high')", name='ck_complaint_priority'),
    )

    complaint_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    category: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    priority: Mapped[str] = mapped_column(String(10))
    channel: Mapped[str] = mapped_column(String(40))
    received_date: Mapped[date] = mapped_column(Date, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ComplaintAnalysis(Base):
    """Append-only attempts; never replace imported complaint fields."""
    __tablename__ = 'complaint_analyses'

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    complaint_id: Mapped[str] = mapped_column(ForeignKey('complaints.complaint_id'), index=True)
    status: Mapped[str] = mapped_column(String(20))
    category: Mapped[str | None] = mapped_column(String(80))
    sentiment: Mapped[str | None] = mapped_column(String(10))
    priority: Mapped[str | None] = mapped_column(String(10))
    error_code: Mapped[str | None] = mapped_column(String(40))
    details: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
