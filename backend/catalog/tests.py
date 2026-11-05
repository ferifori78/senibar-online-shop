"""Catalog filter tests.

These cover the storefront filter rail. Every rule here fails quietly rather
than loudly — a wrong filter shows the wrong products, not an error — so the
boundaries are pinned explicitly.
"""

from django.test import TestCase
from django.urls import reverse

from .models import CoffeeProduct


def make_product(name, **kwargs):
    """A published product with the columns the filters read."""
    defaults = dict(
        kind=CoffeeProduct.Kind.LOT,
        species=CoffeeProduct.Species.ARABICA,
        origin_type=CoffeeProduct.OriginType.SINGLE,
        origin_country="اتیوپی",
        status=CoffeeProduct.Status.PUBLISHED,
        price_per_250g=250000,
    )
    return CoffeeProduct.objects.create(name=name, **{**defaults, **kwargs})


class FilterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.yirgacheffe = make_product("یرگاچف")
        cls.robusta = make_product(
            "روبوستای ویتنام",
            species=CoffeeProduct.Species.ROBUSTA,
            origin_country="ویتنام",
        )
        cls.blend = make_product(
            "ترکیب صبحگاهی",
            species=CoffeeProduct.Species.BLEND,
            origin_type=CoffeeProduct.OriginType.MULTI,
        )
        # The case that makes `origin_type` a column of its own rather than
        # something derived from `species`: arabica *and* multi-origin.
        cls.arabica_blend = make_product(
            "ترکیب دو عربیکا",
            origin_type=CoffeeProduct.OriginType.MULTI,
        )
        cls.masala = make_product(
            "چای ماسالا",
            kind=CoffeeProduct.Kind.PANTRY,
            sale_mode=CoffeeProduct.SaleMode.PACKAGE,
            package_grams=200,
            package_price=185000,
            stock_packages=40,
            origin_country="هند",
        )

    def names(self, query=""):
        response = self.client.get(f"{reverse('product-list')}?{query}")
        self.assertEqual(response.status_code, 200)
        return {row["name"] for row in response.json()["results"]}

    # --- kind -------------------------------------------------------------
    def test_kind_splits_coffee_from_pantry(self):
        self.assertEqual(self.names("kind=pantry"), {"چای ماسالا"})
        self.assertNotIn("چای ماسالا", self.names("kind=lot"))

    def test_kind_accepts_both_values_as_a_union(self):
        # The rail's checkboxes: ticking both must mean "both", not "neither".
        self.assertEqual(len(self.names("kind=lot,pantry")), 5)

    def test_no_kind_filter_shows_everything(self):
        # The catalogue keeps working for a client that predates the split.
        self.assertEqual(len(self.names()), 5)

    # --- species ----------------------------------------------------------
    def test_species_matches_several_values(self):
        self.assertEqual(
            self.names("species=robusta,blend"),
            {"روبوستای ویتنام", "ترکیب صبحگاهی"},
        )

    def test_species_never_returns_pantry_items(self):
        # Masala is stored as arabica because the column is not nullable, not
        # because it is a coffee. Filtering on the column alone would put tea
        # in the arabica results.
        self.assertNotIn("چای ماسالا", self.names("species=arabica"))

    def test_unknown_species_matches_nothing(self):
        self.assertEqual(self.names("species=nonsense"), set())

    # --- origin_type ------------------------------------------------------
    def test_origin_type_separates_single_from_multi(self):
        self.assertEqual(
            self.names("origin_type=multi"), {"ترکیب صبحگاهی", "ترکیب دو عربیکا"}
        )

    def test_a_blend_of_arabicas_appears_under_both_axes(self):
        # The reason the two fields are independent. Deriving origin from
        # species would drop this coffee out of one filter or the other.
        self.assertIn("ترکیب دو عربیکا", self.names("species=arabica"))
        self.assertIn("ترکیب دو عربیکا", self.names("origin_type=multi"))

    def test_species_and_origin_type_narrow_together(self):
        self.assertEqual(
            self.names("species=arabica&origin_type=multi"), {"ترکیب دو عربیکا"}
        )

    # --- facets -----------------------------------------------------------
    def facets(self):
        response = self.client.get(reverse("product-facets"))
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_facet_counts_exclude_pantry_from_coffee_axes(self):
        by_value = {row["value"]: row["count"] for row in self.facets()["species"]}
        # Three arabica lots, not four: masala's default value is not a claim
        # about what it is.
        self.assertEqual(by_value["arabica"], 2)
        self.assertEqual(by_value["robusta"], 1)
        self.assertEqual(by_value["blend"], 1)

    def test_facets_omit_an_option_with_no_products(self):
        CoffeeProduct.objects.filter(species="robusta").delete()
        values = {row["value"] for row in self.facets()["species"]}
        # An option that yields an empty grid is worse than no option.
        self.assertNotIn("robusta", values)

    def test_facets_list_each_origin_once(self):
        make_product("یرگاچف دوم", origin_country="اتیوپی")
        origins = self.facets()["origins"]
        # The bug this pins: the model orders by (sort_order, -created_at),
        # and Django puts those columns in the SELECT behind a DISTINCT — so
        # without an explicit `order_by()` the same country appeared once per
        # product grown there, as two identical checkboxes in the rail.
        self.assertEqual(len(origins), len(set(origins)))
        self.assertEqual(origins.count("اتیوپی"), 1)

    def test_facets_leave_out_a_blank_origin(self):
        make_product("ترکیب بی‌مبدأ", origin_country="", origin_type="multi")
        # 0008 clears the country on a blend, so a blank would otherwise show
        # up as a checkbox with no label.
        self.assertNotIn("", self.facets()["origins"])

    def test_facets_count_both_kinds(self):
        by_value = {row["value"]: row["count"] for row in self.facets()["kinds"]}
        self.assertEqual(by_value, {"lot": 4, "pantry": 1})

    def test_facets_ignore_unpublished_products(self):
        make_product("پیش‌نویس", status=CoffeeProduct.Status.DRAFT)
        by_value = {row["value"]: row["count"] for row in self.facets()["kinds"]}
        self.assertEqual(by_value["lot"], 4)


class FeaturedTests(TestCase):
    """The hand-picked shelf on the landing page."""

    @classmethod
    def setUpTestData(cls):
        cls.picked = make_product("یرگاچف", is_featured=True)
        cls.other = make_product("سانتوس")
        cls.draft_pick = make_product(
            "پیش‌نویس", is_featured=True, status=CoffeeProduct.Status.DRAFT
        )

    def names(self, query=""):
        response = self.client.get(f"{reverse('product-list')}?{query}")
        self.assertEqual(response.status_code, 200)
        return {row["name"] for row in response.json()["results"]}

    def test_featured_true_narrows_to_the_picks(self):
        self.assertEqual(self.names("featured=true"), {"یرگاچف"})

    def test_featured_false_is_not_a_request_for_the_rest(self):
        # Only narrows, like `in_stock`. Sending false is the UI's "no
        # preference", not "show me everything nobody picked".
        self.assertEqual(len(self.names("featured=false")), 2)

    def test_a_draft_pick_never_reaches_the_home_page(self):
        # Ticking the box on an unpublished product must not publish it by
        # the back door.
        self.assertNotIn("پیش‌نویس", self.names("featured=true"))

    def test_products_are_not_featured_by_default(self):
        self.assertFalse(make_product("تازه").is_featured)


class NormaliseOriginTests(TestCase):
    """The origin cleanup in migration 0008.

    Tested as a plain function rather than by running the migration: the
    logic is where the risk is, and a table of cases reads better than a
    schema fixture.
    """

    @staticmethod
    def normalise(value):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "mig0008",
            str(
                __import__("pathlib").Path(__file__).parent
                / "migrations"
                / "0008_normalise_origin_country.py"
            ),
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.normalise(value)

    def test_translates_a_known_country(self):
        self.assertEqual(self.normalise("Brazil"), ("برزیل", False))

    def test_collapses_case_and_spacing(self):
        # «Indonesia» and «indonesia» were two checkboxes for one country.
        self.assertEqual(self.normalise("indonesia"), ("اندونزی", False))
        self.assertEqual(self.normalise("  Brazil  "), ("برزیل", False))

    def test_empties_a_placeholder(self):
        self.assertEqual(self.normalise("-"), ("", False))

    def test_a_list_of_countries_becomes_multi_origin(self):
        # The column is «country of origin», singular. A sentence in it is
        # not a country, and `origin_type` now says this properly.
        for value in (
            "Brazil / Colombia / Ethiopia",
            "Brazil, Colombia, India",
            "Brazil  +Indonesia",
            "Brazil + Vietnam",
        ):
            with self.subTest(value=value):
                self.assertEqual(self.normalise(value), ("", True))

    def test_reads_the_countries_out_of_brackets(self):
        self.assertEqual(
            self.normalise("Blend  (Uganda, Ethiopia, Brazil, Colombia),"),
            ("", True),
        )

    def test_the_word_blend_alone_is_multi_origin(self):
        self.assertEqual(self.normalise("Blend"), ("", True))

    def test_leaves_an_unrecognised_value_alone(self):
        # A migration that silently discards what it did not expect is worse
        # than one that leaves a tidy-up for a person.
        self.assertEqual(self.normalise("Papua New Guinea"), ("Papua New Guinea", False))

    def test_does_not_split_a_single_name_containing_a_comma(self):
        # Only one piece is a country, so this is not a blend — clearing it
        # would throw the value away.
        country, multi = self.normalise("Ethiopia, Yirgacheffe")
        self.assertFalse(multi)
        self.assertEqual(country, "Ethiopia, Yirgacheffe")


class OriginTypeMigrationTests(TestCase):
    """The default the column takes for rows that already existed."""

    def test_new_products_default_to_single_origin(self):
        product = make_product("تازه")
        self.assertEqual(product.origin_type, CoffeeProduct.OriginType.SINGLE)
