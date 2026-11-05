"""Persian and Arabic-Indic digit normalization.

The storefront converts these as they are typed, but that is a convenience for
the person at the keyboard, not a guarantee: the API is public, an older build
may still be cached in a browser, and rows written before the fix already hold
Persian digits. Normalizing here is what makes a phone number reliably
comparable and a postal code reliably ten characters.
"""

# Value order 0-9. Persian keyboards emit the first set; some Arabic layouts
# and older Android IMEs emit the second.
_PERSIAN = "۰۱۲۳۴۵۶۷۸۹"
_ARABIC = "٠١٢٣٤٥٦٧٨٩"

_TRANSLATION = {ord(c): str(i) for i, c in enumerate(_PERSIAN)}
_TRANSLATION.update({ord(c): str(i) for i, c in enumerate(_ARABIC)})


def to_english_digits(value):
    """Rewrite any Persian or Arabic-Indic digits as ASCII, leaving the rest."""
    if not isinstance(value, str):
        return value
    return value.translate(_TRANSLATION)


def digits_only(value):
    """ASCII digits and nothing else — for a field holding just a number."""
    if not isinstance(value, str):
        return value
    return "".join(c for c in to_english_digits(value) if c.isdigit())
