"""Phase 7 operations, security, telemetry, and background maintenance tests."""
import hashlib
import json
import os
import time
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from app.main import app
from app.security import AccessControl, authenticate, required, users
from app.operations import readiness, metrics
from app.job_maintenance import expire_evaluations
from app.evaluation_models import EvaluationCase, Evaluation
from app.agent_models import AgentRun, AgentStep
from app.agent_service import finish
from test_intelligence import database, client


TOKEN_ADMIN = 'a' * 48
TOKEN_OPERATOR = 'b' * 48
TOKEN_REVIEWER = 'c' * 48
TOKEN_VIEWER = 'd' * 48

HASH_ADMIN = hashlib.sha256(TOKEN_ADMIN.encode()).hexdigest()
HASH_OPERATOR = hashlib.sha256(TOKEN_OPERATOR.encode()).hexdigest()
HASH_REVIEWER = hashlib.sha256(TOKEN_REVIEWER.encode()).hexdigest()
HASH_VIEWER = hashlib.sha256(TOKEN_VIEWER.encode()).hexdigest()

SAMPLE_USERS = {
    'admin_user': {'token_sha256': HASH_ADMIN, 'role': 'admin', 'workspace': 'workspace_a'},
    'operator_user': {'token_sha256': HASH_OPERATOR, 'role': 'operator', 'workspace': 'workspace_a'},
    'reviewer_user': {'token_sha256': HASH_REVIEWER, 'role': 'reviewer', 'workspace': 'workspace_a'},
    'viewer_user': {'token_sha256': HASH_VIEWER, 'role': 'viewer', 'workspace': 'workspace_a'},
}


def test_health_check(client):
    response = client.get('/api/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok', 'service': 'neuroops-api'}
    assert 'x-request-id' in response.headers
    assert response.headers['x-content-type-options'] == 'nosniff'


def test_auth_config_endpoint(client):
    response = client.get('/api/auth/config')
    assert response.status_code == 200
    assert 'required' in response.json()


def test_request_telemetry_and_metrics(client):
    res = client.get('/api/health')
    assert res.status_code == 200
    m = metrics()
    assert 'requests' in m
    assert '200' in m['requests']
    assert m['duration_seconds_total'] >= 0


def test_validation_error_strips_sensitive_input(client, monkeypatch):
    monkeypatch.setenv('KB_WORKSPACE_KEYS_JSON', json.dumps({'workspace_a': 'k' * 32}))
    # Send invalid JSON to trigger 422 RequestValidationError
    response = client.post('/api/knowledge/ask',
                           headers={'X-Workspace-Key': 'k' * 32, 'Content-Type': 'application/json'},
                           json={'question': 12345, 'super_secret_leak': 'leaked_data'})
    assert response.status_code == 422
    body = response.json()
    assert 'detail' in body
    # Confirm no raw input values leaked
    for err in body['detail']:
        assert 'input' not in err


def test_auth_users_configuration_validation(monkeypatch):
    monkeypatch.setenv('AUTH_USERS_JSON', 'invalid json')
    with pytest.raises(Exception):
        users()

    monkeypatch.setenv('AUTH_USERS_JSON', '{}')
    with pytest.raises(Exception):
        users()

    # Valid users config
    monkeypatch.setenv('AUTH_USERS_JSON', json.dumps(SAMPLE_USERS))
    loaded = users()
    assert len(loaded) == 4
    assert loaded['admin_user']['role'] == 'admin'


def test_token_authentication_success_and_failure(monkeypatch):
    monkeypatch.setenv('AUTH_USERS_JSON', json.dumps(SAMPLE_USERS))

    # Valid token
    ident = authenticate(f'Bearer {TOKEN_ADMIN}')
    assert ident['id'] == 'admin_user'
    assert ident['role'] == 'admin'

    # Invalid token length
    with pytest.raises(Exception):
        authenticate('Bearer short')

    # Non-bearer prefix
    with pytest.raises(Exception):
        authenticate(f'Basic {TOKEN_ADMIN}')

    # Unknown token
    with pytest.raises(Exception):
        authenticate(f'Bearer {"z" * 48}')


def test_role_based_access_control(monkeypatch, client):
    monkeypatch.setenv('AUTH_REQUIRED', 'true')
    monkeypatch.setenv('AUTH_USERS_JSON', json.dumps(SAMPLE_USERS))
    monkeypatch.setenv('KB_WORKSPACE_KEYS_JSON', json.dumps({'workspace_a': 'w' * 48, 'workspace_b': 'x' * 48}))
    monkeypatch.setenv('KB_ANALYTICS_WORKSPACE', 'workspace_a')

    # Unauthenticated request rejected
    res = client.get('/api/complaints')
    assert res.status_code == 401

    # Viewer role: GET complaints succeeds
    viewer_headers = {'Authorization': f'Bearer {TOKEN_VIEWER}'}
    res = client.get('/api/complaints', headers=viewer_headers)
    assert res.status_code == 200

    # Viewer role: POST /api/complaints/import rejected with 403
    res = client.post('/api/complaints/import', headers={**viewer_headers, 'Content-Type': 'text/csv'})
    assert res.status_code == 403

    # Operator role: cannot post reviews
    op_headers = {'Authorization': f'Bearer {TOKEN_OPERATOR}', 'X-Workspace-Key': 'w' * 48}
    res = client.post('/api/evaluation/results/eval-1/reviews', headers=op_headers, json={'decision': 'approve', 'feedback': 'ok', 'corrections': {}})
    assert res.status_code == 403

    # Reviewer role: cannot post other endpoints (e.g. create cases)
    rev_headers = {'Authorization': f'Bearer {TOKEN_REVIEWER}', 'X-Workspace-Key': 'w' * 48}
    res = client.post('/api/evaluation/cases', headers=rev_headers, json={'dataset': 'd', 'model': 'm', 'question': 'q', 'response': 'r'})
    assert res.status_code == 403

    # Metrics endpoint: non-admin gets 403, admin gets 200
    res = client.get('/api/metrics', headers=op_headers)
    assert res.status_code == 403

    admin_headers = {'Authorization': f'Bearer {TOKEN_ADMIN}'}
    res = client.get('/api/metrics', headers=admin_headers)
    assert res.status_code == 200

    # Workspace isolation: workspace mismatch between bearer token (workspace_a) and header (workspace_b)
    mismatch_headers = {'Authorization': f'Bearer {TOKEN_ADMIN}', 'X-Workspace-Key': 'x' * 48}
    res = client.get('/api/knowledge/documents', headers=mismatch_headers)
    assert res.status_code == 403


def test_job_maintenance_sweep_expires_evaluations(database):
    now = time.time()
    case = EvaluationCase(
        id=str(uuid4()), workspace_id='ws_test', fingerprint=str(uuid4()),
        dataset='d', model='m', provider='p', question='q', response='r',
        reference=None, context={'evidence': [], 'citations': []}, created_at=now
    )
    database.add(case)
    database.flush()

    evaluation = Evaluation(
        id=str(uuid4()), case_id=case.id, status='running',
        expires_at=now - 10, deterministic={}, judged={}, rubric={}, evaluator={},
        error_code=None, created_at=now - 60
    )
    database.add(evaluation)
    database.commit()

    # Expire pending evaluations
    expire_evaluations(database)

    database.refresh(evaluation)
    assert evaluation.status == 'failed'
    assert evaluation.error_code == 'evaluation_timeout'


def test_job_maintenance_sweep_expires_agent_runs(database):
    now = time.time()
    run = AgentRun(
        id=str(uuid4()), workspace_id='ws_test', task='Investigate something',
        status='running', created_at=now - 100, expires_at=now - 10
    )
    database.add(run)
    database.flush()
    step = AgentStep(run_id=run.id, position=0, tool='planning', arguments={}, status='running')
    database.add(step)
    database.commit()

    if run.expires_at <= time.time():
        finish(database, run, 'timed_out', 'agent_timeout')

    database.refresh(run)
    database.refresh(step)
    assert run.status == 'timed_out'
    assert run.error_code == 'agent_timeout'
    assert step.status == 'timed_out'


def test_production_cannot_disable_auth(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'Production')
    monkeypatch.setenv('AUTH_REQUIRED', 'false')
    assert required() is True
    monkeypatch.setenv('APP_ENV', 'typo-production')
    assert required() is True


def test_provider_attempt_persisted_before_call(client, database, monkeypatch):
    from app import evaluation_provider
    from sqlalchemy import select
    monkeypatch.setenv('KB_WORKSPACE_KEYS_JSON', json.dumps({'alpha': 'k' * 32}))
    headers = {'X-Workspace-Key': 'k' * 32}
    case = client.post('/api/evaluation/cases', headers=headers, json={
        'model': 'mock', 'question': 'Refund window?', 'response': 'Thirty days'}).json()['case']
    def fail(case):
        running = database.scalar(select(Evaluation).where(Evaluation.case_id == case.id))
        assert running.status == 'running' and running.expires_at > time.time()
        raise RuntimeError('provider-secret-should-not-leak')
    monkeypatch.setattr(evaluation_provider, 'judge', fail)
    result = client.post(f"/api/evaluation/cases/{case['id']}/evaluate", headers=headers,
                         json={'use_judge': True, 'provider_consent': True})
    assert result.status_code == 201
    assert result.json()['error_code'] == 'evaluation_internal_error'
    assert 'provider-secret' not in result.text


def test_request_logs_exclude_private_queries_and_credentials(client, caplog):
    import logging
    with caplog.at_level(logging.INFO, logger='neuroops.requests'):
        response = client.get('/api/health?private=private-query', headers={'Authorization': 'Bearer private-token'})
    assert response.status_code == 200
    logs = '\n'.join(record.message for record in caplog.records if record.name == 'neuroops.requests')
    assert 'http_request' in logs and '/api/health' in logs
    assert 'private-query' not in logs and 'private-token' not in logs


def test_token_rotation_revokes_inflight_principal(monkeypatch):
    from app.security import principal, check_principal
    from fastapi import HTTPException
    monkeypatch.setenv('AUTH_REQUIRED', 'true')
    monkeypatch.setenv('AUTH_USERS_JSON', json.dumps(SAMPLE_USERS))
    token = principal.set(authenticate('Bearer ' + TOKEN_ADMIN))
    try:
        updated = json.loads(json.dumps(SAMPLE_USERS))
        updated['admin_user']['token_sha256'] = 'f' * 64
        monkeypatch.setenv('AUTH_USERS_JSON', json.dumps(updated))
        with pytest.raises(HTTPException) as error:
            check_principal()
        assert error.value.status_code == 403
    finally:
        principal.reset(token)


def test_readiness_checks_schema_without_exposing_errors(database, monkeypatch):
    from app import operations
    from fastapi import HTTPException
    monkeypatch.setattr(operations, 'get_engine', lambda: database.get_bind())
    assert readiness()['schema'] == 'current'
    database.execute(text("UPDATE alembic_version SET version_num='0005'")); database.commit()
    with pytest.raises(HTTPException) as error:
        readiness()
    assert error.value.status_code == 503 and error.value.detail == {'code': 'not_ready'}


def test_maintenance_expires_agent_without_status_poll(database, monkeypatch):
    from app import job_maintenance
    run = AgentRun(workspace_id='alpha', task='Read facts', status='running', created_at=time.time()-200, expires_at=time.time()-10)
    database.add(run); database.flush()
    step = AgentStep(run_id=run.id, position=0, tool='planning', arguments={}, status='running')
    database.add(step); database.commit()
    monkeypatch.setattr(job_maintenance, 'get_engine', lambda: database.get_bind())
    job_maintenance.sweep()
    database.refresh(run); database.refresh(step)
    assert run.status == step.status == 'timed_out'


def test_database_exception_is_sanitized(client, monkeypatch):
    from app import routes
    from app.database import get_session
    def broken():
        raise RuntimeError('postgresql://private-password@host private-query')
        yield
    app.dependency_overrides[get_session] = broken
    response = client.get('/api/complaints')
    assert response.status_code == 500
    assert response.json()['detail']['code'] == 'internal_error'
    assert 'private-password' not in response.text


def test_compose_and_containers_use_safe_defaults():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    compose = (root / 'docker-compose.yml').read_text(encoding='utf-8-sig')
    assert 'local_dev_only_change_me' not in compose
    assert 'APP_ENV: production' in compose and 'service_completed_successfully' in compose
    assert '127.0.0.1:5432' not in compose and '127.0.0.1:8000' not in compose
    assert 'USER 10001:10001' in (root / 'backend/Dockerfile').read_text()
    assert 'nginx-unprivileged' in (root / 'frontend/Dockerfile').read_text()
