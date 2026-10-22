"""Low-cardinality operational signals. Never log bodies, queries, headers, or SQL."""
import json
import logging
import threading
import time
from collections import Counter
from uuid import uuid4
from fastapi import HTTPException
from starlette.responses import JSONResponse
from sqlalchemy import text
from .database import get_engine

logger = logging.getLogger('neuroops.requests')
counts = Counter()
duration = 0.0
lock = threading.Lock()


def readiness():
    try:
        with get_engine().connect() as connection:
            connection.execute(text('SELECT 1'))
            revision = connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one()
        if revision != '0006':
            raise ValueError()
        from .security import required, users
        if required():
            users()
        return {'status': 'ready', 'database': 'ok', 'schema': 'current'}
    except Exception:
        raise HTTPException(503, {'code': 'not_ready'}) from None


def metrics():
    with lock:
        return {'scope': 'This API process; resets on restart', 'requests': dict(counts),
                'duration_seconds_total': round(duration, 3)}


class RequestTelemetry:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        global duration
        request_id, start, status, started = str(uuid4()), time.monotonic(), 500, False
        async def capture(message):
            nonlocal status, started
            if message['type'] == 'http.response.start':
                started = True
                status = message['status']
                headers = list(message.get('headers', []))
                existing = {k.lower() for k, _ in headers}
                headers.append((b'x-request-id', request_id.encode()))
                headers.append((b'x-content-type-options', b'nosniff'))
                if b'cache-control' not in existing:
                    headers.append((b'cache-control', b'no-store'))
                message['headers'] = headers
            await send(message)
        try:
            await self.app(scope, receive, capture)
        except Exception:
            # No raw exception/traceback: database/provider messages can contain private data.
            if not started:
                await JSONResponse({'detail': {'code': 'internal_error'}, 'request_id': request_id}, status_code=500)(scope, receive, capture)
        finally:
            elapsed = time.monotonic() - start
            with lock:
                counts[str(status)] += 1
                duration += elapsed
            route = getattr(scope.get('route'), 'path', 'unmatched')
            logger.info(json.dumps({'event': 'http_request', 'request_id': request_id,
                'method': scope['method'] if scope['method'] in ('GET', 'POST', 'OPTIONS', 'HEAD') else 'other',
                'route': route, 'status': status, 'duration_ms': round(elapsed * 1000, 2)}))
