from django.db.models import Count
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import SAFE_METHODS, AllowAny, BasePermission
from rest_framework.response import Response

from .filters import CoffeeProductFilter
from .models import CoffeeProduct, ProductImage, RoastBatch
# Imported as a module: the viewset has an action called `recommend`, and a
# bare import of the same name would be shadowed by it.
from . import recommend as recommender
from .recommend import QUESTIONS, validate_answers
from .serializers import (
    CoffeeProductDetailSerializer,
    CoffeeProductListSerializer,
    ProductImageSerializer,
    PublicRoastBatchSerializer,
    RoastBatchSerializer,
)


class IsRoasterOrReadOnly(BasePermission):
    """Anyone may browse the catalog; only roasters and admins may change it."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user.is_authenticated and request.user.is_roaster)


class CoffeeProductViewSet(viewsets.ModelViewSet):
    """The storefront catalog. Looked up by slug so URLs stay readable."""

    permission_classes = (IsRoasterOrReadOnly,)
    lookup_field = "slug"
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filterset_class = CoffeeProductFilter
    search_fields = ("name", "origin_country", "origin_region", "farm", "producer", "varietal")
    ordering_fields = ("price_per_250g", "cupping_score", "created_at", "name", "sort_order")
    # The shelf order set in the panel. OrderingFilter's default has to say so
    # explicitly: it overrides the model's Meta.ordering, so leaving this at
    # "-created_at" would make the drag-and-drop order have no effect.
    ordering = ("sort_order", "-created_at")

    def filter_queryset(self, queryset):
        """Break ties in the shelf order by recency.

        OrderingFilter applies exactly the field it is given, so `sort_order`
        alone leaves every product sharing a number — which is all of them
        until the roaster drags something — in whatever order the database
        returns. That order is not stable across pages, so a product can
        appear twice while another never shows.
        """
        queryset = super().filter_queryset(queryset)
        requested = self.request.query_params.get("ordering", "")
        if requested.strip() == "sort_order":
            return queryset.order_by("sort_order", "-created_at")
        return queryset

    def get_queryset(self):
        qs = CoffeeProduct.objects.all()

        # Customers see only published coffee; staff see drafts too.
        user = self.request.user
        if not (user.is_authenticated and user.is_roaster):
            qs = qs.published()

        if self.action == "list":
            # The list serializer reports stock, which would otherwise be one
            # extra query per card.
            return qs.with_available_stock()
        return qs.prefetch_related("batches", "images")

    def get_serializer_class(self):
        if self.action == "list":
            return CoffeeProductListSerializer
        return CoffeeProductDetailSerializer

    @action(detail=True, methods=["get"], url_path="batches")
    def batches(self, request, slug=None):
        """Roast batches for this coffee. Customers get roast dates and
        freshness; staff get the full record including quantities."""
        product = self.get_object()
        is_staff = request.user.is_authenticated and request.user.is_roaster

        batches = product.batches.all() if is_staff else product.batches.fresh()
        serializer_class = RoastBatchSerializer if is_staff else PublicRoastBatchSerializer
        return Response(serializer_class(batches, many=True).data)

    # --- Gallery ----------------------------------------------------------
    def _gallery(self, product):
        """The gallery, read fresh from the database.

        `get_queryset` prefetches `images`, so `product.images.all()` serves
        the cache captured before this request changed anything — a reorder or
        a cover swap would return the order it had on the way in. Going
        through the manager directly bypasses that cache.

        The request goes into the context so ImageField renders an absolute
        URL. Without it the path is relative and resolves against whatever
        origin the panel is served from, which is only the same host by
        coincidence of the production nginx.
        """
        return ProductImageSerializer(
            ProductImage.objects.filter(product=product),
            many=True,
            context=self.get_serializer_context(),
        ).data

    @action(
        detail=True,
        methods=["get", "post"],
        url_path="images",
        parser_classes=(MultiPartParser, FormParser),
    )
    def images(self, request, slug=None):
        """List the gallery, or add one photograph to it."""
        product = self.get_object()

        if request.method == "GET":
            return Response(self._gallery(product))

        serializer = ProductImageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # New photos go to the end of the gallery unless the roaster says
        # otherwise, so an upload never silently reshuffles the existing order.
        if not serializer.validated_data.get("sort_order"):
            last = ProductImage.objects.filter(product=product).order_by("-sort_order").first()
            serializer.validated_data["sort_order"] = (last.sort_order + 1) if last else 0

        photo = serializer.save(product=product)

        # The first photograph uploaded becomes the cover: a product whose
        # gallery is not empty should never render with no picture.
        if not ProductImage.objects.filter(product=product, is_cover=True).exists():
            photo.make_cover()

        return Response(
            ProductImageSerializer(photo, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["delete"], url_path=r"images/(?P<image_id>\d+)")
    def delete_image(self, request, slug=None, image_id=None):
        """Remove one photograph from the gallery."""
        product = self.get_object()
        photo = ProductImage.objects.filter(product=product, pk=image_id).first()
        if photo is None:
            return Response(
                {"detail": "این تصویر پیدا نشد."}, status=status.HTTP_404_NOT_FOUND
            )

        was_cover = photo.is_cover
        photo.delete()

        # Deleting the cover must promote another photo, not leave the product
        # pointing at a file that no longer exists.
        if was_cover:
            replacement = ProductImage.objects.filter(product=product).first()
            if replacement is not None:
                replacement.make_cover()
            else:
                product.image = None
                product.save(update_fields=["image", "updated_at"])

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path=r"images/(?P<image_id>\d+)/cover")
    def set_cover(self, request, slug=None, image_id=None):
        """Promote one photograph to be the product's cover."""
        product = self.get_object()
        photo = ProductImage.objects.filter(product=product, pk=image_id).first()
        if photo is None:
            return Response(
                {"detail": "این تصویر پیدا نشد."}, status=status.HTTP_404_NOT_FOUND
            )

        photo.make_cover()
        return Response(self._gallery(product))

    @action(detail=True, methods=["post"], url_path="images/reorder")
    def reorder_images(self, request, slug=None):
        """Rewrite the gallery order from a list of image ids."""
        product = self.get_object()
        ids = request.data.get("order")
        if not isinstance(ids, list) or not ids:
            return Response(
                {"order": "فهرستی از شناسه‌های تصویر لازم است."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        owned = {img.pk: img for img in ProductImage.objects.filter(product=product)}
        # Refuse the whole request rather than reordering what matches: a
        # partial apply would leave the gallery in an order the roaster never
        # asked for.
        unknown = [i for i in ids if i not in owned]
        if unknown:
            return Response(
                {"order": "این تصویرها متعلق به این محصول نیستند."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        for position, image_id in enumerate(ids):
            photo = owned[image_id]
            if photo.sort_order != position:
                photo.sort_order = position
                photo.save(update_fields=["sort_order"])

        return Response(self._gallery(product))

    @action(detail=False, methods=["get"], permission_classes=(AllowAny,), url_path="quiz")
    def quiz(self, request):
        """The questionnaire, so its wording lives on the server.

        Returned even when the catalog is empty: the questions are static, and
        the client decides what to do with no results.
        """
        return Response({"questions": QUESTIONS})

    @action(
        detail=False,
        methods=["post"],
        permission_classes=(AllowAny,),
        url_path="recommend",
    )
    def recommend(self, request):
        """Score the catalog against a customer's answers."""
        answers = validate_answers(request.data.get("answers"))
        if not answers:
            return Response(
                {"answers": "دست‌کم به یک پرسش پاسخ دهید."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        results = recommender.recommend(answers)
        context = self.get_serializer_context()

        return Response(
            {
                "answered": len(answers),
                "results": [
                    {
                        "product": CoffeeProductListSerializer(s.product, context=context).data,
                        "score": s.score,
                        "reasons": s.reasons,
                        "against": s.against,
                    }
                    for s in results
                ],
            }
        )

    @action(detail=False, methods=["post"], url_path="reorder")
    def reorder(self, request):
        """Rewrite the shelf order from a list of product slugs.

        Sent by the panel after a drag. Only the products named are touched,
        so reordering one page of a paginated list does not renumber the rest.
        """
        slugs = request.data.get("order")
        if not isinstance(slugs, list) or not slugs:
            return Response(
                {"order": "فهرستی از محصولات لازم است."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        products = {p.slug: p for p in CoffeeProduct.objects.filter(slug__in=slugs)}
        unknown = [s for s in slugs if s not in products]
        if unknown:
            # Refuse the whole request: applying part of a drag would leave the
            # shelf in an order nobody chose.
            return Response(
                {"order": "این محصول‌ها پیدا نشدند: " + "، ".join(map(str, unknown))},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Positions start from the lowest sort_order already in the set, so a
        # reordered page keeps its place relative to products not on it.
        base = min((p.sort_order for p in products.values()), default=0)

        changed = []
        for position, slug in enumerate(slugs):
            product = products[slug]
            target = base + position
            if product.sort_order != target:
                product.sort_order = target
                product.save(update_fields=["sort_order", "updated_at"])
                changed.append(slug)

        return Response({"reordered": changed, "count": len(changed)})

    # --- Retiring a product -----------------------------------------------
    @action(detail=True, methods=["post"])
    def archive(self, request, slug=None):
        """Retire a product without erasing it."""
        product = self.get_object()
        changed = product.archive()
        return Response(
            {
                **CoffeeProductDetailSerializer(product, context={"request": request}).data,
                "changed": changed,
            }
        )

    def destroy(self, request, *args, **kwargs):
        """Erase a product, or archive it when records depend on it.

        A plain delete raises ProtectedError for anything a customer has
        ordered or that has a roast batch, which surfaced as a bare 500. The
        roaster's intent — "get this off the shop" — is satisfied either way,
        so the response says which of the two happened and why.
        """
        product = self.get_object()
        blockers = product.deletion_blockers()

        if not any(blockers.values()):
            product.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        product.archive()

        # Persian digits: the rest of the sentence is Persian, and a Latin
        # numeral in the middle of it reads as a stray token.
        def fa(number):
            return str(number).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))

        reasons = []
        if blockers["orders"]:
            reasons.append(f"{fa(blockers['orders'])} سفارش")
        if blockers["batches"]:
            reasons.append(f"{fa(blockers['batches'])} بچ رست")

        return Response(
            {
                "archived": True,
                "blockers": blockers,
                "detail": (
                    f"این محصول {' و '.join(reasons)} دارد، پس پاک نشد و بایگانی شد. "
                    "از فروشگاه حذف است و در جستجو دیده نمی‌شود، ولی فاکتورهای "
                    "قبلی مشتری‌ها سالم می‌مانند."
                ),
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], permission_classes=(AllowAny,))
    def facets(self, request):
        """The values actually present in the catalog, for building filter UI
        that never offers an option yielding zero results."""
        published = CoffeeProduct.objects.published()

        notes = set()
        for values in published.values_list("flavor_notes", flat=True):
            notes.update(values or [])

        # Counted rather than listed from `choices`: the sidebar prints the
        # number beside each option, and an option with no products is left
        # out entirely so nobody clicks their way to an empty grid.
        def counted(field, labels, queryset=None):
            rows = dict(
                (queryset if queryset is not None else published)
                .values_list(field)
                .annotate(n=Count("id"))
                .values_list(field, "n")
            )
            return [
                {"value": value, "label": label, "count": rows[value]}
                for value, label in labels
                if rows.get(value)
            ]

        return Response(
            {
                # `order_by()` with no arguments is load-bearing. The model
                # orders by (sort_order, -created_at) by default, and Django
                # adds those columns to the SELECT behind a DISTINCT — so
                # every row stays unique and the same country is listed once
                # per product that comes from it.
                # Blends and unrecorded origins hold an empty string, which
                # would otherwise become a nameless checkbox in the rail.
                # A blend is found through «چندخاستگاه» instead.
                "origins": sorted(
                    published.order_by()
                    .exclude(origin_country="")
                    .values_list("origin_country", flat=True)
                    .distinct()
                ),
                "kinds": counted(
                    "kind", [("lot", "قهوه‌ها"), ("pantry", "پودری‌جات")]
                ),
                # Counted over lots only. A pantry item carries the column
                # defaults — arabica, single-origin — because the fields are
                # not nullable, so counting it here would advertise hot
                # chocolate as an arabica and inflate every number.
                "species": counted(
                    "species",
                    [("arabica", "عربیکا"), ("robusta", "روبوستا"), ("blend", "ترکیبی")],
                    queryset=published.lots(),
                ),
                "origin_types": counted(
                    "origin_type",
                    [("single", "تک‌خاستگاه"), ("multi", "چندخاستگاه")],
                    queryset=published.lots(),
                ),
                # Persian, and counted, like every other group in the rail.
                # The model's own choice labels are English — they are what
                # the Django admin shows — so the storefront wording lives
                # here rather than leaving «Washed» in a Persian sidebar.
                # Lots only: a pantry item is not processed.
                "processes": counted(
                    "process",
                    [
                        ("washed", "شسته"),
                        ("natural", "طبیعی"),
                        ("honey", "عسلی"),
                        ("anaerobic", "بی‌هوازی"),
                        ("wet_hulled", "نیمه‌شسته"),
                        ("other", "سایر"),
                    ],
                    queryset=published.lots(),
                ),
                "roast_levels": [
                    {"value": v, "label": l} for v, l in CoffeeProduct.RoastLevel.choices
                ],
                "flavor_notes": sorted(notes),
                "price_range": {
                    "min": published.order_by("price_per_250g")
                    .values_list("price_per_250g", flat=True)
                    .first(),
                    "max": published.order_by("-price_per_250g")
                    .values_list("price_per_250g", flat=True)
                    .first(),
                },
            }
        )


class RoastBatchViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Batch management — the Terminal register. Staff only.

    A batch that has been sold from is never deleted, only withdrawn: orders
    reference it and the audit trail has to survive. A batch nobody has ordered
    from — a typo'd code, a roast that never happened — can be removed outright,
    because keeping it would only clutter the shelf with a fiction.
    """

    serializer_class = RoastBatchSerializer
    permission_classes = (IsRoasterOrReadOnly,)
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filterset_fields = ("product", "status", "roast_date")
    search_fields = ("batch_code", "product__name")
    ordering_fields = ("roast_date", "remaining_grams", "created_at")
    ordering = ("-roast_date",)

    def get_queryset(self):
        return RoastBatch.objects.select_related("product", "roaster")

    def perform_create(self, serializer):
        serializer.save(roaster=self.request.user)

    def destroy(self, request, *args, **kwargs):
        batch = self.get_object()

        # Any order line pointing here makes the batch part of the record.
        if batch.order_items.exists():
            return Response(
                {
                    "detail": (
                        f"بچ {batch.batch_code} در سفارش‌ها استفاده شده و قابل حذف نیست. "
                        "به‌جای آن وضعیتش را «خارج شده» کنید."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        # Likewise if stock has already left it: that difference happened, and
        # deleting the batch would erase where it went.
        if batch.remaining_grams != batch.initial_grams:
            return Response(
                {
                    "detail": (
                        f"از بچ {batch.batch_code} برداشت شده است و قابل حذف نیست. "
                        "به‌جای آن وضعیتش را «خارج شده» کنید."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        return super().destroy(request, *args, **kwargs)
