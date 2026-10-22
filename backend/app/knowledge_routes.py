"""Raw bounded uploads and questions authenticated by workspace capability key."""
import os
from datetime import datetime, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from starlette.concurrency import run_in_threadpool
from .intelligence import IntelligenceError
from .knowledge_config import workspace, settings, limit_requests
from .knowledge_models import KnowledgeDocument
from .knowledge_service import ingest, document_view, retrieve, answer
from .models import Complaint
from .routes import DB

def no_cache(response: Response):
    response.headers['Cache-Control'] = 'no-store'


router = APIRouter(prefix='/api/knowledge', tags=['knowledge'], dependencies=[Depends(no_cache)])
Workspace = Annotated[str, Depends(workspace)]


def failure(exc: IntelligenceError):
    raise HTTPException(exc.status, {'code': exc.code}) from None


@router.get('/documents')
def documents(session: DB, scope: Workspace, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    rows = session.scalars(select(KnowledgeDocument).where(KnowledgeDocument.workspace_id == scope)
                           .order_by(KnowledgeDocument.created_at.desc(), KnowledgeDocument.id)
                           .offset(offset).limit(limit)).all()
    return {'items': [document_view(doc) for doc in rows], 'workspace': scope,
            'analytics_available': scope == os.getenv('KB_ANALYTICS_WORKSPACE', '')}


@router.get('/documents/{document_id}')
def document_status(document_id: Annotated[str, Path(max_length=36)], session: DB, scope: Workspace):
    doc = session.scalar(select(KnowledgeDocument).where(
        KnowledgeDocument.id == document_id, KnowledgeDocument.workspace_id == scope))
    if doc is None:
        raise HTTPException(404, 'Document not found.')
    return document_view(doc)


@router.post('/documents')
async def upload(request: Request, session: DB, scope: Workspace,
                 filename: str = Query(min_length=1, max_length=180)):
    try:
        config = settings()
        limit_requests(scope, config.requests_per_minute)
        if '/' in filename or '\\' in filename or any(ord(c) < 32 for c in filename):
            raise IntelligenceError('invalid_filename', 422)
        extension = filename.rsplit('.', 1)[-1].lower()
        expected = {'pdf': 'application/pdf', 'txt': 'text/plain'}
        if extension not in expected:
            raise IntelligenceError('unsupported_file_type', 415)
        if request.headers.get('content-type', '').split(';')[0].strip().lower() != expected[extension]:
            raise IntelligenceError('file_content_type_mismatch', 415)
        length = request.headers.get('content-length')
        if length is not None:
            try:
                declared = int(length)
                if declared < 0:
                    raise ValueError()
            except ValueError:
                raise IntelligenceError('invalid_content_length', 400) from None
            if declared > config.upload_bytes:
                raise IntelligenceError('upload_too_large', 413)
        content = bytearray()
        async for chunk in request.stream():
            if len(content) + len(chunk) > config.upload_bytes:
                raise IntelligenceError('upload_too_large', 413)
            content.extend(chunk)
        return await run_in_threadpool(ingest, bytes(content), filename, extension, scope, session, config)
    except IntelligenceError as exc:
        failure(exc)


class Question(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    question: str = Field(min_length=3, max_length=1000)
    top_k: int = Field(default=4, ge=1, le=5)
    document_ids: list[Annotated[str, Field(pattern=r'^[a-f0-9-]{36}$')]] | None = Field(default=None, min_length=1, max_length=10)
    include_analytics: bool = False

    @field_validator('question')
    @classmethod
    def trim_question(cls, value):
        if len(value.strip()) < 3 or any(ord(c) < 32 and c not in '\n\t' for c in value):
            raise ValueError('Use a non-empty text question.')
        return value.strip()


@router.post('/ask')
def ask(payload: Question, session: DB, scope: Workspace):
    if payload.include_analytics and scope != os.getenv('KB_ANALYTICS_WORKSPACE', ''):
        raise HTTPException(403, 'Complaint analytics are not authorized for this workspace.')
    try:
        config = settings()
        limit_requests(scope, config.requests_per_minute)
        sources = retrieve(payload.question, scope, session, config, payload.top_k, payload.document_ids)
        result = answer(payload.question, sources)
        if payload.include_analytics:
            # Explicit fixed aggregate queries only. No complaint text goes to an LLM.
            counts = dict(session.execute(select(Complaint.status, func.count()).group_by(Complaint.status)).all())
            categories = session.execute(select(Complaint.category, func.count()).group_by(Complaint.category)
                                         .order_by(func.count().desc(), Complaint.category).limit(20)).all()
            result['calculated_analytics'] = {
                'label': 'Calculated from imported complaint records; not document evidence.',
                'scope': 'All stored complaints assigned to this installation workspace',
                'total': sum(counts.values()), 'status_counts': counts,
                'top_categories': [{'category': category, 'count': count} for category, count in categories],
                'as_of': datetime.now(timezone.utc),
            }
        return result
    except IntelligenceError as exc:
        failure(exc)
