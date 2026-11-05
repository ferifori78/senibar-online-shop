"""Liveness and readiness probes.

`/api/health/` answers whether this process is up — used by the container
healthcheck and the load balancer. `/api/health/ready/` also checks that the
things the app cannot work without are reachable.
"""

from django.db import connection
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes((AllowAny,))
def health(request):
    """Liveness: is this process serving? Deliberately touches nothing."""
    return Response({"status": "ok", "service": "senobar-api"})


@api_view(["GET"])
@permission_classes((AllowAny,))
def readiness(request):
    """Readiness: can we actually serve requests?

    Reports 503 if a dependency is down, so an orchestrator stops routing
    traffic here rather than serving errors.
    """
    checks = {}

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"

    try:
        import redis
        from django.conf import settings

        client = redis.Redis.from_url(settings.CELERY_BROKER_URL, socket_timeout=2)
        client.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {exc}"

    healthy = all(value == "ok" for value in checks.values())
    return Response(
        {"status": "ok" if healthy else "degraded", "checks": checks},
        status=200 if healthy else 503,
    )
