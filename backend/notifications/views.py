"""Recording page views for the Telegram digest."""

import hashlib

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from .models import SiteVisit


class VisitThrottle(AnonRateThrottle):
    """A ceiling per IP. The endpoint is public and unauthenticated, so without
    this anyone could fill the table — and the hourly digest with it."""

    scope = "visit"


def _visitor_hash(request):
    """A short, salted digest of who this is — never the address itself.

    Salted with SECRET_KEY so the hashes cannot be reversed by anyone holding
    a dump of the table: the space of IP addresses is small enough to brute
    force otherwise. This is a counter for distinct visitors within an hour,
    not an identity.
    """
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    ip = forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR", "")
    agent = request.META.get("HTTP_USER_AGENT", "")[:200]
    raw = f"{settings.SECRET_KEY}|{ip}|{agent}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


@api_view(["POST"])
@permission_classes((AllowAny,))
@throttle_classes([VisitThrottle])
def record_visit(request):
    """Record one page view.

    Deliberately returns 204 whatever happens: this is fire-and-forget from
    the client, and a failure here must never surface to a customer browsing
    the shop.
    """
    path = str(request.data.get("path") or "")[:200]
    if not path.startswith("/"):
        return Response(status=status.HTTP_204_NO_CONTENT)

    referrer = str(request.data.get("referrer") or "")[:200]
    # An internal referrer is just the previous page and tells the roaster
    # nothing about where traffic came from.
    if settings.FRONTEND_URL and referrer.startswith(settings.FRONTEND_URL):
        referrer = ""

    try:
        SiteVisit.objects.create(
            path=path,
            visitor_hash=_visitor_hash(request),
            referrer=referrer,
            is_authenticated=request.user.is_authenticated,
        )
    except Exception:  # pragma: no cover - a counter must never break a page
        pass

    return Response(status=status.HTTP_204_NO_CONTENT)
