#!/bin/sh
# Find out why the Telegram feed is silent.
#
#   sh tg-probe.sh
#
# Runs inside the api container, so it reads the very same settings the site
# uses. Checks each step in order and stops being useful at the first failure,
# which is the one to fix.

set -e

docker compose exec -T api python manage.py shell <<'PYTHON'
import json
import requests
from django.conf import settings

TOKEN = settings.TELEGRAM_BOT_TOKEN
CHAT = settings.TELEGRAM_CHAT_ID

print("=" * 60)
print("1. Are the settings reaching the container?")
print("=" * 60)
print(f"   TELEGRAM_BOT_TOKEN: {'set (' + TOKEN[:10] + '...)' if TOKEN else 'EMPTY'}")
print(f"   TELEGRAM_CHAT_ID:   {CHAT!r}")

if not TOKEN or not CHAT:
    print()
    print("   >>> THIS IS THE PROBLEM.")
    print("   The feed posts nothing when either is empty.")
    print("   Put both in /home/senobar/.env (beside docker-compose.yml,")
    print("   NOT in backend/.env), then: docker compose up -d")
    raise SystemExit

print()
print("=" * 60)
print("2. Is the bot token valid?")
print("=" * 60)
r = requests.get(f"https://api.telegram.org/bot{TOKEN}/getMe", timeout=15)
body = r.json()
print(f"   HTTP {r.status_code}")
if not body.get("ok"):
    print(f"   >>> THE TOKEN IS REJECTED: {body.get('description')!r}")
    print("   Get a fresh one from @BotFather.")
    raise SystemExit
print(f"   bot: @{body['result'].get('username')}")

print()
print("=" * 60)
print("3. Can the bot reach the channel?")
print("=" * 60)
r = requests.get(
    f"https://api.telegram.org/bot{TOKEN}/getChat",
    params={"chat_id": CHAT}, timeout=15,
)
body = r.json()
print(f"   HTTP {r.status_code}")
if not body.get("ok"):
    print(f"   >>> CANNOT REACH THE CHANNEL: {body.get('description')!r}")
    print()
    print("   Usually one of:")
    print("     - the bot was never added to the channel as an ADMINISTRATOR")
    print("     - the chat id is wrong (a channel id is negative, like")
    print("       -1001234567890 — not the @name, not a positive number)")
    raise SystemExit
print(f"   chat: {body['result'].get('title')!r} ({body['result'].get('type')})")

print()
print("=" * 60)
print("4. Can it actually post?")
print("=" * 60)
r = requests.post(
    f"https://api.telegram.org/bot{TOKEN}/sendMessage",
    json={"chat_id": CHAT, "text": "تست صنوبر — این پیام از سرور آمد."},
    timeout=15,
)
body = r.json()
print(f"   HTTP {r.status_code}  ok={body.get('ok')}")
if not body.get("ok"):
    print(f"   >>> POST REFUSED: {body.get('description')!r}")
    print("   If it mentions permissions, the bot is in the channel but is")
    print("   not an administrator, or cannot post messages.")
    raise SystemExit
print("   >>> A test message should now be in the channel.")

print()
print("=" * 60)
print("5. Is the Celery worker running the feed tasks?")
print("=" * 60)
from notifications.feed import customer_joined
try:
    res = customer_joined.delay(1)
    print(f"   queued: {res.id}")
    print("   >>> If no message arrives in a few seconds, the worker is not")
    print("       consuming the queue. Check: docker compose logs worker")
except Exception as exc:
    print(f"   >>> COULD NOT QUEUE: {exc}")
    print("   Redis is unreachable from the api container.")

print()
print("=" * 60)
print("6. What has the feed recorded?")
print("=" * 60)
from notifications.models import Notification
rows = Notification.objects.filter(channel="telegram").order_by("-created_at")[:10]
if not rows:
    print("   No feed rows at all — no task has ever reached the posting step.")
    print("   That points at the worker, not at Telegram.")
for n in rows:
    print(f"   {n.created_at:%m-%d %H:%M}  {n.status:7} {n.dedupe_key}")
    if n.error:
        print(f"            error: {n.error}")
PYTHON
