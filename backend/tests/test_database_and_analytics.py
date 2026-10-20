from datetime import date
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

os.environ['DATABASE_URL'] = 'postgresql+psycopg://unused:unused@localhost/unused'
from app.database import Base
from app.models import Complaint
from app.routes import categories, complaints, status_counts, trends


@pytest.fixture()
def session():
    engine = create_engine('sqlite+pysqlite:///:memory:',
                           connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([
            Complaint(complaint_id='CMP-1', title='Late parcel', category='delivery', status='open', priority='high', channel='email', received_date=date(2026, 10, 18)),
            Complaint(complaint_id='CMP-2', title='Refund pending', category='refund', status='resolved', priority='medium', channel='chat', received_date=date(2026, 10, 19)),
        ])
        db.commit()
        yield db


def test_database_primary_key_rejects_duplicate_complaints(session):
    session.add(Complaint(complaint_id='CMP-1', title='Duplicate', category='delivery', status='open', priority='low', channel='email', received_date=date(2026, 10, 20)))
    with pytest.raises(IntegrityError):
        session.commit()


def test_analytics_endpoints_group_stored_records(session):
    assert complaints(session, q='refund', limit=10, offset=0)['items'][0]['complaint_id'] == 'CMP-2'
    assert categories(session) == [{'name': 'delivery', 'count': 1}, {'name': 'refund', 'count': 1}]
    assert status_counts(session)['counts'] == {'open': 1, 'in_progress': 0, 'resolved': 1}
    result = trends(session, start=date(2026, 10, 18), end=date(2026, 10, 20))
    assert result == [{'day': date(2026, 10, 18), 'complaints': 1}, {'day': date(2026, 10, 19), 'complaints': 1}, {'day': date(2026, 10, 20), 'complaints': 0}]
