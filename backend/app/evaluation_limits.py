"""Bound evaluation bodies before JSON/CSV parsing, including chunked uploads."""
from starlette.responses import JSONResponse


class EvaluationBodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get('path', '')
        if scope['type'] != 'http' or scope.get('method') != 'POST' or not path.startswith('/api/evaluation/'):
            return await self.app(scope, receive, send)
        limit = 1024 * 1024 if path == '/api/evaluation/cases/import' else 65536
        messages, size = [], 0
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            size += len(message.get('body', b''))
            if size > limit:
                return await JSONResponse({'detail': {'code': 'evaluation_body_too_large'}}, status_code=413)(scope, receive, send)
            messages.append(message)
            if not message.get('more_body', False):
                break
        iterator = iter(messages)
        async def replay():
            message = next(iterator, None)
            return message if message is not None else await receive()
        await self.app(scope, replay, send)
