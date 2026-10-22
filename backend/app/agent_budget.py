"""A request-local deadline shared with existing RAG provider calls."""
from contextvars import ContextVar
import time
from .intelligence import IntelligenceError

deadline: ContextVar[float | None] = ContextVar('agent_deadline', default=None)


def remaining() -> float:
    end = deadline.get()
    seconds = 25.0 if end is None else end - time.time()
    if seconds <= 0:
        raise IntelligenceError('agent_timeout', 504)
    return min(25.0, seconds)
