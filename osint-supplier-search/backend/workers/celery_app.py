from __future__ import annotations
from celery import Celery
from app.config import settings

celery_app = Celery(
    "osint_supplier",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "workers.tasks.orchestrator",
        "workers.tasks.entity_resolution",
        "workers.tasks.ranking",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "workers.tasks.orchestrator.*": {"queue": "search"},
        "workers.tasks.entity_resolution.*": {"queue": "er"},
        "workers.tasks.ranking.*": {"queue": "ranking"},
    },
)
