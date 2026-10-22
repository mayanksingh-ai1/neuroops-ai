"""Workspace-scoped run creation, timeline, result, and cooperative cancellation."""
import time
from typing import Annotated
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, func
from .routes import DB
from .knowledge_routes import Workspace, no_cache, failure
from .knowledge_config import limit_requests
from .knowledge_service import lock_workspace
from .agent_models import AgentRun, AgentStep
from .agent_planner import redact_task
from . import agent_service as service
from .intelligence import IntelligenceError

router = APIRouter(prefix='/api/agent', tags=['agent'], dependencies=[Depends(no_cache)])


class Task(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    task: str = Field(min_length=3, max_length=1000)
    provider_consent: bool

    @field_validator('task')
    @classmethod
    def clean(cls, value):
        value = value.strip()
        if len(value) < 3 or any(ord(c) < 32 and c not in '\n\t' for c in value):
            raise ValueError('Enter a text investigation task.')
        return redact_task(value)


def scoped_run(session, run_id, scope):
    run = session.scalar(select(AgentRun).where(AgentRun.id == run_id, AgentRun.workspace_id == scope)
                         .with_for_update().execution_options(populate_existing=True))
    if run is None:
        raise HTTPException(404, 'Run not found.')
    service.expire(session, run)
    return run


@router.post('/runs', status_code=202)
def create_run(payload: Task, session: DB, scope: Workspace, background: BackgroundTasks,
               x_workspace_key: Annotated[str, Header(max_length=512)]):
    if not payload.provider_consent:
        raise HTTPException(422, 'Consent is required before sending task text and document passages to the configured providers.')
    try:
        config = service.settings()
        limit_requests('agent:' + scope, 5)
        # Serialize admission across processes; at most 8 live runs, 2 per workspace.
        lock_workspace(session, '__agent_admission__')
        active = select(AgentRun).where(AgentRun.status.in_(service.ACTIVE), AgentRun.expires_at > time.time())
        total = session.scalar(select(func.count()).select_from(active.subquery()))
        own = session.scalar(select(func.count()).select_from(active.where(AgentRun.workspace_id == scope).subquery()))
        if total >= 8 or own >= 2:
            raise IntelligenceError('agent_capacity_reached', 429)
        now = time.time()
        run = AgentRun(workspace_id=scope, task=payload.task, created_at=now, expires_at=now + config.timeout_seconds)
        session.add(run)
        session.flush()
        session.add(AgentStep(run_id=run.id, position=0, tool='planning', arguments={}))
        session.commit()
        response = service.view(session, run)
        background.add_task(service.execute_run, run.id, x_workspace_key, config)
        return response
    except IntelligenceError as exc:
        failure(exc)


@router.get('/runs')
def list_runs(session: DB, scope: Workspace, limit: int = Query(20, ge=1, le=50), offset: int = Query(0, ge=0)):
    ids = session.scalars(select(AgentRun.id).where(AgentRun.workspace_id == scope)
                         .order_by(AgentRun.created_at.desc(), AgentRun.id).offset(offset).limit(limit)).all()
    result = {'items': [service.view(session, scoped_run(session, run_id, scope)) for run_id in ids]}
    session.commit()
    return result


@router.get('/runs/{run_id}')
def get_run(run_id: str, session: DB, scope: Workspace):
    result = service.view(session, scoped_run(session, run_id, scope))
    session.commit()
    return result


@router.get('/runs/{run_id}/result')
def get_result(run_id: str, session: DB, scope: Workspace):
    run = scoped_run(session, run_id, scope)
    if run.status != 'completed':
        session.commit()
        raise HTTPException(409, {'code': run.error_code or 'run_not_completed'})
    result = run.result
    session.commit()
    return result


@router.post('/runs/{run_id}/cancel')
def cancel_run(run_id: str, session: DB, scope: Workspace):
    run = scoped_run(session, run_id, scope)
    if run.status in service.ACTIVE:
        service.finish(session, run, 'cancelled', 'cancelled_by_user')
    result = service.view(session, run)
    session.commit()
    return result
