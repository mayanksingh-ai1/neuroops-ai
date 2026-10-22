import json
import os
from uuid import uuid4
from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from alembic import command
from alembic.config import Config

from app import intelligence as ai
from app.database import get_session
from app.main import app
from app.models import Complaint, ComplaintAnalysis


@pytest.fixture(autouse=True)
def configuration(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key-not-real')
    monkeypatch.setenv('LLM_MODEL', 'mock-model')
    monkeypatch.setenv('IMPORT_API_KEY', 'x' * 32)
    monkeypatch.delenv('AI_RULES_JSON', raising=False)
    monkeypatch.delenv('MOCK_LLM_PROVIDER', raising=False)


def provider(monkeypatch, status=200, output=None, finish='stop', refusal=None):
    captured = []
    original_post = httpx.Client.post
    def post(self, url, **kwargs):
        if url != 'https://api.openai.com/v1/chat/completions':
            return original_post(self, url, **kwargs)
        captured.append(kwargs['json'])
        return httpx.Response(status, json={
            'model': 'mock-model-v1',
            'choices': [{'finish_reason': finish, 'message': {
                'content': json.dumps(output or {'category': 'Refund Issue', 'sentiment': 'Negative'}),
                'refusal': refusal,
            }}],
        })
    monkeypatch.setattr(httpx.Client, 'post', post)
    return captured


def test_provider_validates_and_sends_only_minimized_text(monkeypatch):
    captured = provider(monkeypatch)
    text = ai.minimize_text('Alice alice@example.com https://site.test refund pending 9876543210')
    result, metadata = ai.classify(text, ai.settings())
    assert text == 'refund pending'
    assert captured[0]['messages'][1]['content'] == text
    assert captured[0]['store'] is False
    assert result.sentiment == 'Negative'
    assert metadata['returned_model'] == 'mock-model-v1'


@pytest.mark.parametrize('status,code', [(429, 'rate_limited'), (401, 'provider_authentication'),
                                        (403, 'provider_authentication'), (500, 'provider_error')])
def test_provider_http_errors(monkeypatch, status, code):
    provider(monkeypatch, status)
    with pytest.raises(ai.IntelligenceError, match=code):
        ai.classify('refund', ai.settings())


@pytest.mark.parametrize('exception,code', [
    (httpx.ReadTimeout('secret'), 'provider_timeout'),
    (httpx.ConnectError('secret'), 'provider_unavailable'),
])
def test_network_errors_do_not_leak_provider_details(monkeypatch, exception, code):
    def fail(*args, **kwargs):
        raise exception
    monkeypatch.setattr(httpx.Client, 'post', fail)
    with pytest.raises(ai.IntelligenceError, match=code):
        ai.classify('refund', ai.settings())


@pytest.mark.parametrize('output', [
    {'category': 'invented', 'sentiment': 'Negative'},
    {'category': 'Refund Issue', 'sentiment': 'angry'},
    {'category': 'Refund Issue', 'sentiment': 'Negative', 'confidence': 0.99},
    {'category': 'Refund Issue'},
])
def test_invalid_output(monkeypatch, output):
    provider(monkeypatch, output=output)
    with pytest.raises(ai.IntelligenceError, match='invalid_model_output'):
        ai.classify('refund', ai.settings())


@pytest.mark.parametrize('finish,refusal', [('length', None), ('stop', 'refused')])
def test_refusals_and_truncation(monkeypatch, finish, refusal):
    provider(monkeypatch, finish=finish, refusal=refusal)
    with pytest.raises(ai.IntelligenceError, match='invalid_model_output'):
        ai.classify('refund', ai.settings())


@pytest.mark.parametrize('name,code', [('OPENAI_API_KEY', 'missing_api_key'), ('LLM_MODEL', 'missing_model')])
def test_missing_configuration(monkeypatch, name, code):
    monkeypatch.delenv(name)
    with pytest.raises(ai.IntelligenceError, match=code):
        ai.classify('refund', ai.settings())


def test_rules_and_invalid_configuration(monkeypatch):
    rules = ai.Settings(negative_priority='high')
    assert ai.assess_priority('not unsafe', 'Positive', rules) == ('high', 'safety_keyword')
    assert ai.assess_priority('refund', 'Negative', rules) == ('high', 'negative_sentiment')
    assert ai.assess_priority('good', 'Positive', rules) == ('low', 'default')
    monkeypatch.setenv('AI_RULES_JSON', '{"high_priority_terms":["secret-name"]}')
    with pytest.raises(ai.IntelligenceError, match='invalid_configuration'):
        ai.settings()


@pytest.mark.parametrize('body', [b'not json', b'{"choices":[{"finish_reason":"stop","message":[]}]}'])
def test_malformed_provider_envelope(monkeypatch, body):
    monkeypatch.setattr(httpx.Client, 'post', lambda *args, **kwargs: httpx.Response(200, content=body))
    with pytest.raises(ai.IntelligenceError, match='invalid_model_output'):
        ai.classify('refund', ai.settings())


@pytest.fixture()
def database():
    # Execute real migration functions, not just metadata.create_all().
    postgres = os.getenv('TEST_POSTGRES_URL')
    schema = 'neuroops_test_' + uuid4().hex
    if postgres:
        admin = create_engine(postgres)
        with admin.begin() as connection:
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        engine = create_engine(postgres, connect_args={'options': f'-csearch_path={schema}'})
    else:
        engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
    with engine.begin() as connection:
        config = Config('alembic.ini')
        config.attributes['connection'] = connection
        command.upgrade(config, '0001')
    with Session(engine) as session:
        session.add(Complaint(complaint_id='CMP-1', title='Refund pending', category='original',
                              status='open', priority='low', channel='email', received_date=date.today()))
        session.commit()
        # Upgrade a populated Phase 2 database; the original row must survive.
        with engine.begin() as connection:
            config.attributes['connection'] = connection
            command.upgrade(config, 'head')
        yield session
    engine.dispose()
    if postgres:
        with admin.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
        admin.dispose()


@pytest.fixture()
def client(database):
    def override():
        yield database
    app.dependency_overrides[get_session] = override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


HEADERS = {'X-Import-Key': 'x' * 32}


def test_single_history_and_dashboard_preserve_original(client, database, monkeypatch):
    provider(monkeypatch)
    for _ in range(2):
        response = client.post('/api/complaints/CMP-1/classify', headers=HEADERS)
        assert response.status_code == 200
        assert response.json()['human_verified'] is False
    assert len(database.scalars(select(ComplaintAnalysis)).all()) == 2
    row = client.get('/api/complaints').json()['items'][0]
    assert row['category'] == 'original' and row['priority'] == 'low'
    assert row['analysis']['category'] == 'Refund Issue'
    assert row['analysis']['priority'] == 'medium'


def test_failed_attempt_stored_without_fake_classification(client, monkeypatch):
    provider(monkeypatch, 429)
    response = client.post('/api/complaints/CMP-1/classify', headers=HEADERS)
    assert response.status_code == 429
    row = client.get('/api/complaints').json()['items'][0]['analysis']
    assert row['status'] == 'failed' and row['category'] is None
    assert row['error_code'] == 'rate_limited'


def test_batch_validation_auth_and_missing_ids(client, monkeypatch):
    captured = provider(monkeypatch)
    assert client.post('/api/complaints/CMP-1/classify').status_code == 401
    assert client.post('/api/complaints/UNKNOWN/classify', headers=HEADERS).status_code == 404
    for ids in ([], ['CMP-1'] * 6, ['bad id']):
        assert client.post('/api/complaints/classify-batch', headers=HEADERS,
                           json={'complaint_ids': ids}).status_code == 422
    result = client.post('/api/complaints/classify-batch', headers=HEADERS,
                         json={'complaint_ids': ['CMP-1', 'CMP-1', 'UNKNOWN']})
    assert result.status_code == 200
    assert [row['status'] for row in result.json()['items']] == ['completed', 'not_found']
    assert len(captured) == 1


def test_no_domain_text_does_not_call_provider(client, database, monkeypatch):
    captured = provider(monkeypatch)
    database.get(Complaint, 'CMP-1').title = 'Alice 123'
    database.commit()
    assert client.post('/api/complaints/CMP-1/classify', headers=HEADERS).status_code == 422
    assert captured == []


def test_mock_llm_provider_classification(client, database, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('LLM_MODEL', raising=False)
    monkeypatch.setenv('MOCK_LLM_PROVIDER', 'true')
    # Should classify deterministically without any httpx client call
    response = client.post('/api/complaints/CMP-1/classify', headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'completed'
    assert data['category'] == 'Refund Issue'
    assert data['sentiment'] == 'Neutral'
    assert data['details']['provider'] == 'mock'
    assert data['details']['returned_model'] == 'mock-demo-v1'
    # Also verify batch endpoint with mock mode
    batch_res = client.post('/api/complaints/classify-batch', headers=HEADERS, json={'complaint_ids': ['CMP-1']})
    assert batch_res.status_code == 200
    assert batch_res.json()['items'][0]['status'] == 'completed'
