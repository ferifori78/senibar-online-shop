#!/bin/sh
# Measure where the OTP delay actually is.
#
#   sh sms-timing.sh 09121234567
#
# Sends one real code and reports how long SMS.ir took to ACCEPT it. Note the
# wall-clock time you receive the SMS on the handset and compare:
#
#   accepted fast (~1s), arrives late   -> the delay is the operator's, not ours
#   accepted slowly (>5s)               -> the delay is the network or SMS.ir's API
#
# Also prints the template's own delivery status, which is where a template
# awaiting approval in the panel shows up.

set -e
PHONE="${1:?usage: sh sms-timing.sh 09121234567}"

docker compose exec -T api python manage.py shell <<PYTHON
import json, time
import requests
from django.conf import settings
from django.utils import timezone

KEY = settings.SMSIR_API_KEY
if not KEY:
    print("SMSIR_API_KEY is empty in the container.")
    raise SystemExit

H = {"Content-Type": "application/json", "Accept": "application/json", "x-api-key": KEY}
BASE = "https://api.sms.ir/v1"

digits = "".join(c for c in "$PHONE" if c.isdigit())
bare = digits[1:] if digits.startswith("0") and len(digits) == 11 else digits

print("sending one real code to", bare, "at", timezone.localtime().strftime("%H:%M:%S"))

payload = {
    "mobile": bare,
    "templateId": int(settings.SMSIR_VERIFY_TEMPLATE_ID),
    "parameters": [{"name": settings.SMSIR_VERIFY_PARAM, "value": "12345"}],
}

t0 = time.monotonic()
r = requests.post(f"{BASE}/send/verify", json=payload, headers=H, timeout=20)
elapsed = time.monotonic() - t0

body = r.json()
print(f"\nSMS.ir accepted in {elapsed:.2f}s  (HTTP {r.status_code}, status {body.get('status')})")
print(json.dumps(body, ensure_ascii=False, indent=2)[:600])

# The message id lets us ask what the operator did with it afterwards, which
# is the half of the journey the accept time cannot show.
mid = (body.get("data") or {}).get("messageId")
if mid:
    print(f"\nmessage id {mid} — waiting 10s, then asking for its delivery report")
    time.sleep(10)
    rr = requests.get(f"{BASE}/send/{mid}", headers=H, timeout=20)
    try:
        print(json.dumps(rr.json(), ensure_ascii=False, indent=2)[:800])
    except ValueError:
        print("non-JSON:", rr.text[:300])

print("\nNote the time the SMS actually arrives on the handset and compare with the")
print("accept time above. A fast accept plus a late arrival is the operator, not us.")
PYTHON
