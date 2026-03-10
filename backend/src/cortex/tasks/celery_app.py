import os

from celery import Celery

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

# Auto-discover tasks in cortex.tasks package
app.autodiscover_tasks(["cortex.tasks"])
