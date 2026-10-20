"""Database connections are lazy: health checks work before database setup."""
import os
from functools import lru_cache

from dotenv import load_dotenv
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session
from fastapi import HTTPException

# Existing shell variables always take precedence over the local file.
load_dotenv(Path(__file__).resolve().parents[1] / '.env', override=False)


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine():
    url = os.getenv('DATABASE_URL', '')
    if not url.startswith('postgresql+psycopg://'):
        raise HTTPException(503, 'Set DATABASE_URL to a PostgreSQL psycopg connection URL.')
    return create_engine(url, pool_pre_ping=True, connect_args={'connect_timeout': 5})


def get_session():
    with Session(get_engine()) as session:
        yield session
