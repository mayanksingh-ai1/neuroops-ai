"""Reviewer identities are bound to separate backend-configured capability keys."""
import json
import os
import re
import secrets
from fastapi import HTTPException


def reviewer(scope, key):
    try:
        config = json.loads(os.getenv('EVAL_REVIEWER_KEYS_JSON', '{}'))
        if not isinstance(config, dict) or not config or len(config) > 100:
            raise ValueError()
        seen = []
        for workspace, reviewers in config.items():
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', workspace) or not isinstance(reviewers, dict) or not 1 <= len(reviewers) <= 50:
                raise ValueError()
            for name, secret in reviewers.items():
                if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', name) or not isinstance(secret, str) or not 32 <= len(secret) <= 512:
                    raise ValueError()
                seen.append(secret)
        if len(set(seen)) != len(seen):
            raise ValueError()
    except (ValueError, TypeError):
        raise HTTPException(503, 'Configure valid distinct evaluation reviewer keys.') from None
    for name, secret in config.get(scope, {}).items():
        if key and secrets.compare_digest(key.encode(), secret.encode()):
            return name
    raise HTTPException(403, 'An authorized X-Reviewer-Key is required for this workspace.')
