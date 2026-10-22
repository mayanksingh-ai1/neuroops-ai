"""Expire abandoned work without replaying paid calls after a process crash."""
import time
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from .database import get_engine
from .agent_models import AgentRun
from .agent_service import finish
from .evaluation_models import Evaluation


def expire_evaluations(session):
    session.execute(update(Evaluation).where(Evaluation.status == 'running', Evaluation.expires_at <= time.time())
                    .values(status='failed', error_code='evaluation_timeout'))
    session.commit()


def sweep():
    with Session(get_engine()) as session:
        expire_evaluations(session)
        runs = session.scalars(select(AgentRun).where(AgentRun.status.in_(('queued', 'running')),
            AgentRun.expires_at <= time.time()).limit(100).with_for_update(skip_locked=True)).all()
        # Finish one at a time with a new row lock after each commit.
        ids = [run.id for run in runs]
        session.rollback()
        for run_id in ids:
            run = session.scalar(select(AgentRun).where(AgentRun.id == run_id).with_for_update())
            if run.status in ('queued', 'running') and run.expires_at <= time.time():
                finish(session, run, 'timed_out', 'agent_timeout')
            else:
                session.rollback()


def maintenance(stop):
    while not stop.is_set():
        try:
            sweep()
        except Exception:
            # Readiness reports dependency failures; do not print credentials from DB exceptions.
            pass
        stop.wait(15)
