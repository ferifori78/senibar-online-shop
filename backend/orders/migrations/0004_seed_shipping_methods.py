from decimal import Decimal

from django.db import migrations

# Verbatim from the SHIPPING_METHODS dict this table replaces. A running shop
# must see the same three options at the same prices after the deploy.
SEED = [
    {
        "key": "standard",
        "label": "پست پیشتاز",
        "description": "۳ تا ۵ روز کاری، تحویل با پست ملی.",
        "days": "۳ تا ۵ روز کاری",
        "cost": Decimal("150000"),
        "free_over": Decimal("3000000"),
        "sort_order": 10,
    },
    {
        "key": "express",
        "label": "پیک سریع",
        "description": "۱ تا ۲ روز کاری، با رهگیری درب تا درب.",
        "days": "۱ تا ۲ روز کاری",
        "cost": Decimal("320000"),
        "free_over": None,
        "sort_order": 20,
    },
    {
        "key": "pickup",
        "label": "تحویل حضوری در کارگاه",
        "description": "روز پس از رست آماده است. بدون هزینه ارسال.",
        "days": "پس از رست",
        "cost": Decimal("0"),
        "free_over": None,
        "sort_order": 30,
    },
]


def seed(apps, schema_editor):
    ShippingMethod = apps.get_model("orders", "ShippingMethod")
    for row in SEED:
        # get_or_create, not create: a re-run must not trip over the unique key,
        # and must never overwrite a price the roastery has since edited.
        ShippingMethod.objects.get_or_create(key=row["key"], defaults=row)


def unseed(apps, schema_editor):
    ShippingMethod = apps.get_model("orders", "ShippingMethod")
    ShippingMethod.objects.filter(key__in=[r["key"] for r in SEED]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0003_shippingmethod_alter_order_shipping_method"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
