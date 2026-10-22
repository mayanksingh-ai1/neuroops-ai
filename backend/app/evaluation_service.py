"""Storage and execution shared by the API and CSV importer."""
import csv
import hashlib
import io
import json
import time
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select, func, update
from .evaluation_models import EvaluationCase, Evaluation, EvaluationReview, EvaluationComparison
from .evaluation_schemas import CaseInput
from .evaluation_metrics import RUBRIC, deterministic, unassessed, normalize
from . import evaluation_provider as provider
from .knowledge_models import KnowledgeChunk, KnowledgeDocument
from .knowledge_service import lock_workspace
from .knowledge_config import workspace
from .agent_budget import deadline
from .intelligence import IntelligenceError

CASE_LIMIT = 1000
ATTEMPT_LIMIT = 20


def get_case(session, scope, case_id):
    row = session.scalar(select(EvaluationCase).where(EvaluationCase.id == case_id, EvaluationCase.workspace_id == scope))
    if row is None:
        raise HTTPException(404, 'Evaluation case not found.')
    return row


def get_evaluation(session, scope, evaluation_id):
    row = session.scalar(select(Evaluation).join(EvaluationCase).where(Evaluation.id == evaluation_id,
                                                                        EvaluationCase.workspace_id == scope))
    if row is None:
        raise HTTPException(404, 'Evaluation not found.')
    return row


def case_view(row):
    return {field: getattr(row, field) for field in ('id', 'dataset', 'model', 'provider', 'question', 'response', 'reference', 'context', 'created_at')}


def review_view(row):
    return {field: getattr(row, field) for field in ('id', 'reviewer_id', 'decision', 'feedback', 'corrections', 'created_at')}


def evaluation_view(session, row):
    result = {field: getattr(row, field) for field in ('id', 'case_id', 'status', 'deterministic', 'judged', 'rubric', 'evaluator', 'error_code', 'created_at')}
    result['reviews'] = [review_view(review) for review in session.scalars(select(EvaluationReview).where(
        EvaluationReview.evaluation_id == row.id).order_by(EvaluationReview.created_at, EvaluationReview.id))]
    result['human_verified'] = False  # A review is a separate opinion, not a truth certificate.
    return result


def selected_evidence(session, scope, ids):
    if not ids:
        return []
    rows = session.execute(select(KnowledgeChunk, KnowledgeDocument).join(KnowledgeDocument).where(
        KnowledgeDocument.workspace_id == scope, KnowledgeDocument.status == 'ready', KnowledgeChunk.id.in_(ids))).all()
    if len(rows) != len(ids):
        raise HTTPException(422, 'One or more evidence chunks are unavailable in this workspace.')
    sources = {chunk.id: {'chunk_id': chunk.id, 'document_id': document.id, 'name': document.name,
                         'page_number': chunk.page_number, 'chunk_index': chunk.chunk_index, 'passage': chunk.passage,
                         'provenance': 'Workspace document selected as expected evidence; not a relevance guarantee.'}
               for chunk, document in rows}
    return [sources[source_id] for source_id in ids]


def save_case(session, scope, payload):
    canonical = payload.model_dump()
    fingerprint = hashlib.sha256(json.dumps(canonical, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    lock_workspace(session, 'eval-cases:' + scope)
    existing = session.scalar(select(EvaluationCase).where(EvaluationCase.workspace_id == scope,
                                                          EvaluationCase.fingerprint == fingerprint))
    if existing is not None:
        return existing, True
    if session.scalar(select(func.count()).select_from(EvaluationCase).where(EvaluationCase.workspace_id == scope)) >= CASE_LIMIT:
        raise HTTPException(409, 'Workspace evaluation case limit reached (1000).')
    evidence = selected_evidence(session, scope, payload.evidence_chunk_ids)
    row = EvaluationCase(workspace_id=scope, fingerprint=fingerprint, dataset=payload.dataset, model=payload.model,
                         provider=payload.provider, question=payload.question, response=payload.response, reference=payload.reference,
                         context={'instructions': payload.instructions, 'policy': payload.policy, 'evidence': evidence,
                                  'citations': [item.model_dump() for item in payload.citations],
                                  'rules': payload.rules.model_dump(), 'metadata': payload.metadata})
    session.add(row)
    session.flush()
    return row, False


def import_cases(content, session, scope):
    try:
        source = content.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise HTTPException(422, 'Upload a UTF-8 CSV file.') from None
    reader = csv.DictReader(io.StringIO(source, newline=''), strict=True)
    try:
        fields = reader.fieldnames
        if not fields or len(fields) != len(set(fields)) or not {'question', 'response', 'model'} <= set(fields):
            raise HTTPException(422, 'CSV requires distinct headers including question, response, and model.')
        if set(fields) - set(CaseInput.model_fields):
            raise HTTPException(422, 'CSV contains unsupported columns.')
        rows = []
        for number, row in enumerate(reader, 2):
            if len(rows) >= 500:
                raise HTTPException(413, 'CSV exceeds 500 data rows; no rows imported.')
            rows.append((number, row))
    except csv.Error:
        raise HTTPException(422, 'Malformed CSV; no rows imported.') from None
    if not rows:
        raise HTTPException(422, 'CSV contains no data rows.')
    inserted = duplicates = invalid = 0
    errors = []
    for number, row in rows:
        try:
            if None in row or any(value is None for value in row.values()):
                raise ValueError('Column count does not match the header.')
            values = {name: value for name, value in row.items() if value != ''}
            for name in ('evidence_chunk_ids', 'citations', 'rules', 'metadata'):
                if name in values:
                    values[name] = json.loads(values[name])
            payload = CaseInput.model_validate(values)
            _, duplicate = save_case(session, scope, payload)
            duplicates += int(duplicate)
            inserted += int(not duplicate)
        except (ValueError, ValidationError, HTTPException, RecursionError) as exc:
            # Do not echo arbitrary row content or validation input into errors.
            invalid += 1
            if len(errors) < 50:
                if isinstance(exc, ValidationError):
                    message = '; '.join('.'.join(map(str, item['loc'])) + ': ' + item['type'] for item in exc.errors()[:5])
                elif isinstance(exc, HTTPException):
                    message = str(exc.detail)
                else:
                    message = 'Invalid JSON field or CSV column count.'
                errors.append({'row': number, 'message': message})
    session.commit()
    return {'total_rows': len(rows), 'inserted': inserted, 'duplicates': duplicates, 'invalid': invalid,
            'errors': errors, 'errors_truncated': invalid > len(errors)}


def verify_capability(key, scope):
    from .security import check_principal
    check_principal()
    if workspace(key) != scope:
        raise HTTPException(403, 'Workspace authorization changed.')


def evaluate(session, scope, case, use_judge, key):
    # Serialize one case's bounded history. No customer table is touched.
    lock_workspace(session, 'eval-attempt:' + case.id)
    if session.scalar(select(func.count()).select_from(Evaluation).where(Evaluation.case_id == case.id)) >= ATTEMPT_LIMIT:
        raise HTTPException(409, 'Evaluation history limit reached (20 per case).')
    rules = deterministic(case)
    judged = unassessed(case, 'LLM judge was not requested.')
    metadata = {**provider.identity(), 'requested': use_judge} if use_judge else {
        'provider': 'local', 'model': None, 'prompt_version': None, 'requested': False}
    error, status = None, 'completed'
    expires_at = time.time() + 60
    row = Evaluation(case_id=case.id, status='running', deterministic=rules, judged=judged,
                     rubric=RUBRIC, evaluator=metadata, error_code=None, expires_at=expires_at)
    session.add(row)
    session.commit()  # Durable attempt and capacity reservation BEFORE any paid call.
    row_id = row.id
    token = deadline.set(expires_at)
    try:
        if use_judge:
            judged, metadata = provider.judge(case)
            metadata = {**metadata, 'requested': True}
    except IntelligenceError as exc:
        error, status = exc.code, 'failed'
        judged = unassessed(case, 'Judge failed: ' + exc.code)
    except Exception:
        error, status = 'evaluation_internal_error', 'failed'
        judged = unassessed(case, 'Evaluation failed.')
    finally:
        deadline.reset(token)
    try:
        verify_capability(key, scope)
    except HTTPException:
        session.execute(update(Evaluation).where(Evaluation.id == row_id, Evaluation.status == 'running')
                        .values(status='failed', error_code='authorization_changed'))
        session.commit()
        raise
    if time.time() >= expires_at:
        error, status, judged = 'evaluation_timeout', 'failed', unassessed(case, 'Evaluation deadline exceeded.')
    session.execute(update(Evaluation).where(Evaluation.id == row_id, Evaluation.status == 'running')
                    .values(status=status, judged=judged, evaluator=metadata, error_code=error))
    session.commit()
    session.refresh(row)
    return row


def comparable(cases):
    first = cases[0]
    def comparable_context(case):
        return {'reference': case.reference, 'instructions': case.context['instructions'],
                'rules': case.context['rules'], 'policy': case.context['policy'],
                'evidence': sorted(case.context['evidence'], key=lambda item: item['chunk_id'])}
    if any(normalize(case.question) != normalize(first.question) or comparable_context(case) != comparable_context(first)
           for case in cases[1:]):
        raise HTTPException(422, 'Comparison requires the same question, reference, instructions, rules, policy, and expected evidence.')


def compare(session, scope, cases, use_judge, key):
    comparable(cases)
    lock_workspace(session, 'eval-comparison:' + scope)
    if session.scalar(select(func.count()).select_from(EvaluationComparison).where(EvaluationComparison.workspace_id == scope)) >= 200:
        raise HTTPException(409, 'Workspace comparison limit reached (200).')
    items = []
    for case in cases:
        latest = session.scalar(select(Evaluation).where(Evaluation.case_id == case.id)
                                .order_by(Evaluation.created_at.desc(), Evaluation.id.desc()).limit(1))
        items.append({'case': case_view(case), 'evaluation': evaluation_view(session, latest) if latest else None})
    preference = {'status': 'not_requested', 'preference': None}
    token = deadline.set(time.time() + 60)
    try:
        if use_judge:
            preference = provider.pairwise(cases)
    except IntelligenceError as exc:
        preference = {'status': 'failed', 'preference': None, 'error_code': exc.code, 'evaluator': provider.identity()}
    finally:
        deadline.reset(token)
    verify_capability(key, scope)
    row = EvaluationComparison(workspace_id=scope, snapshot={'items': items, 'pairwise': preference, 'rubric': RUBRIC,
        'limitation': 'Supplied model labels are unverified. These examples do not establish a universal winning model.'})
    session.add(row)
    session.commit()
    return {'id': row.id, 'created_at': row.created_at, **row.snapshot}
