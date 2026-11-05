from django.conf import settings
from rest_framework import serializers

from .images import shrink
from .models import CoffeeProduct, ProductImage, RoastBatch


class ProductImageSerializer(serializers.ModelSerializer):
    """One gallery photograph."""

    class Meta:
        model = ProductImage
        fields = ("id", "image", "alt_text", "is_cover", "sort_order", "created_at")
        # The cover is set through its own endpoint, which demotes the previous
        # one; writing the flag here would let two covers be posted and trip
        # the unique constraint.
        read_only_fields = ("id", "is_cover", "created_at")

    def validate_image(self, value):
        """Refuse an oversized file, then shrink what is left.

        The ceiling is checked before Pillow touches the file: decoding an
        enormous image allocates width x height x 4 bytes of memory, so an
        unbounded upload is a way to exhaust the server's RAM, not merely a
        way to waste disk.
        """
        limit = settings.MAX_IMAGE_UPLOAD_BYTES
        if value.size > limit:
            raise serializers.ValidationError(
                f"حجم تصویر نباید بیشتر از {limit // (1024 * 1024)} مگابایت باشد."
            )
        return shrink(value)


class RoastBatchSerializer(serializers.ModelSerializer):
    """Full batch record — admin / Terminal register."""

    product_name = serializers.CharField(source="product.name", read_only=True)
    days_since_roast = serializers.IntegerField(read_only=True)
    freshness = serializers.CharField(read_only=True)
    available_grams = serializers.IntegerField(read_only=True)
    is_sellable = serializers.BooleanField(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = RoastBatch
        fields = (
            "id", "batch_code", "product", "product_name", "roast_date", "roaster",
            "initial_grams", "remaining_grams", "reserved_grams", "available_grams",
            "roast_profile", "development_time_ratio", "notes",
            "status", "status_display", "days_since_roast", "freshness", "is_sellable",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "remaining_grams", "reserved_grams", "created_at", "updated_at")

    def validate_roast_date(self, value):
        from django.utils import timezone

        if value > timezone.localdate():
            raise serializers.ValidationError("Roast date cannot be in the future.")
        return value


class PublicRoastBatchSerializer(serializers.ModelSerializer):
    """What a customer may see: roast date and freshness, never quantities."""

    freshness = serializers.CharField(read_only=True)
    days_since_roast = serializers.IntegerField(read_only=True)

    class Meta:
        model = RoastBatch
        fields = ("id", "batch_code", "roast_date", "days_since_roast", "freshness")


class CoffeeProductListSerializer(serializers.ModelSerializer):
    """Grid / listing payload — deliberately lean."""

    available_grams = serializers.IntegerField(read_only=True)
    available_packages = serializers.IntegerField(read_only=True)
    is_in_stock = serializers.BooleanField(read_only=True)
    process_display = serializers.CharField(source="get_process_display", read_only=True)
    roast_level_display = serializers.CharField(source="get_roast_level_display", read_only=True)
    all_processes = serializers.ReadOnlyField()
    all_roast_levels = serializers.ReadOnlyField()

    class Meta:
        model = CoffeeProduct
        fields = (
            "id", "name", "slug", "subtitle", "origin_country", "origin_region",
            "species", "origin_type",
            "process", "process_display", "roast_level", "roast_level_display",
            "all_processes", "all_roast_levels",
            "flavor_notes", "price_per_250g", "image", "sort_order",
            "is_featured",
            "available_grams", "is_in_stock",
            # The card needs `kind` to know whether to print a roast level and
            # a process at all, and the package fields to show one price
            # instead of a "from …" range.
            "kind", "brand", "sale_mode", "package_grams", "package_price",
            "available_packages",
        )
        # The card shows one photograph; the gallery belongs on the detail
        # payload, not on every row of the grid.


class CoffeeProductDetailSerializer(serializers.ModelSerializer):
    """Product page payload, including the freshest batch we'd ship from."""

    available_grams = serializers.IntegerField(read_only=True)
    is_in_stock = serializers.BooleanField(read_only=True)
    process_display = serializers.CharField(source="get_process_display", read_only=True)
    roast_level_display = serializers.CharField(source="get_roast_level_display", read_only=True)
    species_display = serializers.CharField(source="get_species_display", read_only=True)
    origin_type_display = serializers.CharField(
        source="get_origin_type_display", read_only=True
    )
    all_processes = serializers.ReadOnlyField()
    all_roast_levels = serializers.ReadOnlyField()
    current_batch = serializers.SerializerMethodField()
    price_options = serializers.SerializerMethodField()
    cup_profile = serializers.SerializerMethodField()
    # Read-only here: photos are added and removed through /images/, so a
    # product PATCH can never silently drop the gallery by omitting the key.
    images = ProductImageSerializer(many=True, read_only=True)

    class Meta:
        model = CoffeeProduct
        fields = (
            "id", "name", "slug", "subtitle", "description",
            "origin_country", "origin_region", "farm", "producer", "varietal",
            "altitude_masl", "harvest_year",
            "species", "species_display", "origin_type", "origin_type_display",
            "process", "process_display",
            "roast_level", "roast_level_display",
            "processes_extra", "roast_levels_extra",
            "all_processes", "all_roast_levels",
            "flavor_notes", "cupping_score",
            # The four axes are writable individually; `cup_profile` is the
            # read-only bundle the product page renders.
            "acidity", "body", "sweetness", "bitterness", "cup_profile",
            "price_per_250g", "price_options",
            "is_espresso_suitable", "is_filter_suitable",
            "image", "images", "status", "sort_order", "is_featured",
            "available_grams", "is_in_stock", "current_batch",
            # --- Pantry items ---
            "kind", "brand", "production_year", "best_before",
            "ingredients", "preparation",
            "sale_mode", "package_grams", "package_price",
            "stock_packages", "stock_grams", "low_stock_threshold",
            "available_packages", "is_low_stock",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "slug", "created_at", "updated_at")

    def validate(self, attrs):
        """Reject a pantry item that cannot be priced or counted.

        Caught here rather than at checkout: a package with no price would
        reach the storefront as a free product, and the first anyone would
        know is an order for nothing.
        """
        kind = attrs.get("kind", getattr(self.instance, "kind", CoffeeProduct.Kind.LOT))
        if kind != CoffeeProduct.Kind.PANTRY:
            return attrs

        mode = attrs.get("sale_mode", getattr(self.instance, "sale_mode", None))
        if mode == CoffeeProduct.SaleMode.PACKAGE:
            price = attrs.get("package_price", getattr(self.instance, "package_price", None))
            if not price:
                raise serializers.ValidationError(
                    {"package_price": "قیمت بسته را وارد کنید."}
                )
            grams = attrs.get("package_grams", getattr(self.instance, "package_grams", None))
            if not grams:
                raise serializers.ValidationError(
                    {"package_grams": "وزن بسته را وارد کنید."}
                )
        return attrs

    def get_current_batch(self, obj):
        batch = obj.freshest_batch()
        return PublicRoastBatchSerializer(batch).data if batch else None

    def get_price_options(self, obj):
        """Price for each sellable weight, so the client never does the maths.

        A package item has exactly one option — the pack — so the weight
        selector on the product page collapses to a single stated size rather
        than offering four sizes that do not exist.
        """
        if obj.sold_by_package:
            return [{
                "weight_grams": obj.package_grams or 0,
                "price": obj.price_for_grams(obj.package_grams or 0),
            }]
        return [
            {"weight_grams": grams, "price": obj.price_for_grams(grams)}
            for grams in (100, 250, 500, 1000)
        ]

    def get_cup_profile(self, obj):
        return {
            "acidity": obj.acidity,
            "body": obj.body,
            "sweetness": obj.sweetness,
            "bitterness": obj.bitterness,
        }

    def validate_flavor_notes(self, value):
        if not isinstance(value, list) or any(not isinstance(n, str) for n in value):
            raise serializers.ValidationError("Flavor notes must be a list of strings.")
        return value

    @staticmethod
    def _validate_choices(value, choices, label):
        """A JSONField accepts anything, so the choices have to be checked here.

        An unrecognised value would be stored happily and then never match a
        filter — the product would quietly stop appearing under a facet with
        nothing to show why.
        """
        if not isinstance(value, list):
            raise serializers.ValidationError(f"{label} باید یک فهرست باشد.")
        allowed = {c[0] for c in choices}
        bad = [v for v in value if v not in allowed]
        if bad:
            raise serializers.ValidationError(f"مقدار نامعتبر: {'، '.join(map(str, bad))}")
        # De-duplicated, order preserved.
        return list(dict.fromkeys(value))

    def validate_processes_extra(self, value):
        return self._validate_choices(value, CoffeeProduct.Process.choices, "پروسس‌ها")

    def validate_roast_levels_extra(self, value):
        return self._validate_choices(
            value, CoffeeProduct.RoastLevel.choices, "درجه‌های رست"
        )

    def validate(self, attrs):
        """Keep the primary value out of its own extras list.

        Otherwise `all_processes` would show it twice, and a later change of
        the primary would leave the old value behind as a phantom extra.
        """
        for primary, extra in (
            ("process", "processes_extra"),
            ("roast_level", "roast_levels_extra"),
        ):
            if extra in attrs:
                current = attrs.get(primary, getattr(self.instance, primary, None))
                attrs[extra] = [v for v in attrs[extra] if v != current]
        return attrs
