"""No paid requests: workflow, provider adapter, and authorization regression tests."""
import json
import time
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from app.main import app
from app.database import get_session
from app.models import Complaint
from app.agent_models import AgentRun, AgentStep
from app import agent_service as service, agent_tools, agent_planner as planner
from app.agent_budget import deadline, remaining
from app import knowledge_service, knowledge_provider as provider
from app.knowledge_config import _calls
from app.intelligence import IntelligenceError
from test_intelligence import database

HEADERS = {'X-Workspace-Key': 'a' * 32}
BETA = {'X-Workspace-Key': 'b' * 32}
SOURCE = {'chunk_id': 'chunk-1', 'document_id': 'doc-1', 'name': 'refunds.txt', 'page_number': 2,
          'chunk_index': 0, 'passage': 'Refund requests must be submitted within thirty days.', 'similarity': .9}
REAL_EXECUTE = service.execute_run
REAL_PLAN = planner.plan_task


@pytest.fixture(autouse=True)
def config(monkeypatch):
    monkeypatch.setenv('KB_WORKSPACE_KEYS_JSON', json.dumps({'alpha': 'a' * 32, 'beta': 'b' * 32}))
    monkeypatch.setenv('KB_ANALYTICS_WORKSPACE', 'alpha')
    monkeypatch.setenv('OPENAI_API_KEY', 'test-only')
    monkeypatch.setenv('LLM_MODEL', 'mock-model')
    for field in ('MAX_STEPS', 'TIMEOUT_SECONDS', 'RETRIES', 'LLM_MODEL'):
        monkeypatch.delenv('AGENT_' + field, raising=False)
    _calls.clear()
    monkeypatch.setattr(service, 'plan_task', lambda task: (planner.Plan(
        supported=True, reason='Overall complaint trends and refund policy.', analytics=True, knowledge=True, days=30, top_k=4), {'model': 'mock'}))
    monkeypatch.setattr(knowledge_service, 'retrieve', lambda *args: [SOURCE.copy()])
    monkeypatch.setattr(provider, 'explain', lambda *args: (provider.GroundedOutput(sufficient=True,
        claims=[provider.EvidenceClaim(explanation='Check the documented refund submission window.', source_id='chunk-1', quote=SOURCE['passage'])]), {'model': 'mock'}))


@pytest.fixture
def client(database, monkeypatch):
    app.dependency_overrides[get_session] = lambda: database
    monkeypatch.setattr(service, 'session_factory', lambda: Session(database.get_bind()))
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def create(client, headers=HEADERS, task='Investigate overall complaints and refund policy'):
    response = client.post('/api/agent/runs', headers=headers, json={'task': task, 'provider_consent': True})
    assert response.status_code == 202, response.text
    return response.json()['id']


def status(client, run_id, headers=HEADERS):
    response = client.get('/api/agent/runs/' + run_id, headers=headers)
    assert response.status_code == 200
    return response.json()


def test_workflow_real_analytics_and_citations(client, database):
    run_id = create(client)
    run = status(client, run_id)
    assert run['status'] == 'completed', run
    assert [step['tool'] for step in run['steps']] == ['planning', 'complaint_analytics', 'knowledge_retrieval', 'report_generation']
    assert all(step['status'] == 'completed' for step in run['steps'])
    report = client.get(f'/api/agent/runs/{run_id}/result', headers=HEADERS).json()
    assert report['database_facts']['total'] == 1
    assert report['database_facts']['counts']['open'] == 1
    assert sum(row['complaints'] for row in report['database_facts']['trends']) == 1
    assert report['document_findings']['sources'][0]['passage'] == SOURCE['passage']
    assert report['document_findings']['sources'][0]['page_number'] == 2
    assert report['human_verified'] is False
    database.expire_all()
    assert database.get(Complaint, 'CMP-1').category == 'original'
    assert database.get(Complaint, 'CMP-1').priority == 'low'
    assert client.get('/api/agent/runs', headers=HEADERS).headers['cache-control'] == 'no-store'


@pytest.mark.parametrize('path,method', [('', 'get'), ('/result', 'get'), ('/cancel', 'post')])
def test_other_workspace_cannot_read_or_cancel(client, path, method):
    run_id = create(client)
    assert getattr(client, method)(f'/api/agent/runs/{run_id}{path}', headers=BETA).status_code == 404
    assert client.get('/api/agent/runs', headers=BETA).json() == {'items': []}
    assert client.get('/api/agent/runs').status_code == 401


def test_analytics_authorization_at_tool_boundary(client):
    run = status(client, create(client, BETA), BETA)
    assert run['status'] == 'failed'
    assert run['error_code'] == 'analytics_not_authorized'
    assert run['steps'][1]['output'] is None


def test_revoked_key_stops_worker(client, monkeypatch):
    def revoke(task):
        monkeypatch.setenv('KB_WORKSPACE_KEYS_JSON', json.dumps({'alpha': 'c' * 32}))
        return planner.Plan(supported=True, reason='Read facts', analytics=True, knowledge=False, days=30, top_k=4), {}
    monkeypatch.setattr(service, 'plan_task', revoke)
    run_id = create(client)
    run = status(client, run_id, {'X-Workspace-Key': 'c' * 32})
    assert run['error_code'] == 'workspace_authorization_failed'
    assert run['steps'][0]['output'] is None


def test_empty_evidence_and_no_complaints(client, database, monkeypatch):
    database.execute(delete(Complaint)); database.commit()
    monkeypatch.setattr(knowledge_service, 'retrieve', lambda *args: [])
    run = status(client, create(client))
    assert run['status'] == 'completed'
    assert run['result']['status'] == 'insufficient_evidence'
    assert run['result']['document_findings']['sources'] == []
    assert run['result']['database_facts']['total'] == 0


@pytest.mark.parametrize('source_id,quote', [('invented-id', SOURCE['passage']), ('chunk-1', 'Invented policy that is not in any document.')])
def test_citations_must_match_retrieved_passages(client, monkeypatch, source_id, quote):
    monkeypatch.setattr(provider, 'explain', lambda *args: (provider.GroundedOutput(sufficient=True,
        claims=[provider.EvidenceClaim(explanation='Unsupported', source_id=source_id, quote=quote)]), {}))
    run = status(client, create(client))
    assert run['status'] == 'failed' and run['error_code'] == 'invalid_citation'
    assert run['steps'][-1]['attempts'] == 1
    assert run['result'] is None


def test_model_insufficient_evidence(client, monkeypatch):
    monkeypatch.setattr(provider, 'explain', lambda *args: (provider.GroundedOutput(sufficient=False, claims=[]), {}))
    run = status(client, create(client))
    assert run['result']['status'] == 'insufficient_evidence'
    assert run['result']['document_findings']['sources'] == []


@pytest.mark.parametrize('code,attempts', [('provider_rate_limited', 2), ('provider_timeout', 2),
                                         ('provider_unavailable', 2), ('invalid_embedding', 1)])
def test_bounded_transient_retries(client, monkeypatch, code, attempts):
    def fail(*args):
        raise IntelligenceError(code)
    monkeypatch.setattr(knowledge_service, 'retrieve', fail)
    run = status(client, create(client))
    assert run['status'] == 'failed' and run['error_code'] == code
    assert run['steps'][2]['attempts'] == attempts
    assert run['steps'][3]['attempts'] == 0


def test_transient_retry_recovers(client, monkeypatch):
    calls = []
    def retrieve(*args):
        calls.append(1)
        if len(calls) == 1:
            raise IntelligenceError('provider_unavailable')
        return [SOURCE]
    monkeypatch.setattr(knowledge_service, 'retrieve', retrieve)
    run = status(client, create(client))
    assert run['status'] == 'completed' and run['steps'][2]['attempts'] == 2


def test_cancel_and_duplicate_delivery_do_not_execute(client, monkeypatch):
    monkeypatch.setattr(service, 'execute_run', lambda *args: None)
    run_id = create(client)
    assert status(client, run_id)['status'] == 'queued'
    assert client.get(f'/api/agent/runs/{run_id}/result', headers=HEADERS).status_code == 409
    assert client.post(f'/api/agent/runs/{run_id}/cancel', headers=HEADERS).json()['status'] == 'cancelled'
    REAL_EXECUTE(run_id, 'a' * 32, service.settings())
    assert status(client, run_id)['steps'][0]['attempts'] == 0


def test_cancel_during_tool_discards_late_output(client, monkeypatch):
    def retrieve(*args):
        with service.session_factory() as session:
            run = session.scalar(select(AgentRun))
            service.finish(session, run, 'cancelled', 'cancelled_by_user')
        return [SOURCE]
    monkeypatch.setattr(knowledge_service, 'retrieve', retrieve)
    run = status(client, create(client))
    assert run['status'] == 'cancelled' and run['steps'][2]['output'] is None
    assert run['steps'][3]['attempts'] == 0


def test_deadline_discards_late_tool_result(client, monkeypatch):
    def retrieve(*args):
        with service.session_factory() as session:
            run = session.scalar(select(AgentRun)); run.expires_at = time.time() - 1; session.commit()
        return [SOURCE]
    monkeypatch.setattr(knowledge_service, 'retrieve', retrieve)
    run = status(client, create(client))
    assert run['status'] == 'timed_out' and run['error_code'] == 'agent_timeout'
    assert run['steps'][2]['output'] is None


def test_restart_or_orphaned_run_expires_on_read(client, database, monkeypatch):
    monkeypatch.setattr(service, 'execute_run', lambda *args: None)
    run_id = create(client)
    run = database.get(AgentRun, run_id); run.expires_at = time.time() - 1; database.commit()
    assert status(client, run_id)['status'] == 'timed_out'


def test_step_limit_and_unsupported_request(client, monkeypatch):
    monkeypatch.setenv('AGENT_MAX_STEPS', '2')
    assert status(client, create(client))['error_code'] == 'agent_step_limit'
    monkeypatch.setattr(service, 'plan_task', lambda task: (planner.Plan(
        supported=False, reason='External actions are unavailable.', analytics=False, knowledge=False, days=30, top_k=4), {}))
    run = status(client, create(client, task='Send refunds and email every customer'))
    assert run['error_code'] == 'unsupported_investigation' and len(run['steps']) == 1


@pytest.mark.parametrize('name,args', [('shell', {'command': 'whoami'}), ('complaint_analytics', {'days': '30'}),
                                     ('complaint_analytics', {'days': 367}), ('knowledge_retrieval', {'question': 'refund', 'top_k': 6}),
                                     ('report_generation', {'sql': 'DELETE FROM complaints'})])
def test_registry_rejects_unregistered_tools_and_invalid_arguments(name, args):
    with pytest.raises(IntelligenceError):
        agent_tools.validate_call(name, args)


def test_body_limits_consent_capacity_and_input_validation(client, monkeypatch):
    assert client.post('/api/agent/runs', headers=HEADERS, json={'task': '   ', 'provider_consent': True}).status_code == 422
    assert client.post('/api/agent/runs', headers=HEADERS, json={'task': 'refunds', 'provider_consent': False}).status_code == 422
    assert client.post('/api/agent/runs', headers=HEADERS, json={'task': 'refunds', 'provider_consent': True, 'workspace': 'beta'}).status_code == 422
    assert client.post('/api/agent/runs', headers=HEADERS, content=b'x' * 9000).status_code == 413
    monkeypatch.setattr(service, 'execute_run', lambda *args: None)
    create(client); create(client)
    assert client.post('/api/agent/runs', headers=HEADERS, json={'task': 'refunds', 'provider_consent': True}).status_code == 429


def test_planner_payload_schema_and_privacy(monkeypatch):
    captured = []
    def post(url, payload, key):
        captured.append(payload)
        return {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps({
            'supported': True, 'reason': 'Read facts', 'analytics': True, 'knowledge': False, 'days': 30, 'top_k': 4})}}]}
    monkeypatch.setattr(provider, 'post_json', post)
    task = planner.redact_task('Review refund for alice@example.com +91 9876543210 https://private.test')
    plan, metadata = REAL_PLAN(task)
    assert plan.analytics and metadata['prompt_version'] == 'agent-plan-v1'
    payload = json.dumps(captured)
    assert 'alice@example.com' not in payload and '9876543210' not in payload
    assert captured[0]['store'] is False and captured[0]['response_format']['json_schema']['strict'] is True


@pytest.mark.parametrize('body', [{}, {'choices': []}, {'choices': [{'finish_reason': 'length', 'message': {}}]},
    {'choices': [{'finish_reason': 'stop', 'message': {'content': '{"tool":"shell"}'}}]},
    {'choices': [{'finish_reason': 'stop', 'message': {'refusal': 'no', 'content': '{}'}}]}])
def test_invalid_planner_outputs(monkeypatch, body):
    monkeypatch.setattr(provider, 'post_json', lambda *args: body)
    with pytest.raises(IntelligenceError, match='invalid_agent_plan'):
        REAL_PLAN('Refund policies')


def test_missing_provider_configuration_and_deadline(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY')
    with pytest.raises(IntelligenceError, match='missing_agent_configuration'):
        REAL_PLAN('Refund policies')
    token = deadline.set(time.time() - 1)
    try:
        with pytest.raises(IntelligenceError, match='agent_timeout'):
            remaining()
    finally:
        deadline.reset(token)


def test_unexpected_tool_error_is_sanitized(client, monkeypatch):
    def fail(*args):
        raise RuntimeError('secret database password and provider content')
    monkeypatch.setattr(knowledge_service, 'retrieve', fail)
    run = status(client, create(client))
    assert run['error_code'] == 'agent_internal_error'
    assert 'secret database' not in json.dumps(run)


def test_invalid_configuration_fails_without_dispatch(client, monkeypatch):
    monkeypatch.setenv('AGENT_TIMEOUT_SECONDS', '0')
    response = client.post('/api/agent/runs', headers=HEADERS, json={'task': 'Refunds', 'provider_consent': True})
    assert response.status_code == 503
    assert response.json()['detail']['code'] == 'invalid_agent_configuration'


def test_analytics_permission_is_checked_again_during_report(client, monkeypatch):
    def retrieve(*args):
        monkeypatch.setenv('KB_ANALYTICS_WORKSPACE', 'beta')
        return [SOURCE]
    monkeypatch.setattr(knowledge_service, 'retrieve', retrieve)
    run = status(client, create(client))
    assert run['steps'][1]['status'] == 'completed'
    assert run['steps'][-1]['error_code'] == 'analytics_not_authorized'
    assert run['result'] is None


def test_completed_run_cannot_execute_twice(client, monkeypatch):
    run_id = create(client)
    def forbidden(*args):
        pytest.fail('Completed run must not call a provider again')
    monkeypatch.setattr(service, 'plan_task', forbidden)
    REAL_EXECUTE(run_id, 'a' * 32, service.settings())
    assert status(client, run_id)['status'] == 'completed'
