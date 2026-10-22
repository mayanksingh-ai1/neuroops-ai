"""Real HTTP smoke checks against a newly created disposable PostgreSQL database.

Run from backend with TEST_POSTGRES_URL set to an isolated test PostgreSQL server.
Requires permission to create/drop a database. Never uses the application's .env DB.
"""
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
from uuid import uuid4
import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def main():
    source = os.environ.get('TEST_POSTGRES_URL')
    if not source:
        raise SystemExit('Set TEST_POSTGRES_URL to a disposable local PostgreSQL server.')
    source_url = make_url(source)
    if source_url.host not in ('127.0.0.1', 'localhost'):
        raise SystemExit('Smoke tests require an explicit local test server.')
    database = 'neuroops_smoke_' + uuid4().hex
    admin = create_engine(source, isolation_level='AUTOCOMMIT')
    process = None
    log = None
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{database}"'))
    try:
        access_token = secrets.token_urlsafe(36)
        env = {**os.environ, 'APP_ENV': 'production', 'AUTH_REQUIRED': 'false',
               'DATABASE_URL': source_url.set(database=database).render_as_string(hide_password=False),
               'AUTH_USERS_JSON': json.dumps({'smoke': {'token_sha256': hashlib.sha256(access_token.encode()).hexdigest(),
                    'role': 'viewer', 'workspace': 'smoke'}}), 'KB_ANALYTICS_WORKSPACE': 'smoke',
               'CORS_ORIGINS_JSON': '[]', 'OPENAI_API_KEY': ''}
        subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], env=env, check=True)
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0)); port = listener.getsockname()[1]
        log = open(os.devnull, 'w')
        process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1',
            '--port', str(port), '--no-access-log', '--no-proxy-headers'], env=env, stdout=log, stderr=log)
        with httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=5) as client:
            for attempt in range(40):
                try:
                    if client.get('/api/ready').status_code == 200:
                        break
                except httpx.RequestError:
                    pass
                time.sleep(.25)
            else:
                raise AssertionError('API did not become ready.')
            checks = [
                ('health', client.get('/api/health'), 200),
                ('readiness', client.get('/api/ready'), 200),
                ('anonymous complaint denial', client.get('/api/complaints'), 401),
                ('anonymous dataset denial', client.get('/api/evaluation/cases'), 401),
            ]
            headers = {'Authorization': 'Bearer ' + access_token}
            checks += [
                ('authenticated complaint read', client.get('/api/complaints', headers=headers), 200),
                ('viewer write denial', client.post('/api/complaints/import', headers=headers), 403),
                ('viewer metrics denial', client.get('/api/metrics', headers=headers), 403),
                ('production docs disabled', client.get('/docs', headers=headers), 404),
                ('session metadata', client.get('/api/auth/session', headers=headers), 200),
            ]
            for name, response, expected in checks:
                assert response.status_code == expected, (name, response.status_code)
                assert response.headers.get('x-request-id')
                assert access_token not in response.text
                print(f'PASS: {name} ({expected})')
            print('9 HTTP smoke checks passed; schema migrated to 0006.')
    finally:
        if process:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait()
        if log:
            log.close()
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{database}" WITH (FORCE)'))
        admin.dispose()


if __name__ == '__main__':
    main()
