from celery import Celery
from celery.schedules import schedule

from app.core.config import get_settings

settings = get_settings()
celery_app = Celery(
    "job_radar",
    broker=settings.redis_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.jobs"],
)
celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    timezone="UTC",
    beat_schedule={
        "dispatch-due-profiles": {
            "task": "app.tasks.jobs.dispatch_due_profiles_task",
            "schedule": schedule(settings.scheduler_dispatch_interval_seconds),
        },
        "send-pending-notifications": {
            "task": "app.tasks.jobs.send_pending_notifications_task",
            "schedule": schedule(15),
        },
    },
)
