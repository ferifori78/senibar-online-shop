#!/bin/sh
# Ask SMS.ir directly what is wrong with sending.
#
#   sh sms-probe.sh 09121234567
#
# Runs inside the api container through Django, so it uses the very same key,
# line number and template ids the site uses — nothing is copied or retyped.
# Read-only except for the two test sends at the end.

set -e
PHONE="${1:?usage: sh sms-probe.sh 09121234567}"

docker compose exec -T api python manage.py shell <<PYTHON
import json
import requests
from django.conf import settings

BASE = "https://api.sms.ir/v1"
KEY = settings.SMSIR_API_KEY
LINE = settings.SMSIR_LINE_NUMBER

if not KEY:
    print("SMSIR_API_KEY is empty in the container. The .env is not reaching it.")
    raise SystemExit

print(f"key: {KEY[:6]}...{KEY[-4:]}  ({len(KEY)} chars)")
print(f"line number: {LINE!r}")
print(f"backend: {settings.SMS_BACKEND!r}")
for name in ("VERIFY", "WELCOME", "ORDER", "PAYMENT", "TICKET_REPLY", "TICKET_STATUS"):
    print(f"  {name} template: {getattr(settings, f'SMSIR_{name}_TEMPLATE_ID', '') !r}")

H = {"Content-Type": "application/json", "Accept": "application/json", "x-api-key": KEY}


def show(label, method, path, payload=None):
    print(f"\n=== {label} ===")
    if payload is not None:
        print("payload:", json.dumps(payload, ensure_ascii=False))
    try:
        r = (requests.get if method == "GET" else requests.post)(
            f"{BASE}{path}", headers=H, timeout=20,
            **({"json": payload} if payload is not None else {}),
        )
    except Exception as exc:
        print("UNREACHABLE:", exc)
        return
    print("HTTP", r.status_code)
    try:
        print(json.dumps(r.json(), ensure_ascii=False, indent=2)[:900])
    except ValueError:
        print("non-JSON:", r.text[:400])


# Is the key valid and funded? Read-only, so this separates authentication
# from anything to do with the message itself.
show("credit", "GET", "/credit")
# Is SMSIR_LINE_NUMBER actually registered? If not, /send/bulk fails with 101
# however correct everything else is.
show("registered lines", "GET", "/line")

digits = "".join(c for c in "$PHONE" if c.isdigit())
bare = digits[1:] if digits.startswith("0") and len(digits) == 11 else digits

tpl = settings.SMSIR_VERIFY_TEMPLATE_ID
if tpl:
    # Both forms, so the provider's own reply says which it wants.
    for label, mobile in (("no leading zero", bare), ("with leading zero", digits)):
        show(f"verify - {label}", "POST", "/send/verify", {
            "mobile": mobile,
            "templateId": int(tpl),
            "parameters": [{"name": settings.SMSIR_VERIFY_PARAM, "value": "12345"}],
        })

if LINE:
    show("bulk - no leading zero", "POST", "/send/bulk", {
        "lineNumber": int(LINE) if str(LINE).isdigit() else LINE,
        "messageText": "تست صنوبر",
        "mobiles": [bare],
    })
PYTHON
