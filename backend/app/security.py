"""Production access tokens supplement existing workspace/import/reviewer capabilities."""
import hashlib
import json
import os
import re
import secrets
from contextvars import ContextVar
from fastapi import HTTPException
from starlette.responses import JSONResponse
from .knowledge_config import workspace, limit_requests
from .intelligence import IntelligenceError

principal = ContextVar('principal', default=None)
ROLES = {'viewer', 'operator', 'reviewer', 'admin'}


def required():
    environment = os.getenv('APP_ENV', 'development').strip().lower()
    # Unknown environment names fail closed rather than accidentally disabling auth.
    return environment not in ('development', 'test') or os.getenv('AUTH_REQUIRED', 'false').strip().lower() != 'false'


def users():
    try:
        values = json.loads(os.getenv('AUTH_USERS_JSON', '{}'))
        if not isinstance(values, dict) or not 1 <= len(values) <= 100:
            raise ValueError()
        digests = []
        for name, user in values.items():
            if (not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', name) or not isinstance(user, dict)
                or set(user) != {'token_sha256', 'role', 'workspace'} or user['role'] not in ROLES
                or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', user['workspace'])
                or not re.fullmatch(r'[a-f0-9]{64}', user['token_sha256'])):
                raise ValueError()
            digests.append(user['token_sha256'])
        if len(set(digests)) != len(digests):
            raise ValueError()
        return values
    except (ValueError, TypeError, KeyError):
        raise HTTPException(503, 'Authentication configuration unavailable.') from None


def authenticate(authorization):
    if not authorization.startswith('Bearer ') or not 32 <= len(authorization[7:]) <= 512:
        raise HTTPException(401, 'A valid access token is required.')
    digest = hashlib.sha256(authorization[7:].encode()).hexdigest()
    for name, user in users().items():
        if secrets.compare_digest(user['token_sha256'], digest):
            return {'id': name, 'role': user['role'], 'workspace': user['workspace'], '_credential': digest}
    raise HTTPException(401, 'A valid access token is required.')


def check_principal():
    """Recheck revocation/role changes before accepting provider output."""
    identity = principal.get()
    if required() and identity:
        current = users().get(identity['id'])
        if (current is None or current['role'] != identity['role'] or current['workspace'] != identity['workspace']
                or current['token_sha256'] != identity['_credential']):
            raise HTTPException(403, 'Access was revoked or changed.')


class AccessControl:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        path = scope.get('path', '').rstrip('/') or '/'
        public = path in ('/api/health', '/api/ready', '/api/auth/config')
        if not required() or public or scope['method'] == 'OPTIONS':
            return await self.app(scope, receive, send)
        token = None
        try:
            headers = dict(scope['headers'])
            identity = authenticate(headers.get(b'authorization', b'').decode('latin1'))
            role = identity['role']
            if path == '/api/metrics' and role != 'admin':
                raise HTTPException(403, 'Administrator role required.')
            if scope['method'] not in ('GET', 'HEAD'):
                allowed = {'admin', 'reviewer'} if path.endswith('/reviews') else {'admin', 'operator'}
                if role not in allowed:
                    raise HTTPException(403, 'Role does not permit this action.')
            if path.startswith(('/api/complaints', '/api/analytics')):
                if identity['workspace'] != os.getenv('KB_ANALYTICS_WORKSPACE', ''):
                    raise HTTPException(403, 'Complaint data is not assigned to this workspace.')
            if path.startswith(('/api/knowledge', '/api/agent', '/api/evaluation')):
                actual = workspace(headers.get(b'x-workspace-key', b'').decode('latin1'))
                if actual != identity['workspace']:
                    raise HTTPException(403, 'Workspace does not match authenticated access.')
            # Authenticated IDs bound cardinality; never use raw attacker-supplied keys/IPs.
            limit_requests('access:' + identity['id'], 120)
            token = principal.set(identity)
            scope['principal'] = identity
            await self.app(scope, receive, send)
        except HTTPException as exc:
            await JSONResponse({'detail': exc.detail}, status_code=exc.status_code)(scope, receive, send)
        except IntelligenceError as exc:
            await JSONResponse({'detail': {'code': exc.code}}, status_code=exc.status)(scope, receive, send)
        finally:
            if token is not None:
                principal.reset(token)
