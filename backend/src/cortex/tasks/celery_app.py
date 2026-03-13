import os

from celery import Celery
from celery.signals import worker_process_init

redis_url = os.environ.get("REDIS_URL", "redis://localhost:6380/0")

app = Celery(
    "cortex",
    broker=redis_url,
    backend=redis_url,
)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_max_tasks_per_child=50,  # restart workers periodically to free GPU memory
)

# Explicitly include task modules
app.conf.update(
    include=["cortex.tasks.ingest"],
)


@worker_process_init.connect
def setup_worker_logging(**kwargs) -> None:
    """Configure structured JSON logging for Celery worker processes."""
    from cortex.infrastructure.logging import configure_logging
    from cortex.settings import Settings

    settings = Settings()
    configure_logging(level=settings.log_level, json_format=settings.log_json)
