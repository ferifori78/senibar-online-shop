import os

from celery import Celery
from celery.signals import setup_logging

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("senobar")

# Every CELERY_-prefixed setting in settings.py configures the app.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Finds tasks.py in each installed app.
app.autodiscover_tasks()

# ...and only tasks.py. A task defined in any other module is registered on
# the process that imports it — so the web container queues it happily, and
# the worker, which never imports that module, silently has no such task and
# drops it. The symptom is a task that queues without error and never runs.
app.autodiscover_tasks(related_name="feed")


@setup_logging.connect
def configure_logging(**kwargs):
    """Let Django own logging so worker output matches the rest of the app."""
    from logging.config import dictConfig

    from django.conf import settings

    if settings.LOGGING:
        dictConfig(settings.LOGGING)


@app.task(bind=True, name="debug.ping")
def ping(self):
    """Smoke test: `celery -A config call debug.ping` proves the wiring."""
    return {"ok": True, "task_id": self.request.id, "worker": self.request.hostname}
