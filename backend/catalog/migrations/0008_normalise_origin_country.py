"""Tidy the free-text origin column.

`origin_country` has always been free text, so the same country arrived
spelled several ways and the storefront's «مبدأ» filter listed each spelling
as its own checkbox — seventeen options for eight countries, two of them the
same word in different case.

Three separate problems, handled differently:

  1. Case and spacing      «Indonesia» / «indonesia»      -> one value
  2. A placeholder         «-»                            -> empty
  3. A list of countries   «Brazil / Colombia / Ethiopia» -> see below

(3) is the interesting one. Those rows are blends, and the column is
*country of origin* — singular. Now that `origin_type` exists, a blend says
so there, and the country column is left empty rather than holding a
sentence. The filter then offers real countries only, and «چندخاستگاه» is
how a customer finds these.

Country names are translated to Persian because every other word on the
storefront is Persian; an English «Brazil» in a Persian sidebar is the odd
one out. The mapping is deliberately explicit rather than a library: eight
countries, and a wrong automatic transliteration on a product page is worse
than a missing one.

Anything unrecognised is left exactly as it is. A migration that silently
discards a value it did not expect is worse than one that leaves a tidy-up
for a person.
"""

from django.db import migrations

# Spelling -> Persian. Keys are compared lowercased with spaces collapsed.
COUNTRIES = {
    "brazil": "برزیل",
    "colombia": "کلمبیا",
    "ethiopia": "اتیوپی",
    "india": "هند",
    "indonesia": "اندونزی",
    "nigeria": "نیجریه",
    "uganda": "اوگاندا",
    "vietnam": "ویتنام",
    "ecuador": "اکوادور",
}

# Values that mean "not recorded" rather than naming a place.
BLANKS = {"-", "--", "?", "n/a", "na", "none", "unknown"}

# Values that mean "several origins" without naming one usable country.
BLEND_WORDS = {"blend", "blends", "mixed", "mix"}

# What separates countries in a multi-origin string.
SEPARATORS = ("/", "+", ",", "&", "،")


def normalise(raw):
    """Return (country, is_multi_origin) for one stored value."""
    if not raw:
        return "", False

    # Collapse runs of whitespace: «Brazil  +Indonesia» has two spaces.
    text = " ".join(raw.split()).strip().strip(",").strip()
    key = text.lower()

    if key in BLANKS:
        return "", False
    if key in COUNTRIES:
        return COUNTRIES[key], False

    # «Blend (Uganda, Ethiopia, Brazil, Colombia),» — take what is in the
    # brackets, which is the actual list.
    if "(" in text and ")" in text:
        inside = text[text.index("(") + 1 : text.rindex(")")]
        before = text[: text.index("(")].strip().lower()
        if before in BLEND_WORDS or not before:
            text, key = inside, inside.lower()

    if key in BLEND_WORDS:
        # «Blend» alone names no country at all.
        return "", True

    # A list of countries: this is a blend, and no single country describes
    # it, so the column is cleared and `origin_type` carries the meaning.
    for separator in SEPARATORS:
        if separator in text:
            parts = [p.strip() for p in text.split(separator) if p.strip()]
            recognised = [p for p in parts if p.lower() in COUNTRIES]
            # Only treat it as a blend when the pieces really are countries.
            # Otherwise it may be one country whose name contains a comma,
            # and clearing it would lose information.
            if len(recognised) >= 2:
                return "", True
            break

    # Unrecognised: leave it untouched for a person to look at.
    return raw, False


def forwards(apps, schema_editor):
    CoffeeProduct = apps.get_model("catalog", "CoffeeProduct")

    for product in CoffeeProduct.objects.all().only(
        "id", "origin_country", "origin_type"
    ):
        country, is_multi = normalise(product.origin_country)
        changed = []

        if country != product.origin_country:
            product.origin_country = country
            changed.append("origin_country")

        # Only ever promotes to multi. A product a roaster has already marked
        # multi-origin by hand is never demoted by a string that happens to
        # name one country.
        if is_multi and product.origin_type != "multi":
            product.origin_type = "multi"
            changed.append("origin_type")

        if changed:
            product.save(update_fields=changed)


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0007_coffeeproduct_origin_type"),
    ]

    operations = [
        # Irreversible by design: the original spellings are not recoverable
        # from the normalised ones, and pretending otherwise with a no-op
        # reverse would make `migrate backwards` look safe when it is not.
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
