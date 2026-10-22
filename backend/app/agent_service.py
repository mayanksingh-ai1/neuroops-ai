"""Small, bounded worker. Each transaction is short; provider calls hold no run lock."""
import os
import time
from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from .database import get_engine
from .agent_models import AgentRun, AgentStep
from .agent_budget import deadline, remaining
from .agent_planner import plan_task, compile_plan, Plan
from . import agent_tools
from .knowledge_config import workspace
from .intelligence import IntelligenceError

ACTIVE = ('queued', 'running')
TRANSIENT = {'provider_rate_limited', 'provider_unavailable', 'provider_timeout'}


class AgentSettings(BaseModel):
    max_steps: int = Field(default=4, ge=2, le=4)
    timeout_seconds: int = Field(default=90, ge=5, le=180)
    retries: int = Field(default=1, ge=0, le=1)


def settings():
    try:
        return AgentSettings.model_validate({name: os.environ['AGENT_' + name.upper()]
            for name in AgentSettings.model_fields if 'AGENT_' + name.upper() in os.environ})
    except ValidationError:
        raise IntelligenceError('invalid_agent_configuration', 503) from None


def session_factory():
    return Session(get_engine())


def finish(session: Session, run: AgentRun, status: str, code: str | None):
    run.status, run.error_code = status, code
    for step in session.scalars(select(AgentStep).where(AgentStep.run_id == run.id,
                                                      AgentStep.status.in_(('pending', 'running')))):
        step.status, step.error_code = status, code
    session.commit()


def expire(session: Session, run: AgentRun):
    if run.status in ACTIVE and run.expires_at <= time.time():
        finish(session, run, 'timed_out', 'agent_timeout')


def locked_run(session: Session, run_id: str):
    return session.scalar(select(AgentRun).where(AgentRun.id == run_id).with_for_update()
                          .execution_options(populate_existing=True))


def guard(session: Session, run_id: str, key: str):
    from .security import check_principal
    check_principal()
    run = locked_run(session, run_id)
    if run is None:
        raise IntelligenceError('run_not_found', 404)
    expire(session, run)
    if run.status not in ACTIVE:
        raise IntelligenceError('run_stopped', 409)
    remaining()
    try:
        if workspace(key) != run.workspace_id:
            raise IntelligenceError('workspace_authorization_failed', 403)
    except HTTPException:
        raise IntelligenceError('workspace_authorization_failed', 403) from None
    return run


def perform(run_id: str, position: int, key: str, config: AgentSettings, operation):
    for attempt in range(config.retries + 1):
        with session_factory() as session:
            run = guard(session, run_id, key)
            step = session.scalar(select(AgentStep).where(AgentStep.run_id == run_id, AgentStep.position == position))
            step.status, step.attempts, step.error_code = 'running', attempt + 1, None
            scope = run.workspace_id
            session.commit()
        try:
            with session_factory() as session:
                if session.bind.dialect.name == 'postgresql':
                    # Fixed parameterized configuration, never model-generated SQL.
                    session.execute(text("SELECT set_config('statement_timeout', :timeout, true)"),
                                    {'timeout': str(max(1, int(min(5, remaining()) * 1000)))})
                output = operation(scope, session)
            with session_factory() as session:
                guard(session, run_id, key)  # Discard late/revoked/cancelled outputs.
                step = session.scalar(select(AgentStep).where(AgentStep.run_id == run_id, AgentStep.position == position))
                step.status, step.output = 'completed', output
                session.commit()
            return output
        except IntelligenceError as exc:
            with session_factory() as session:
                guard(session, run_id, key)
                step = session.scalar(select(AgentStep).where(AgentStep.run_id == run_id, AgentStep.position == position))
                step.error_code = exc.code
                session.commit()
            if exc.code not in TRANSIENT or attempt >= config.retries:
                raise
            time.sleep(min(0.25, remaining()))


def execute_run(run_id: str, key: str, config: AgentSettings):
    """BackgroundTasks passes the capability in memory only, never to the model/database."""
    token = None
    try:
        with session_factory() as session:
            run = locked_run(session, run_id)
            if run is None or run.status != 'queued':
                return  # Claim once, even if a dispatcher accidentally delivers twice.
            token = deadline.set(run.expires_at)
            run = guard(session, run_id, key)
            run.status = 'running'
            task = run.task
            session.commit()

        def planning(scope, session):
            plan, metadata = plan_task(task)
            return {'plan': plan.model_dump(), 'model_metadata': metadata}

        output = perform(run_id, 0, key, config, planning)
        plan = Plan.model_validate(output['plan'])
        if not plan.supported:
            raise IntelligenceError('unsupported_investigation', 422)
        calls = compile_plan(plan, task, config.max_steps)
        with session_factory() as session:
            guard(session, run_id, key)
            for position, call in enumerate(calls, 1):
                session.add(AgentStep(run_id=run_id, position=position, **call))
            session.commit()
        context = {'task': task, 'outputs': {}}
        for position, call in enumerate(calls, 1):
            output = perform(run_id, position, key, config, lambda scope, session: agent_tools.execute(
                call['tool'], call['arguments'], scope, session, context))
            context['outputs'][call['tool']] = output
        with session_factory() as session:
            run = guard(session, run_id, key)
            run.result, run.status = output, 'completed'
            session.commit()
    except Exception as exc:
        # Only stable codes are persisted, never exception text or provider payloads.
        code = exc.code if isinstance(exc, IntelligenceError) else 'agent_internal_error'
        try:
            with session_factory() as session:
                run = locked_run(session, run_id)
                if run is not None and run.status in ACTIVE:
                    timed_out = run.expires_at <= time.time() or code == 'agent_timeout'
                    finish(session, run, 'timed_out' if timed_out else 'failed', 'agent_timeout' if timed_out else code)
        except Exception:
            # If the database is unavailable, status reads expire the run after its deadline.
            pass
    finally:
        if token is not None:
            deadline.reset(token)


def view(session: Session, run: AgentRun):
    steps = session.scalars(select(AgentStep).where(AgentStep.run_id == run.id).order_by(AgentStep.position)).all()
    return {'id': run.id, 'task': run.task, 'status': run.status, 'created_at': run.created_at,
            'expires_at': run.expires_at, 'error_code': run.error_code, 'result': run.result,
            'steps': [{'position': step.position, 'tool': step.tool, 'arguments': step.arguments,
                       'status': step.status, 'attempts': step.attempts, 'output': step.output,
                       'error_code': step.error_code} for step in steps]}
