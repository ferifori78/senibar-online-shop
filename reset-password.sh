#!/bin/sh
# Find the admin accounts, and set a new password on one.
#
#   sh reset-password.sh                     # just list who can log in
#   sh reset-password.sh you@example.com     # set a new password on that account
#
# Both logins — Django's own /admin/ and the Senobar panel — use the SAME
# account: email plus password. There is no separate panel password. What
# separates them is a flag on the account:
#
#   is_superuser / is_staff  ->  Django admin at /admin/
#   role ROASTER or ADMIN    ->  the Senobar panel
#
# A password is stored hashed and cannot be read back, by design — a database
# dump must not hand anyone your login. So there is nothing to look up; the
# only way back in is to set a new one, which is what this does.

set -e
WHO="$1"

if [ -z "$WHO" ]; then
    # No argument: just show which accounts can get in, so you can pick.
    docker compose exec -T api python manage.py shell <<'PYTHON'
from django.contrib.auth import get_user_model

User = get_user_model()
admins = User.objects.filter(is_staff=True) | User.objects.filter(
    role__in=["roaster", "admin"]
)
admins = admins.distinct().order_by("-is_superuser", "email")

if not admins:
    print("No admin account exists at all. Create one with:")
    print("   docker compose exec api python manage.py createsuperuser")
    raise SystemExit

print("=" * 66)
print("  Accounts that can log in")
print("=" * 66)
for u in admins:
    doors = []
    if u.is_staff:
        doors.append("Django /admin/")
    if u.is_roaster:
        doors.append("Senobar panel")
    print(f"  {u.email}")
    print(f"     role:   {u.role}   superuser: {u.is_superuser}   active: {u.is_active}")
    print(f"     opens:  {', '.join(doors) or 'nothing'}")
    print(f"     last login: {u.last_login:%Y-%m-%d %H:%M}" if u.last_login else "     last login: never")
    print()
print("=" * 66)
print("To set a new password:  sh reset-password.sh <that email>")
PYTHON
    exit 0
fi

# A password typed as an argument would sit in your shell history and in the
# process list, where another user on the box can read it. Read it from the
# terminal instead, twice, and never echo it.
printf 'New password for %s: ' "$WHO"
stty -echo 2>/dev/null || true
read PW1
stty echo 2>/dev/null || true
printf '\n'

printf 'Again: '
stty -echo 2>/dev/null || true
read PW2
stty echo 2>/dev/null || true
printf '\n'

if [ "$PW1" != "$PW2" ]; then
    echo "They do not match. Nothing was changed."
    exit 1
fi

# Django's own validators run below (length, not-all-numeric, not a common
# password). This is only a first, friendlier check.
if [ ${#PW1} -lt 10 ]; then
    echo "Too short — use at least 10 characters. Nothing was changed."
    exit 1
fi

PW="$PW1" docker compose exec -T -e NEWPW="$PW1" api python manage.py shell <<PYTHON
import os
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

User = get_user_model()
term = "$WHO".strip()
new = os.environ["NEWPW"]

try:
    user = User.objects.get(email__iexact=term)
except User.DoesNotExist:
    print(f"No account with the email {term!r}.")
    print("Run the script with no argument to list the admin accounts.")
    raise SystemExit(1)

try:
    validate_password(new, user)
except ValidationError as exc:
    print("Django rejected that password:")
    for msg in exc.messages:
        print("   -", msg)
    print("Nothing was changed.")
    raise SystemExit(1)

user.set_password(new)

# A locked-out admin is usually one who is also inactive; say so rather than
# silently handing back a password that still will not log in.
if not user.is_active:
    user.is_active = True
    print("NOTE: the account was disabled. Re-enabled it.")

user.save(update_fields=["password", "is_active"])

doors = []
if user.is_staff:
    doors.append("Django admin  ->  https://senobar.shop/admin/")
if user.is_roaster:
    doors.append("Senobar panel ->  https://senobar.shop/senobar-panel/nazadmin/")

print("=" * 66)
print(f"  Password changed for {user.email}")
print("=" * 66)
for d in doors:
    print("  " + d)
if not doors:
    print("  WARNING: this account opens neither. It is a plain customer.")
    print("  To make it a roaster:")
    print(f"     u = User.objects.get(email='{user.email}'); u.role='admin'; u.is_staff=True; u.save()")
print()
print("  Any session you had open elsewhere still works until it expires.")
PYTHON
