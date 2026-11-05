import django_filters as filters
from django.db.models import Q

from .models import CoffeeProduct


class CoffeeProductFilter(filters.FilterSet):
    """Storefront filters. Multi-value fields accept a comma-separated list so
    the UI can toggle several origins or processes at once."""

    origin = filters.BaseInFilter(field_name="origin_country", lookup_expr="in")
    process = filters.BaseInFilter(method="filter_process")
    roast_level = filters.BaseInFilter(method="filter_roast_level")
    # Multi-value: someone narrowing to "arabica" and "blend" at once is asking
    # for the union, not for nothing. A plain CharFilter would match neither.
    species = filters.BaseInFilter(method="filter_coffee_only")
    origin_type = filters.BaseInFilter(method="filter_coffee_only")

    min_price = filters.NumberFilter(field_name="price_per_250g", lookup_expr="gte")
    max_price = filters.NumberFilter(field_name="price_per_250g", lookup_expr="lte")
    min_score = filters.NumberFilter(field_name="cupping_score", lookup_expr="gte")

    brew_method = filters.ChoiceFilter(
        choices=[("espresso", "Espresso"), ("filter", "Filter")],
        method="filter_brew_method",
        label="Suitable for",
    )
    in_stock = filters.BooleanFilter(method="filter_in_stock")
    # The landing page asks for these by name. Only narrows: `featured=false`
    # is not a request for everything the roaster did *not* pick.
    featured = filters.BooleanFilter(
        method="filter_featured", label="Featured on the home page"
    )
    note = filters.CharFilter(method="filter_note", label="Flavor note")
    # `lot` or `pantry`. Unfiltered shows both, so the catalogue keeps working
    # for anyone who has not been updated to know the distinction exists.
    # Accepts a list for the same reason as `species`: the sidebar toggles are
    # checkboxes, and ticking both must mean "both", not "neither".
    kind = filters.BaseInFilter(field_name="kind", lookup_expr="in")

    class Meta:
        model = CoffeeProduct
        fields = ("origin", "process", "roast_level", "species", "origin_type", "kind")

    @staticmethod
    def _match_primary_or_extra(queryset, values, primary_field, extra_field):
        """Match the primary column OR the extras list.

        A coffee whose second process is Natural has to appear under the
        Natural filter, or the multi-select would be invisible to customers.

        The extras are matched with `icontains` on the JSON text rather than
        the JSONField `contains` lookup: the latter is unsupported on SQLite,
        which would make this filter untestable outside production. The values
        are fixed choice slugs with no substring overlap ("washed" is not
        inside "natural"), so a text match is exact in practice. `"value"`
        is quoted into the pattern so a slug cannot match a fragment of
        another word.
        """
        if not values:
            return queryset

        query = Q()
        for value in values:
            if not value:
                continue
            query |= Q(**{primary_field: value}) | Q(
                **{f"{extra_field}__icontains": f'"{value}"'}
            )

        # `distinct` is not needed — neither side joins — but an empty query
        # must not turn into "match everything".
        return queryset.filter(query) if query else queryset

    def filter_process(self, queryset, name, value):
        return self._match_primary_or_extra(queryset, value, "process", "processes_extra")

    def filter_roast_level(self, queryset, name, value):
        return self._match_primary_or_extra(
            queryset, value, "roast_level", "roast_levels_extra"
        )

    def filter_coffee_only(self, queryset, name, value):
        """Match `species` / `origin_type`, and exclude pantry items outright.

        Both columns are non-nullable, so masala tea is stored as arabica and
        single-origin whether or not that means anything. Filtering on the
        column alone would put hot chocolate in the arabica results; anyone
        asking about species is asking about coffee.
        """
        if not value:
            return queryset
        return queryset.lots().filter(**{f"{name}__in": value})

    def filter_brew_method(self, queryset, name, value):
        if value == "espresso":
            return queryset.filter(is_espresso_suitable=True)
        if value == "filter":
            return queryset.filter(is_filter_suitable=True)
        return queryset

    def filter_in_stock(self, queryset, name, value):
        # Only narrows; `in_stock=false` is not a request for sold-out coffee.
        return queryset.in_stock() if value else queryset

    def filter_featured(self, queryset, name, value):
        return queryset.featured() if value else queryset

    def filter_note(self, queryset, name, value):
        """Match a tasting note inside the JSON list."""
        return queryset.filter(flavor_notes__icontains=value)
