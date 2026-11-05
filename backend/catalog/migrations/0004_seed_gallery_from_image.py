"""Carry each product's existing photo into the new gallery.

Without this the gallery starts empty for every product already in the shop,
the panel shows no photos, and the first upload would be treated as the first
image — silently demoting a cover the roaster had already chosen.
"""

from django.db import migrations


def seed_gallery(apps, schema_editor):
    CoffeeProduct = apps.get_model("catalog", "CoffeeProduct")
    ProductImage = apps.get_model("catalog", "ProductImage")

    rows = [
        ProductImage(product=product, image=product.image, is_cover=True, sort_order=0)
        # `.exclude(image="")` as well as null: a cleared ImageField stores an
        # empty string, not NULL, and would otherwise seed a broken row.
        for product in CoffeeProduct.objects.exclude(image="").exclude(image__isnull=True)
    ]
    ProductImage.objects.bulk_create(rows)


def unseed(apps, schema_editor):
    # Only the rows this migration could have made: a photo that is the cover
    # and sits first. Anything the roaster has since uploaded is left alone.
    ProductImage = apps.get_model("catalog", "ProductImage")
    ProductImage.objects.filter(is_cover=True, sort_order=0).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0003_productimage"),
    ]

    operations = [
        migrations.RunPython(seed_gallery, unseed),
    ]
