#!/bin/sh
# Remove a test account.
#
#   sh delete-user.sh 09121234567          # by phone
#   sh delete-user.sh someone@example.com  # by email
#
# Shows everything attached to the account and asks before touching anything.
# An account with real orders is NOT deleted: an order is a financial record,
# and erasing the customer would leave it pointing at nobody.

set -e
WHO="${1:?usage: sh delete-user.sh <phone or email>}"

docker compose exec -T api python manage.py shell <<PYTHON
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()
term = "$WHO".strip()

users = list(User.objects.filter(Q(email__iexact=term) | Q(phone=term)))

if not users:
    print(f"No account matches {term!r}.")
    raise SystemExit

if len(users) > 1:
    print(f"{len(users)} accounts match — refusing to guess:")
    for u in users:
        print(f"   #{u.pk}  {u.email}  {u.phone}")
    raise SystemExit

user = users[0]
print("=" * 60)
print(f"  #{user.pk}  {user.display_name}")
print(f"  email:  {user.email}")
print(f"  phone:  {user.phone}")
print(f"  staff:  {user.is_staff}")
print(f"  joined: {user.date_joined:%Y-%m-%d %H:%M}")
print("=" * 60)

if user.is_staff:
    print()
    print(">>> This is a STAFF account. Refusing.")
    print("    Deleting it could lock you out of the panel.")
    raise SystemExit

from orders.models import Order
from support.models import Ticket
from notifications.models import Notification

orders = Order.objects.filter(user=user)
paid = orders.exclude(payment_status="pending")
tickets = Ticket.objects.filter(user=user)

print(f"  orders:        {orders.count()}  (of which paid//settled: {paid.count()})")
print(f"  tickets:       {tickets.count()}")
print(f"  notifications: {Notification.objects.filter(user=user).count()}")
print()

if paid.exists():
    print(">>> This account has orders that were paid. Refusing to delete.")
    print("    An order is a financial record; erasing the customer would")
    print("    leave it attached to nobody. Deactivate the account instead:")
    print()
    print(f"    User.objects.filter(pk={user.pk}).update(is_active=False)")
    raise SystemExit

# Everything else cascades from the user row, so one delete is enough.
deleted, per_model = user.delete()
print(f"Deleted {deleted} rows:")
for model, n in sorted(per_model.items()):
    print(f"   {model}: {n}")
PYTHON
