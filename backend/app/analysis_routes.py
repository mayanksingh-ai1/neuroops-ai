"""Operator-only paid actions; read results through the complaint API."""
from typing import Annotated
from uuid import uuid4
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from . import intelligence
from .models import Complaint, ComplaintAnalysis
from .routes import DB, require_import_key

router = APIRouter(prefix='/api', dependencies=[Depends(require_import_key)])
ComplaintID = Annotated[str, Field(pattern=r'^[A-Za-z0-9_-]+$', min_length=1, max_length=64)]


class BatchRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    complaint_ids: list[ComplaintID] = Field(min_length=1, max_length=5)


def serialize_analysis(row: ComplaintAnalysis) -> dict:
    return {name: getattr(row, name) for name in (
        'id', 'complaint_id', 'status', 'category', 'sentiment', 'priority',
        'error_code', 'details', 'created_at',
    )} | {'human_verified': False}


def analyze(complaint: Complaint, session: DB) -> tuple[dict, int]:
    attempt = ComplaintAnalysis(
        id=str(uuid4()), complaint_id=complaint.complaint_id,
        status='failed', details={'human_verified': False},
        created_at=datetime.now(timezone.utc),
    )
    status = 200
    try:
        rules = intelligence.settings()
        attempt.details = {
            'rules': rules.model_dump(), 'rules_version': '1',
            'provider': 'openai', 'prompt_version': '1', 'privacy_version': 'vocabulary-v1',
        }
        text = intelligence.minimize_text(complaint.title)
        if not text:
            raise intelligence.IntelligenceError('insufficient_text', 422)
        output, metadata = intelligence.classify(text, rules)
        priority, reason = intelligence.assess_priority(text, output.sentiment, rules)
        attempt.status = 'completed'
        attempt.category, attempt.sentiment, attempt.priority = output.category, output.sentiment, priority
        attempt.details = {**attempt.details, **metadata, 'priority_rule': reason}
    except intelligence.IntelligenceError as exc:
        attempt.error_code, status = exc.code, exc.status
    session.add(attempt)
    session.commit()
    session.refresh(attempt)
    return serialize_analysis(attempt), status


@router.post('/complaints/classify-batch')
def classify_batch(payload: BatchRequest, session: DB):
    ids = list(dict.fromkeys(payload.complaint_ids))
    rows = {row.complaint_id: row for row in session.scalars(
        select(Complaint).where(Complaint.complaint_id.in_(ids))
    )}
    results = []
    for complaint_id in ids:
        if complaint_id not in rows:
            results.append({'complaint_id': complaint_id, 'status': 'not_found'})
        else:
            result, status = analyze(rows[complaint_id], session)
            results.append({**result, 'http_status': status})
    return {'items': results}


@router.post('/complaints/{complaint_id}/classify')
def classify_one(session: DB, complaint_id: Annotated[str, Path(
    pattern=r'^[A-Za-z0-9_-]+$', min_length=1, max_length=64,
)]):
    complaint = session.get(Complaint, complaint_id)
    if complaint is None:
        raise HTTPException(404, 'Complaint not found.')
    result, status = analyze(complaint, session)
    if status != 200:
        raise HTTPException(status, {'code': result['error_code'], 'analysis_id': result['id']})
    return result
