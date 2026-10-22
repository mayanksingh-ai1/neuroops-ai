"""Agent history is separate from customer records. No tool updates complaints."""
from uuid import uuid4
from sqlalchemy import String, Text, Float, Integer, JSON, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


class AgentRun(Base):
    __tablename__ = 'agent_runs'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(String(64), index=True)
    task: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default='queued')
    created_at: Mapped[float] = mapped_column(Float)
    expires_at: Mapped[float] = mapped_column(Float)
    error_code: Mapped[str | None] = mapped_column(String(80))
    result: Mapped[dict | None] = mapped_column(JSON)
    __table_args__ = (CheckConstraint("status IN ('queued','running','completed','failed','cancelled','timed_out')", name='ck_agent_run_status'),)


class AgentStep(Base):
    __tablename__ = 'agent_steps'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(ForeignKey('agent_runs.id'), index=True)
    position: Mapped[int] = mapped_column(Integer)
    tool: Mapped[str] = mapped_column(String(40))
    arguments: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default='pending')
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    output: Mapped[dict | None] = mapped_column(JSON)
    error_code: Mapped[str | None] = mapped_column(String(80))
    __table_args__ = (UniqueConstraint('run_id', 'position', name='uq_agent_step_position'),
        CheckConstraint("status IN ('pending','running','completed','failed','cancelled','timed_out')", name='ck_agent_step_status'))
