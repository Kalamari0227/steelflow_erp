import os

from alembic import context
from sqlalchemy import create_engine, pool

from app.models import Base
from app.operations import models as operations_models  # noqa: F401 -- register additive tables
from app.operations import models_v3 as factory_models  # noqa: F401 -- register factory tables

config = context.config
url = config.get_main_option("sqlalchemy.url") or "sqlite:///steelflow.db"
if not config.attributes.get("explicit_url"):
    url = os.environ.get("STEELFLOW_DATABASE_URL", url)
url = url.replace("sqlite+aiosqlite", "sqlite")
target_metadata = Base.metadata

if context.is_offline_mode():
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
