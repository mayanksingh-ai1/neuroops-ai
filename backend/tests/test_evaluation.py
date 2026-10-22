import csv
import io
import json
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.database import get_session
from app.main import app
from app.models import Complaint
from app.knowledge_models import KnowledgeDocument, KnowledgeChunk
from app.knowledge_config import _calls
from app import evaluation_provider as provider
from app.evaluation_models import Evaluation, EvaluationCase
from app.intelligence import IntelligenceError
from test_intelligence import database

HEADERS = {'X-Workspace-Key': 'a' * 32}
BETA = {'X-Workspace-Key': 'b' * 32}
REVIEW = {**HEADERS, 'X-Reviewer-Key': 'r' * 32}


@pytest.fixture(autouse=True)
def config(monkeypatch):
    monkeypatch.setenv('KB_WORKSPACE_KEYS_JSON', json.dumps({'alpha': 'a' * 32, 'beta': 'b' * 32}))
    monkeypatch.setenv('EVAL_REVIEWER_KEYS_JSON', json.dumps({'alpha': {'reviewer-1': 'r' * 32}}))
    monkeypatch.setenv('OPENAI_API_KEY', 'test-only')
    monkeypatch.setenv('LLM_MODEL', 'mock-model')
    monkeypatch.setenv('EVAL_JUDGE_PROVIDER', 'openai')
    monkeypatch.delenv('EVAL_JUDGE_MODEL', raising=False)
    _calls.clear()
    def no_network(*args, **kwargs):
        raise AssertionError('Unexpected external provider call')
    monkeypatch.setattr(provider, 'post_json', no_network)


@pytest.fixture
def client(database):
    app.dependency_overrides[get_session] = lambda: database
    with TestClient(app) as value:
        yield value
    app.dependency_overrides.clear()


def create(client, **values):
    result = client.post('/api/evaluation/cases', headers=HEADERS, json={
        'question': 'What is the refund window?', 'response': 'Thirty days.', 'model': 'model-a', **values})
    assert result.status_code == 201, result.text
    return result.json()['case']


def evaluate(client, case, judge=False):
    result = client.post(f"/api/evaluation/cases/{case['id']}/evaluate", headers=HEADERS,
                         json={'use_judge': judge, 'provider_consent': judge})
    assert result.status_code == 201, result.text
    return result.json()


def mock_judge(monkeypatch, output=None):
    calls = []
    def post(url, payload, key):
        calls.append(payload)
        scores = {name: {'score': 3, 'reason': 'Mostly satisfies this criterion.'} for name in provider.JudgeOutput.model_fields}
        return {'model': 'mock-judge-version', 'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(output or scores)}}]}
    monkeypatch.setattr(provider, 'post_json', post)
    return calls


def evidence(database, scope='alpha'):
    document_id, chunk_id = str(uuid4()), str(uuid4())
    database.add(KnowledgeDocument(id=document_id, workspace_id=scope, name='policy.txt', file_type='txt',
        size_bytes=50, fingerprint=uuid4().hex, checksum='x' * 64, status='ready', chunk_count=1, source_metadata={}))
    database.flush()
    database.add(KnowledgeChunk(id=chunk_id, document_id=document_id, chunk_index=0, page_number=2,
        passage='Refund requests must arrive within thirty days.', embedding=[1., 0.]))
    database.commit()
    return chunk_id


def test_deterministic_rules_exact_match_and_preservation(client, database):
    case = create(client, response='  THIRTY  days. ', reference='thirty days.',
                  rules={'max_words': 3, 'required_terms': ['thirty', 'missing'], 'json_object': True})
    result = evaluate(client, case)
    assert result['deterministic']['correctness']['score'] == 1
    assert result['deterministic']['instruction_following']['score'] == .5
    assert all(value['score'] is None for value in result['judged'].values())
    assert result['rubric']['version'] == 'eval-v1'
    assert result['evaluator']['provider'] == 'local'
    assert database.get(Complaint, 'CMP-1').category == 'original'


def test_missing_context_is_not_scored_even_if_judge_invents_scores(client, monkeypatch):
    mock_judge(monkeypatch)
    result = evaluate(client, create(client), True)
    for name in ('correctness', 'groundedness', 'instruction_following', 'safety'):
        assert result['judged'][name]['score'] is None
    assert result['judged']['relevance']['score'] == .75
    assert result['deterministic']['correctness']['score'] is None
    assert result['deterministic']['citation_validity']['score'] is None


def test_judge_payload_is_blinded_and_minimized(client, database, monkeypatch):
    calls = mock_judge(monkeypatch)
    chunk = evidence(database)
    case = create(client, reference='Thirty days.', evidence_chunk_ids=[chunk], instructions='Be concise',
        policy='Do not disclose personal data.', metadata={'private_tag': 'do-not-send'}, model='secret-model-label')
    result = evaluate(client, case, True)
    assert all(value['score'] == .75 for value in result['judged'].values())
    payload = json.dumps(calls)
    assert 'do-not-send' not in payload and 'secret-model-label' not in payload and 'a' * 32 not in payload
    assert calls[0]['store'] is False
    assert calls[0]['response_format']['json_schema']['strict'] is True
    assert result['evaluator']['returned_model'] == 'mock-judge-version'


@pytest.mark.parametrize('quote,marker,expected', [('within thirty days', True, 1), ('fabricated passage', True, 0), ('within thirty days', False, 0)])
def test_citation_integrity(client, database, quote, marker, expected):
    chunk = evidence(database)
    case = create(client, response=f'Thirty days. [source:{chunk}]' if marker else 'Thirty days.',
                  evidence_chunk_ids=[chunk], citations=[{'chunk_id': chunk, 'quote': quote}])
    assert evaluate(client, case)['deterministic']['citation_validity']['score'] == expected


def test_required_citation_missing(client):
    result = evaluate(client, create(client, rules={'require_citations': True}))
    assert result['deterministic']['citation_validity']['score'] == 0


def test_cross_workspace_evidence_rejected_without_disclosure(client, database):
    chunk = evidence(database, 'beta')
    result = client.post('/api/evaluation/cases', headers=HEADERS, json={
        'question': 'Refund policy?', 'response': 'Thirty days', 'model': 'a', 'evidence_chunk_ids': [chunk]})
    assert result.status_code == 422
    assert 'policy.txt' not in result.text


@pytest.mark.parametrize('response,score', [('sk-' + 'x' * 20, 0), ('-----BEGIN PRIVATE KEY-----', 0), ('No matching pattern.', 1)])
def test_safety_screen_is_explicit_proxy(client, response, score):
    result = evaluate(client, create(client, response=response))
    assert result['deterministic']['safety']['score'] == score
    assert 'not a policy' in result['deterministic']['safety']['reason']


@pytest.mark.parametrize('code', ['provider_timeout', 'provider_rate_limited', 'provider_authentication', 'provider_unavailable'])
def test_provider_errors_persist_with_deterministic_results(client, monkeypatch, code):
    def fail(*args):
        raise IntelligenceError(code)
    monkeypatch.setattr(provider, 'post_json', fail)
    result = evaluate(client, create(client), True)
    assert result['status'] == 'failed' and result['error_code'] == code
    assert result['deterministic'] and all(item['score'] is None for item in result['judged'].values())


@pytest.mark.parametrize('output', [{}, {'correctness': {'score': 5, 'reason': 'Out of range'}},
    {name: {'score': '4', 'reason': 'Wrong type'} for name in provider.JudgeOutput.model_fields}])
def test_invalid_judge_output(client, monkeypatch, output):
    monkeypatch.setattr(provider, 'post_json', lambda *args: {'model': 'mock', 'choices': [{
        'finish_reason': 'stop', 'message': {'content': json.dumps(output)}}]})
    result = evaluate(client, create(client), True)
    assert result['error_code'] == 'invalid_evaluator_output'


def test_missing_credentials_and_consent(client, monkeypatch):
    case = create(client)
    assert client.post(f"/api/evaluation/cases/{case['id']}/evaluate", headers=HEADERS,
        json={'use_judge': True}).status_code == 422
    monkeypatch.delenv('OPENAI_API_KEY')
    assert evaluate(client, case, True)['error_code'] == 'missing_evaluation_configuration'


def test_review_is_append_only_and_identity_is_not_user_supplied(client, database):
    case = create(client, reference='Other answer')
    result = evaluate(client, case)
    path = f"/api/evaluation/results/{result['id']}/reviews"
    payload = {'decision': 'correct', 'feedback': 'Reference is wrong; human checked the policy.',
               'corrections': {'correctness': {'score': 1.0, 'reason': 'Verified against current policy.'}}}
    assert client.post(path, headers=HEADERS, json=payload).status_code == 403
    response = client.post(path, headers=REVIEW, json=payload)
    assert response.status_code == 201
    assert response.json()['reviewer_id'] == 'reviewer-1'
    assert client.post(path, headers=REVIEW, json={'decision': 'approve', 'feedback': 'Second review agrees.'}).status_code == 201
    detail = client.get(f"/api/evaluation/cases/{case['id']}", headers=HEADERS).json()
    original = detail['evaluations'][0]
    assert original['deterministic']['correctness']['score'] == 0
    assert len(original['reviews']) == 2
    assert database.get(Evaluation, result['id']).deterministic == result['deterministic']
    assert client.post(path, headers=REVIEW, json={**payload, 'reviewer_id': 'impersonated'}).status_code == 422


def test_all_reads_and_actions_are_workspace_scoped(client):
    case = create(client)
    result = evaluate(client, case)
    assert client.get('/api/evaluation/cases').status_code == 401
    assert client.get(f"/api/evaluation/cases/{case['id']}", headers=BETA).status_code == 404
    assert client.post(f"/api/evaluation/cases/{case['id']}/evaluate", headers=BETA, json={}).status_code == 404
    for path in ('cases', 'results', 'comparisons'):
        assert client.get('/api/evaluation/' + path, headers=BETA).json()['items'] == []
    assert client.get('/api/evaluation/summary', headers=BETA).json()['evaluations'] == 0
    assert client.get('/api/evaluation/export', headers=BETA).json()['items'] == []
    assert client.post(f"/api/evaluation/results/{result['id']}/reviews", headers={**BETA, 'X-Reviewer-Key': 'r' * 32},
        json={'decision': 'approve', 'feedback': 'Looks fine'}).status_code == 403


def csv_bytes(rows, fields=None):
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=fields or ['question', 'response', 'model', 'rules'])
    writer.writeheader(); writer.writerows(rows)
    return buffer.getvalue().encode()


def test_csv_partial_validation_duplicates_and_error_rows(client):
    good = {'question': 'Refund window?', 'response': 'Thirty days', 'model': 'a', 'rules': '{}'}
    content = csv_bytes([good, good, {**good, 'question': ''}, {**good, 'rules': '{bad json'}])
    result = client.post('/api/evaluation/cases/import', headers={**HEADERS, 'Content-Type': 'text/csv'}, content=content)
    assert result.status_code == 200, result.text
    assert {key: result.json()[key] for key in ('inserted', 'duplicates', 'invalid')} == {'inserted': 1, 'duplicates': 1, 'invalid': 2}
    assert [error['row'] for error in result.json()['errors']] == [4, 5]


@pytest.mark.parametrize('content', [b'question,response\nHello,Hi', b'question,response,model,model\na,b,c,d',
    b'question,response,model\n"unterminated', b'\xff\xfe'])
def test_csv_malformed_files_rejected(client, content):
    assert client.post('/api/evaluation/cases/import', headers={**HEADERS, 'Content-Type': 'text/csv'}, content=content).status_code == 422


def test_size_and_row_limits_are_atomic(client):
    assert client.post('/api/evaluation/cases/import', headers={**HEADERS, 'Content-Type': 'text/csv'}, content=b'x' * (1024 * 1024 + 1)).status_code == 413
    content = csv_bytes([{'question': 'Refund?', 'response': 'Thirty days', 'model': 'a', 'rules': '{}'}] * 501)
    assert client.post('/api/evaluation/cases/import', headers={**HEADERS, 'Content-Type': 'text/csv'}, content=content).status_code == 413
    assert client.get('/api/evaluation/cases', headers=HEADERS).json()['total'] == 0
    assert client.post('/api/evaluation/cases', headers=HEADERS, content=b'x' * 65537).status_code == 413


def test_summary_denominators_filters_and_export(client):
    a = create(client, model='a', dataset='sample', reference='Thirty days.')
    b = create(client, model='b')
    evaluate(client, a); evaluate(client, b)
    summary = client.get('/api/evaluation/summary', headers=HEADERS).json()
    exact = next(item for item in summary['metrics'] if item['metric'] == 'correctness' and item['method'] == 'deterministic')
    assert exact['mean'] == 1 and exact['assessed'] == 1 and exact['not_assessed'] == 1
    assert client.get('/api/evaluation/summary?model=a&dataset=sample&status=completed', headers=HEADERS).json()['evaluations'] == 1
    assert client.get('/api/evaluation/summary?start=2099-01-01', headers=HEADERS).json()['evaluations'] == 0
    assert client.get('/api/evaluation/summary?start=2026-02-01&end=2026-01-01', headers=HEADERS).status_code == 422
    exported = client.get('/api/evaluation/export?model=a&format=json', headers=HEADERS)
    assert len(exported.json()['items']) == 1 and exported.headers['cache-control'] == 'no-store'
    assert exported.json()['items'][0]['evaluation']['rubric']['version'] == 'eval-v1'


def test_export_neutralizes_spreadsheet_formulas(client):
    case = create(client, model='=DANGEROUS()', response='@formula')
    evaluate(client, case)
    response = client.get('/api/evaluation/export?format=csv', headers=HEADERS)
    row = list(csv.DictReader(io.StringIO(response.text)))[0]
    assert row['model'] == "'=DANGEROUS()" and row['response'] == "'@formula"


def test_comparison_requires_shared_context_and_is_a_snapshot(client):
    a = create(client); b = create(client, model='b', response='Twenty days.')
    evaluate(client, a); evaluate(client, b)
    response = client.post('/api/evaluation/comparisons', headers=HEADERS, json={'case_ids': [a['id'], b['id']]})
    assert response.status_code == 201
    assert len(response.json()['items']) == 2
    assert response.json()['pairwise']['status'] == 'not_requested'
    c = create(client, model='c', reference='Different reference')
    assert client.post('/api/evaluation/comparisons', headers=HEADERS, json={'case_ids': [a['id'], c['id']]}).status_code == 422
    assert client.post('/api/evaluation/comparisons', headers=HEADERS, json={'case_ids': [a['id'], a['id']]}).status_code == 422


@pytest.mark.parametrize('preferences,expected', [(['A', 'B'], 'first'), (['A', 'A'], 'inconclusive'), (['tie', 'tie'], 'tie')])
def test_pairwise_reverse_order_and_blinding(client, monkeypatch, preferences, expected):
    calls = []
    monkeypatch.setattr(provider.secrets, 'randbelow', lambda size: 0)
    def post(url, payload, key):
        index = len(calls); calls.append(payload)
        return {'model': 'mock', 'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps({
            'preference': preferences[index], 'reason': 'Preference only on these supplied responses.'})}}]}
    monkeypatch.setattr(provider, 'post_json', post)
    a = create(client); b = create(client, model='secret-model-b', response='Twenty days.')
    response = client.post('/api/evaluation/comparisons', headers=HEADERS, json={
        'case_ids': [a['id'], b['id']], 'use_judge': True, 'provider_consent': True})
    assert response.status_code == 201
    result = response.json()['pairwise']
    assert result['preference'] == (a['id'] if expected == 'first' else expected)
    assert len(calls) == 2 and 'secret-model-b' not in json.dumps(calls)
    first = json.loads(calls[0]['messages'][1]['content'])
    second = json.loads(calls[1]['messages'][1]['content'])
    assert first['candidate_A'] == second['candidate_B']
