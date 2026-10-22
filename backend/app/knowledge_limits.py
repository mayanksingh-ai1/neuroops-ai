"""Bound the JSON body before FastAPI parses or validates a question."""
from starlette.responses import JSONResponse


class KnowledgeQuestionLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope.get('path') not in ('/api/knowledge/ask', '/api/agent/runs'):
            return await self.app(scope, receive, send)
        messages, length = [], 0
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            length += len(message.get('body', b''))
            if length > 8192:
                response = JSONResponse({'detail': {'code': 'question_body_too_large'}}, status_code=413)
                return await response(scope, receive, send)
            messages.append(message)
            if not message.get('more_body', False):
                break
        iterator = iter(messages)

        async def replay():
            message = next(iterator, None)
            return message if message is not None else await receive()

        await self.app(scope, replay, send)
