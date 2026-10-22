"""Workspace-scoped datasets, evaluation, audit review, reporting, and comparison."""
import csv
import io
import json
from collections import Counter, defaultdict
from datetime import date, datetime, time as day_time, timedelta, timezone
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import select, func
from starlette.concurrency import run_in_threadpool
from .routes import DB
from .knowledge_routes import Workspace, no_cache, failure, Question
from .knowledge_config import limit_requests, settings as knowledge_settings
from .knowledge_service import retrieve, lock_workspace
from .evaluation_models import EvaluationCase, Evaluation, EvaluationReview, EvaluationComparison
from .evaluation_schemas import CaseInput, EvaluateInput, ComparisonInput, ReviewInput
from .evaluation_metrics import RUBRIC
from .evaluation_auth import reviewer
from . import evaluation_service as service
from .intelligence import IntelligenceError

def expire_pending(session: DB):
    from .job_maintenance import expire_evaluations
    expire_evaluations(session)


router = APIRouter(prefix='/api/evaluation', tags=['evaluation'], dependencies=[Depends(no_cache), Depends(expire_pending)])
Key = Annotated[str, Header(alias='X-Workspace-Key', max_length=512)]


def filters(dataset: str | None = Query(None, max_length=80), model: str | None = Query(None, max_length=120),
            status: Literal['running', 'completed', 'failed'] | None = None, start: date | None = None, end: date | None = None):
    if start and end and start > end:
        raise HTTPException(422, 'Start date must not follow end date.')
    if end == date.max:
        raise HTTPException(422, 'End date is out of range.')
    return {'dataset': dataset, 'model': model, 'status': status,
            'start': datetime.combine(start, day_time.min, timezone.utc).timestamp() if start else None,
            'end': datetime.combine(end + timedelta(days=1), day_time.min, timezone.utc).timestamp() if end else None}

Filters = Annotated[dict, Depends(filters)]


def filtered(scope, filters, cases=False):
    statement = select(EvaluationCase) if cases else select(Evaluation, EvaluationCase).join(EvaluationCase)
    statement = statement.where(EvaluationCase.workspace_id == scope)
    for name in ('dataset', 'model'):
        if filters[name] is not None:
            statement = statement.where(getattr(EvaluationCase, name) == filters[name])
    if filters['status']:
        if cases:
            statement = statement.where(select(Evaluation.id).where(Evaluation.case_id == EvaluationCase.id,
                Evaluation.status == filters['status']).exists())
        else:
            statement = statement.where(Evaluation.status == filters['status'])
    timestamp = EvaluationCase.created_at if cases else Evaluation.created_at
    if filters['start'] is not None:
        statement = statement.where(timestamp >= filters['start'])
    if filters['end'] is not None:
        statement = statement.where(timestamp < filters['end'])
    return statement


def paid_access(use_judge, consent, scope):
    if use_judge:
        if not consent:
            raise HTTPException(422, 'Provider consent is required for judge calls.')
        limit_requests('evaluation:' + scope, 10)


@router.get('/rubric')
def rubric(scope: Workspace):
    return RUBRIC


@router.post('/cases', status_code=201)
def create_case(payload: CaseInput, session: DB, scope: Workspace):
    row, duplicate = service.save_case(session, scope, payload)
    session.commit()
    return {'case': service.case_view(row), 'duplicate': duplicate}


@router.post('/cases/import')
async def import_csv(request: Request, session: DB, scope: Workspace):
    if request.headers.get('content-type', '').split(';')[0].strip().lower() != 'text/csv':
        raise HTTPException(415, 'Use Content-Type: text/csv with a raw UTF-8 CSV body.')
    return await run_in_threadpool(service.import_cases, await request.body(), session, scope)


@router.get('/cases')
def cases(session: DB, scope: Workspace, selected: Filters, offset: int = Query(0, ge=0), limit: int = Query(30, ge=1, le=100)):
    statement = filtered(scope, selected, cases=True)
    total = session.scalar(select(func.count()).select_from(statement.subquery()))
    rows = session.scalars(statement.order_by(EvaluationCase.created_at.desc(), EvaluationCase.id).offset(offset).limit(limit))
    items = []
    for row in rows:
        latest = session.scalar(select(Evaluation).where(Evaluation.case_id == row.id)
                                .order_by(Evaluation.created_at.desc(), Evaluation.id.desc()).limit(1))
        items.append({**service.case_view(row), 'latest_evaluation': service.evaluation_view(session, latest) if latest else None})
    return {'items': items, 'total': total}


@router.get('/cases/{case_id}')
def case_detail(case_id: str, session: DB, scope: Workspace):
    row = service.get_case(session, scope, case_id)
    results = session.scalars(select(Evaluation).where(Evaluation.case_id == row.id)
                              .order_by(Evaluation.created_at.desc(), Evaluation.id.desc()))
    return {**service.case_view(row), 'evaluations': [service.evaluation_view(session, result) for result in results]}


@router.post('/cases/{case_id}/evaluate', status_code=201)
def evaluate(case_id: str, payload: EvaluateInput, session: DB, scope: Workspace, x_workspace_key: Key):
    case = service.get_case(session, scope, case_id)
    try:
        paid_access(payload.use_judge, payload.provider_consent, scope)
        row = service.evaluate(session, scope, case, payload.use_judge, x_workspace_key)
        return service.evaluation_view(session, row)
    except IntelligenceError as exc:
        failure(exc)


@router.get('/results')
def results(session: DB, scope: Workspace, selected: Filters, offset: int = Query(0, ge=0), limit: int = Query(30, ge=1, le=100)):
    statement = filtered(scope, selected)
    total = session.scalar(select(func.count()).select_from(statement.subquery()))
    rows = session.execute(statement.order_by(Evaluation.created_at.desc(), Evaluation.id).offset(offset).limit(limit))
    return {'total': total, 'items': [{'case': service.case_view(case), 'evaluation': service.evaluation_view(session, result)} for result, case in rows]}


@router.post('/results/{evaluation_id}/reviews', status_code=201)
def review(evaluation_id: str, payload: ReviewInput, session: DB, scope: Workspace,
           x_reviewer_key: Annotated[str | None, Header(max_length=512)] = None):
    identity = reviewer(scope, x_reviewer_key)
    result = service.get_evaluation(session, scope, evaluation_id)
    lock_workspace(session, 'eval-review:' + result.id)
    if session.scalar(select(func.count()).select_from(EvaluationReview).where(EvaluationReview.evaluation_id == result.id)) >= 20:
        raise HTTPException(409, 'Review history limit reached (20 per evaluation).')
    row = EvaluationReview(evaluation_id=result.id, reviewer_id=identity, decision=payload.decision,
                           feedback=payload.feedback, corrections={name: value.model_dump() for name, value in payload.corrections.items()})
    session.add(row)
    session.commit()
    return service.review_view(row)


@router.post('/comparisons', status_code=201)
def compare(payload: ComparisonInput, session: DB, scope: Workspace, x_workspace_key: Key):
    rows = [service.get_case(session, scope, case_id) for case_id in payload.case_ids]
    service.comparable(rows)
    try:
        paid_access(payload.use_judge, payload.provider_consent, scope)
        return service.compare(session, scope, rows, payload.use_judge, x_workspace_key)
    except IntelligenceError as exc:
        failure(exc)


@router.get('/comparisons')
def comparisons(session: DB, scope: Workspace, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=50)):
    rows = session.scalars(select(EvaluationComparison).where(EvaluationComparison.workspace_id == scope)
                           .order_by(EvaluationComparison.created_at.desc(), EvaluationComparison.id).offset(offset).limit(limit))
    return {'items': [{'id': row.id, 'created_at': row.created_at, **row.snapshot} for row in rows]}


class EvidenceSearch(Question):
    provider_consent: bool = False


@router.post('/evidence/search')
def evidence_search(payload: EvidenceSearch, session: DB, scope: Workspace):
    if payload.include_analytics:
        raise HTTPException(422, 'Evaluation evidence search supports documents only.')
    try:
        paid_access(True, payload.provider_consent, scope)
        return {'sources': retrieve(payload.question, scope, session, knowledge_settings(), payload.top_k, payload.document_ids)}
    except IntelligenceError as exc:
        failure(exc)


@router.get('/summary')
def summary(session: DB, scope: Workspace, selected: Filters):
    # Load only small score JSONs. Storage caps bound this to 20,000 attempts/workspace.
    statement = filtered(scope, selected).with_only_columns(Evaluation.id, Evaluation.case_id, Evaluation.status,
        Evaluation.error_code, Evaluation.deterministic, Evaluation.judged, EvaluationCase.model)
    rows = session.execute(statement).all()
    distributions, failures, models = {}, Counter(), defaultdict(lambda: {'evaluations': 0, 'cases': set()})
    for row in rows:
        models[row.model]['evaluations'] += 1
        models[row.model]['cases'].add(row.case_id)
        if row.error_code:
            failures[row.error_code] += 1
        for method, scores in (('deterministic', row.deterministic), ('llm_judge', row.judged)):
            for name, value in scores.items():
                key = method + ':' + name
                item = distributions.setdefault(key, {'method': method, 'metric': name, 'assessed': 0,
                    'not_assessed': 0, 'sum': 0.0, 'distribution': {'zero': 0, 'partial': 0, 'one': 0}})
                score = value['score']
                if score is None:
                    item['not_assessed'] += 1
                else:
                    item['assessed'] += 1
                    item['sum'] += score
                    item['distribution']['zero' if score == 0 else 'one' if score == 1 else 'partial'] += 1
                    if score < 1:
                        failures[key + ':below_full_score'] += 1
    metrics = [{**{key: value for key, value in item.items() if key != 'sum'},
                'mean': item['sum'] / item['assessed'] if item['assessed'] else None} for item in distributions.values()]
    return {'evaluations': len(rows), 'distinct_cases': len({row.case_id for row in rows}),
            'completed': sum(row.status == 'completed' for row in rows), 'failed': sum(row.status == 'failed' for row in rows),
            'metrics': metrics, 'common_failures': [{'type': name, 'count': count} for name, count in failures.most_common(20)],
            'models': [{'model': name, 'evaluations': values['evaluations'], 'distinct_cases': len(values['cases'])}
                       for name, values in sorted(models.items())],
            'label': 'Stored automated attempts, including repeats. Human reviews are separate. Model names are supplied labels, not verified identities.'}


def safe_cell(value):
    value = str(value)
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) or value.startswith(('\t', '\r', '\n')) else value


@router.get('/export')
def export(session: DB, scope: Workspace, selected: Filters, format: Literal['csv', 'json'] = 'json'):
    statement = filtered(scope, selected)
    count = session.scalar(select(func.count()).select_from(statement.subquery()))
    if count > 1000:
        raise HTTPException(413, 'Export exceeds 1000 evaluations. Narrow the date/model/dataset/status filters.')
    rows = [{'case': service.case_view(case), 'evaluation': service.evaluation_view(session, result)} for result, case in
            session.execute(statement.order_by(Evaluation.created_at, Evaluation.id))]
    headers = {'Content-Disposition': f'attachment; filename="neuroops-evaluations.{format}"', 'Cache-Control': 'no-store'}
    if format == 'json':
        return JSONResponse({'rubric': RUBRIC, 'items': rows}, headers=headers)
    buffer = io.StringIO(newline='')
    writer = csv.writer(buffer)
    writer.writerow(['evaluation_id', 'case_id', 'dataset', 'model', 'question', 'response', 'reference', 'status',
                     'created_at', 'deterministic_json', 'judged_json', 'review_history_json', 'context_json', 'evaluator_json', 'rubric_json', 'error_code'])
    for row in rows:
        case, result = row['case'], row['evaluation']
        writer.writerow([safe_cell(value) for value in [result['id'], case['id'], case['dataset'], case['model'],
            case['question'], case['response'], case['reference'] or '', result['status'], result['created_at'],
            json.dumps(result['deterministic'], ensure_ascii=False), json.dumps(result['judged'], ensure_ascii=False),
            json.dumps(result['reviews'], ensure_ascii=False), json.dumps(case['context'], ensure_ascii=False),
            json.dumps(result['evaluator'], ensure_ascii=False), json.dumps(result['rubric'], ensure_ascii=False), result['error_code'] or '']])
    return Response(buffer.getvalue(), media_type='text/csv; charset=utf-8', headers=headers)
