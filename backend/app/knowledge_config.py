"""Fail-closed workspace credentials and bounded RAG configuration."""
import json
import os
import re
import secrets
import threading
import time
from typing import Annotated
from fastapi import Header, HTTPException
from pydantic import BaseModel, Field, ValidationError, model_validator
from .intelligence import IntelligenceError


class KnowledgeSettings(BaseModel):
    upload_bytes: int = Field(default=5 * 1024 * 1024, ge=1024, le=10 * 1024 * 1024)
    chunk_size: int = Field(default=1000, ge=100, le=2000)
    chunk_overlap: int = Field(default=150, ge=0)
    workspace_chunks: int = Field(default=1000, ge=1, le=2000)
    workspace_documents: int = Field(default=100, ge=1, le=100)
    min_similarity: float = Field(default=0.3, ge=-1, le=1)
    requests_per_minute: int = Field(default=10, ge=1, le=60)

    @model_validator(mode='after')
    def valid_overlap(self):
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError('overlap must be smaller than chunk size')
        return self


def settings() -> KnowledgeSettings:
    try:
        values = {field: os.environ['KB_' + field.upper()] for field in KnowledgeSettings.model_fields
                  if 'KB_' + field.upper() in os.environ}
        return KnowledgeSettings.model_validate(values)
    except ValidationError:
        raise IntelligenceError('invalid_kb_configuration', 503) from None


def workspace(x_workspace_key: Annotated[str | None, Header(max_length=512)] = None) -> str:
    try:
        keys = json.loads(os.getenv('KB_WORKSPACE_KEYS_JSON', '{}'))
        if (not isinstance(keys, dict) or not keys or len(keys) > 100
                or any(not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', name)
                       or not isinstance(key, str) or not 32 <= len(key) <= 512
                       for name, key in keys.items())
                or len(set(keys.values())) != len(keys)):
            raise ValueError()
    except (ValueError, TypeError):
        raise HTTPException(503, 'Configure valid, distinct knowledge workspace keys.') from None
    for name, key in keys.items():
        if x_workspace_key and secrets.compare_digest(x_workspace_key.encode(), key.encode()):
            return name
    raise HTTPException(401, 'A valid X-Workspace-Key header is required.')


_calls: dict[str, list[float]] = {}
_lock = threading.Lock()


def limit_requests(workspace_id: str, limit: int):
    """Per-process protection for costly requests, not a distributed quota."""
    now = time.monotonic()
    with _lock:
        calls = [stamp for stamp in _calls.get(workspace_id, []) if now - stamp < 60]
        if len(calls) >= limit:
            raise IntelligenceError('workspace_rate_limited', 429)
        _calls[workspace_id] = calls + [now]
