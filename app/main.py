from __future__ import annotations

import os
from collections.abc import Callable

from fastapi import FastAPI

from app.db.migrations import apply_sqlite_compat_migrations
from app.db.models import Base
from app.db.session import build_session_factory
from app.providers.valuecell_runner import BrowserAdapter
from app.routes.health import router as health_router
from app.routes.schedules import build_schedules_router
from app.routes.tasks import build_tasks_router


def create_app(
    db_url: str | None = None,
    adapter_factory: Callable[[], BrowserAdapter] | None = None,
) -> FastAPI:
    resolved_db_url = db_url or os.getenv("DATABASE_URL", "sqlite:///./data/app.db")
    scheduler_enabled = os.getenv("SCHEDULER_ENABLED", "false").lower() == "true"
    session_factory = build_session_factory(resolved_db_url)
    engine = session_factory.kw["bind"]
    Base.metadata.create_all(bind=engine)
    apply_sqlite_compat_migrations(engine)

    app = FastAPI(title="stock-agent", version="0.1.0")
    app.include_router(health_router)
    app.include_router(build_tasks_router(session_factory, adapter_factory=adapter_factory))
    app.include_router(
        build_schedules_router(session_factory, enable_scheduler=scheduler_enabled, adapter_factory=adapter_factory)
    )
    return app


app = create_app()
