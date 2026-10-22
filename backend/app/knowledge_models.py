"""Workspace-scoped document metadata and durable semantic vectors."""
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


class KnowledgeDocument(Base):
    __tablename__ = 'knowledge_documents'
    __table_args__ = (
        UniqueConstraint('workspace_id', 'fingerprint', name='uq_kb_workspace_fingerprint'),
        CheckConstraint("status IN ('processing', 'ready', 'failed')", name='ck_kb_status'),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(180))
    file_type: Mapped[str] = mapped_column(String(10))
    size_bytes: Mapped[int] = mapped_column(Integer)
    fingerprint: Mapped[str] = mapped_column(String(64))
    checksum: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20))
    error_code: Mapped[str | None] = mapped_column(String(50))
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    source_metadata: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KnowledgeChunk(Base):
    __tablename__ = 'knowledge_chunks'
    __table_args__ = (UniqueConstraint('document_id', 'chunk_index', name='uq_kb_document_chunk'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey('knowledge_documents.id'), index=True)
    page_number: Mapped[int | None] = mapped_column(Integer)
    chunk_index: Mapped[int] = mapped_column(Integer)
    passage: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list] = mapped_column(JSON)
