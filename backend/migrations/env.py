import os
from alembic import context
from app.database import Base, get_engine
from app.models import Complaint  # Register the model metadata.

config = context.config


def run(connection):
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(
        url=os.getenv('DATABASE_URL', 'postgresql+psycopg://neuroops@localhost/neuroops'),
        target_metadata=Base.metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()
elif config.attributes.get('connection') is not None:
    run(config.attributes['connection'])
else:
    with get_engine().connect() as connection:
        run(connection)
