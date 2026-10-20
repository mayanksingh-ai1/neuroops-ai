"""Parameterized SQL queries; imports never overwrite existing complaints."""
import os
import secrets
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from .database import get_engine, get_session
from .ingestion import CSVError, MAX_BYTES, validate_csv
from .models import Complaint

router = APIRouter(prefix='/api')
DB = Annotated[Session, Depends(get_session)]


def require_import_key(x_import_key: Annotated[str | None, Header()] = None):
    expected = os.getenv('IMPORT_API_KEY', '')
    if len(expected) < 32:
        raise HTTPException(503, 'Configure an IMPORT_API_KEY of at least 32 characters before importing.')
    if not x_import_key or not secrets.compare_digest(x_import_key.encode(), expected.encode()):
        raise HTTPException(401, 'A valid X-Import-Key header is required.')


def validate_import_content_type(content_type: str | None) -> None:
    if (content_type or '').split(';')[0].strip().lower() != 'text/csv':
        raise HTTPException(415, 'Send a UTF-8 CSV body with Content-Type: text/csv.')


def save_records(records: list[dict]) -> int:
    inserted = 0
    # PostgreSQL handles conflicts atomically, including concurrent uploads.
    # Batches avoid exceeding the driver's SQL parameter limit.
    with Session(get_engine()) as session:
        for start in range(0, len(records), 500):
            statement = insert(Complaint).values(records[start:start + 500]).on_conflict_do_nothing(
                index_elements=['complaint_id']
            ).returning(Complaint.complaint_id)
            inserted += len(session.execute(statement).all())
        session.commit()
    return inserted


@router.post('/complaints/import', dependencies=[Depends(require_import_key)])
async def import_csv(request: Request):
    # Raw CSV avoids multipart spooling before the size check. No file is saved.
    validate_import_content_type(request.headers.get('content-type'))
    length = request.headers.get('content-length')
    if length is not None:
        try:
            length = int(length)
            if length < 0:
                raise ValueError()
        except ValueError:
            raise HTTPException(400, 'Invalid Content-Length header.') from None
        if length > MAX_BYTES:
            raise HTTPException(413, 'CSV exceeds the 2 MiB limit.')
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > MAX_BYTES:
            raise HTTPException(413, 'CSV exceeds the 2 MiB limit.')
        content.extend(chunk)
    try:
        records, invalid, errors = validate_csv(bytes(content))
    except CSVError as exc:
        raise HTTPException(422, str(exc)) from exc
    # Run the synchronous database transaction outside the event loop.
    from starlette.concurrency import run_in_threadpool
    inserted = await run_in_threadpool(save_records, records) if records else 0
    return {'total_rows': len(records) + invalid, 'inserted': inserted,
            'duplicates': len(records) - inserted, 'invalid': invalid,
            'errors': errors, 'errors_truncated': invalid > len(errors)}


@router.get('/complaints')
def complaints(session: DB, q: str = Query('', max_length=100),
               limit: int = Query(10, ge=1, le=100), offset: int = Query(0, ge=0)):
    statement = select(Complaint)
    if q.strip():
        # Escape wildcard characters: search terms are literal, not SQL patterns.
        term = q.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        statement = statement.where(
            Complaint.title.ilike(f'%{term}%', escape='\\') |
            Complaint.complaint_id.ilike(f'%{term}%', escape='\\') |
            Complaint.category.ilike(f'%{term}%', escape='\\')
        )
    total = session.scalar(select(func.count()).select_from(statement.subquery()))
    rows = session.scalars(statement.order_by(Complaint.received_date.desc(), Complaint.complaint_id)
                           .limit(limit).offset(offset)).all()
    return {'total': total, 'items': [{'complaint_id': row.complaint_id, 'title': row.title,
        'category': row.category, 'status': row.status, 'priority': row.priority,
        'channel': row.channel, 'received_date': row.received_date} for row in rows]}


@router.get('/analytics/categories')
def categories(session: DB):
    rows = session.execute(select(Complaint.category, func.count()).group_by(Complaint.category)
                           .order_by(func.count().desc(), Complaint.category)).all()
    return [{'name': name, 'count': count} for name, count in rows]


@router.get('/analytics/status')
def status_counts(session: DB):
    counts = {'open': 0, 'in_progress': 0, 'resolved': 0}
    counts.update(dict(session.execute(select(Complaint.status, func.count()).group_by(Complaint.status)).all()))
    return {'total': sum(counts.values()), 'counts': counts}


@router.get('/analytics/trends')
def trends(session: DB, start: date | None = None, end: date | None = None):
    end = end or date.today()
    start = start or end - timedelta(days=29)
    if start > end or (end - start).days > 365:
        raise HTTPException(422, 'Use start <= end with a range of at most 366 days.')
    rows = session.execute(select(Complaint.received_date, func.count()).where(
        Complaint.received_date.between(start, end)).group_by(Complaint.received_date)).all()
    counts = dict(rows)
    return [{'day': start + timedelta(days=i), 'complaints': counts.get(start + timedelta(days=i), 0)}
            for i in range((end - start).days + 1)]
