"""Only these three read-only capabilities can appear in an agent plan."""
from datetime import date, timedelta, datetime, timezone
import os
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.orm import Session
from . import routes, knowledge_service
from .knowledge_config import settings
from .intelligence import IntelligenceError


class Arguments(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class AnalyticsArgs(Arguments):
    days: int = Field(ge=1, le=366)


class RetrievalArgs(Arguments):
    question: str = Field(min_length=3, max_length=1000)
    top_k: int = Field(ge=1, le=5)


class ReportArgs(Arguments):
    pass


def analytics(args: AnalyticsArgs, scope: str, session: Session, context: dict):
    # Complaints currently belong to ONE installation workspace, not every key.
    if scope != os.getenv('KB_ANALYTICS_WORKSPACE', ''):
        raise IntelligenceError('analytics_not_authorized', 403)
    end = date.today()
    return {'label': 'Calculated database facts; original imported categories, not AI labels.',
            'scope': 'All stored complaints in the installation analytics workspace',
            'as_of': datetime.now(timezone.utc).isoformat(),
            **routes.status_counts(session), 'categories': routes.categories(session),
            'trends': [{**row, 'day': row['day'].isoformat()} for row in routes.trends(
                session, end - timedelta(days=args.days - 1), end)],
            'trend_days': args.days}


def knowledge(args: RetrievalArgs, scope: str, session: Session, context: dict):
    return {'sources': knowledge_service.retrieve(args.question, scope, session, settings(), args.top_k)}


def report(args: ReportArgs, scope: str, session: Session, context: dict):
    facts = context['outputs'].get('complaint_analytics')
    if facts is not None and scope != os.getenv('KB_ANALYTICS_WORKSPACE', ''):
        raise IntelligenceError('analytics_not_authorized', 403)
    retrieved = context['outputs'].get('knowledge_retrieval')
    evidence = knowledge_service.answer(context['task'], retrieved['sources']) if retrieved is not None else None
    limitations = ['AI interpretations are unverified. A matching quote does not prove that the interpretation is correct.',
                   'This workflow cannot establish root causes or perform external actions.']
    missing = False
    if facts is not None and facts['total'] == 0:
        missing = True
        limitations.append('No complaint records are available; no complaint conclusions can be drawn.')
    if evidence is not None and evidence['status'] != 'answered':
        missing = True
        limitations.append(knowledge_service.INSUFFICIENT)
    return {'status': 'insufficient_evidence' if missing else 'completed',
            'database_facts': facts, 'document_findings': evidence,
            # We deliberately do not ask a model to rewrite numeric database facts.
            'recommendations': [],
            'review_next_step': 'A human should verify the evidence before deciding on an operational action.',
            'limitations': limitations, 'human_verified': False}


# A model cannot register code, URLs, SQL, shell commands, or filesystem paths.
REGISTRY = {
    'complaint_analytics': (AnalyticsArgs, analytics),
    'knowledge_retrieval': (RetrievalArgs, knowledge),
    'report_generation': (ReportArgs, report),
}


def validate_call(name: str, arguments: dict):
    if name not in REGISTRY:
        raise IntelligenceError('unknown_agent_tool', 422)
    schema, function = REGISTRY[name]
    try:
        return function, schema.model_validate(arguments)
    except ValidationError:
        raise IntelligenceError('invalid_tool_arguments', 422) from None


def execute(name: str, arguments: dict, scope: str, session: Session, context: dict):
    function, parsed = validate_call(name, arguments)
    # The worker re-authenticates the original workspace capability before EVERY call.
    return function(parsed, scope, session, context)
