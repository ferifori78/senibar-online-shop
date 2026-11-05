"""Matching a customer's answers to a coffee we actually have.

The questionnaire asks about taste, not about coffee jargon: someone who does
not know what "washed" means still knows whether they like sharp fruit or
dark chocolate. Each answer is translated here into the fields the catalog
already carries — the sensory axes, roast level, process, and brew
suitability — so nothing new has to be recorded per product.

Kept out of the view so the weights are in one readable place, and so the
scoring can be tested without going through HTTP.
"""

from dataclasses import dataclass

from .models import CoffeeProduct

# --- The questionnaire ----------------------------------------------------
# `key` matches the field on the submitted answers; `options` carry the values
# the scorer understands. Served to the client so the wording lives in one
# place and a new option never needs a frontend deploy.
QUESTIONS = [
    {
        "key": "brew",
        "title": "معمولاً چطور قهوه درست می‌کنید؟",
        "hint": "اگر چند روش دارید، آن‌که بیشتر استفاده می‌کنید.",
        "options": [
            {"value": "espresso", "label": "اسپرسو / موکاپات"},
            {"value": "filter", "label": "فیلتر، V60، کمکس"},
            {"value": "french_press", "label": "فرنچ‌پرس"},
            {"value": "unsure", "label": "هنوز مطمئن نیستم"},
        ],
    },
    {
        "key": "milk",
        "title": "با شیر می‌نوشید یا ساده؟",
        "hint": "شیر تلخی و بادی بیشتری می‌طلبد تا طعم گم نشود.",
        "options": [
            {"value": "black", "label": "ساده، بدون شیر"},
            {"value": "milk", "label": "با شیر — لاته، کاپوچینو"},
            {"value": "both", "label": "هر دو، بستگی به روز دارد"},
        ],
    },
    {
        "key": "flavor",
        "title": "کدام توصیف بیشتر وسوسه‌تان می‌کند؟",
        "options": [
            {"value": "fruity", "label": "میوه‌ای و روشن — توت، مرکبات، گل"},
            {"value": "sweet", "label": "شیرین و متعادل — کارامل، عسل، بادام"},
            {"value": "chocolate", "label": "شکلاتی و پُرمایه — کاکائو، آجیل"},
            {"value": "unusual", "label": "چیزی غیرمنتظره — هرچه متفاوت باشد"},
        ],
    },
    {
        "key": "acidity",
        "title": "ترشیِ روشن در قهوه را دوست دارید؟",
        "hint": "منظور همان تُنُدیِ زنده‌ای است که در قهوه‌های اتیوپی می‌آید.",
        "options": [
            {"value": "love", "label": "بله، هرچه بیشتر بهتر"},
            {"value": "some", "label": "کمی، نه غالب"},
            {"value": "avoid", "label": "ترجیح می‌دهم نباشد"},
        ],
    },
    {
        "key": "body",
        "title": "قهوه در دهان چطور بنشیند؟",
        "options": [
            {"value": "light", "label": "سبک و شفاف، مثل چای"},
            {"value": "medium", "label": "متعادل"},
            {"value": "heavy", "label": "سنگین و غلیظ، مثل شربت"},
        ],
    },
    {
        "key": "adventure",
        "title": "اهل تجربه‌های تازه هستید؟",
        "hint": "پروسس‌های بی‌هوازی و عسلی طعم‌های غیرمعمول می‌دهند.",
        "options": [
            {"value": "classic", "label": "کلاسیک را ترجیح می‌دهم"},
            {"value": "open", "label": "بازم به تجربه"},
            {"value": "adventurous", "label": "دنبال چیزی هستم که قبلاً نچشیده‌ام"},
        ],
    },
]

VALID = {q["key"]: {o["value"] for o in q["options"]} for q in QUESTIONS}


@dataclass
class Scored:
    product: CoffeeProduct
    score: float
    reasons: list          # why this coffee, in the customer's words
    against: list          # where it does not match — said out loud


# How much each question can contribute. Flavour and acidity carry the most
# because they are what people actually taste; the adventure question is a
# tiebreaker, not a filter.
WEIGHTS = {
    "brew": 3.0,
    "milk": 2.0,
    "flavor": 4.0,
    "acidity": 4.0,
    "body": 3.0,
    "adventure": 2.0,
}

# Roast levels as a number, so "darker than you asked for" is measurable.
ROAST_SCALE = {
    "light": 1,
    "medium_light": 2,
    "medium": 3,
    "medium_dark": 4,
    "dark": 5,
}

FRUITY_NOTES = (
    "توت", "مرکبات", "لیمو", "پرتقال", "انبه", "هلو", "گل", "یاس", "برگاموت",
    "berry", "citrus", "floral", "jasmine", "peach", "mango",
)
CHOCOLATE_NOTES = (
    "شکلات", "کاکائو", "آجیل", "بادام", "فندق", "کارامل", "تنباکو",
    "chocolate", "cocoa", "nut", "almond", "hazelnut", "caramel",
)


def _roast_value(product):
    return ROAST_SCALE.get(product.roast_level, 3)


def _has_note(product, needles):
    """Does any tasting note contain one of these words?"""
    notes = " ".join(product.flavor_notes or []).lower()
    return any(n.lower() in notes for n in needles)


def _all_process_values(product):
    return {product.process, *(product.processes_extra or [])}


def _score_brew(product, answer):
    """Espresso and filter suitability are recorded per product."""
    if answer == "espresso":
        if product.is_espresso_suitable:
            return 1.0, "برای اسپرسو مناسب است", None
        return 0.0, None, "برای اسپرسو توصیه نشده"
    if answer in ("filter", "french_press"):
        if product.is_filter_suitable:
            return 1.0, "برای دم‌آوری فیلتر مناسب است", None
        return 0.0, None, "برای فیلتر توصیه نشده"
    # "unsure" — no preference to satisfy, so nothing is gained or lost.
    return 0.5, None, None


def _score_milk(product, answer):
    """Milk needs body and a darker roast, or the coffee disappears in it."""
    if answer == "milk":
        strong = product.body >= 3 and _roast_value(product) >= 3
        if strong:
            return 1.0, "بادی و رستش با شیر گم نمی‌شود", None
        return 0.2, None, "ممکن است در شیر کم‌رنگ شود"
    if answer == "black":
        # A light, clean cup rewards drinking it neat.
        if _roast_value(product) <= 3:
            return 1.0, "ساده نوشیدنش بهترین حالت است", None
        return 0.6, None, None
    return 0.7, None, None


def _score_flavor(product, answer):
    if answer == "fruity":
        if _has_note(product, FRUITY_NOTES):
            return 1.0, "نت‌های میوه‌ای و روشن دارد", None
        if product.acidity >= 4:
            return 0.7, "پروفایل روشنی دارد", None
        return 0.1, None, "چندان میوه‌ای نیست"
    if answer == "chocolate":
        if _has_note(product, CHOCOLATE_NOTES):
            return 1.0, "نت‌های شکلاتی و آجیلی دارد", None
        if _roast_value(product) >= 4:
            return 0.7, "رست تیره‌تر، پُرمایه", None
        return 0.1, None, "پروفایل شکلاتی ندارد"
    if answer == "sweet":
        if product.sweetness >= 4:
            return 1.0, "شیرینی محسوسی دارد", None
        if product.sweetness >= 3:
            return 0.6, None, None
        return 0.2, None, "شیرینی‌اش غالب نیست"
    if answer == "unusual":
        exotic = _all_process_values(product) & {"anaerobic", "honey", "natural"}
        if exotic:
            return 1.0, "پروسس غیرمعمول دارد", None
        return 0.2, None, "پروسس کلاسیک دارد"
    return 0.5, None, None


def _score_acidity(product, answer):
    if answer == "love":
        if product.acidity >= 4:
            return 1.0, "اسیدیته‌ی بالا و زنده", None
        if product.acidity == 3:
            return 0.5, None, None
        return 0.1, None, "اسیدیته‌ی پایینی دارد"
    if answer == "avoid":
        if product.acidity <= 2:
            return 1.0, "اسیدیته‌ی کم", None
        if product.acidity == 3:
            return 0.5, None, None
        return 0.0, None, "اسیدیته‌اش بالاست"
    # "some" — the middle is exactly right, the extremes are not.
    return (1.0, "اسیدیته‌ی متعادل", None) if product.acidity == 3 else (0.6, None, None)


def _score_body(product, answer):
    want = {"light": 2, "medium": 3, "heavy": 5}.get(answer, 3)
    distance = abs(product.body - want)
    if distance == 0:
        return 1.0, "بادی دقیقاً در همان حدی است که خواستید", None
    if distance == 1:
        return 0.6, None, None
    return 0.1, None, "بادی‌اش با آنچه خواستید فاصله دارد"


def _score_adventure(product, answer):
    exotic = _all_process_values(product) & {"anaerobic", "honey"}
    if answer == "adventurous":
        if exotic:
            return 1.0, "پروسس تجربی و کمیاب", None
        return 0.3, None, None
    if answer == "classic":
        if exotic:
            return 0.3, None, "پروسسش غیرمعمول است"
        return 1.0, "پروفایل کلاسیک و آشنا", None
    return 0.8, None, None


SCORERS = {
    "brew": _score_brew,
    "milk": _score_milk,
    "flavor": _score_flavor,
    "acidity": _score_acidity,
    "body": _score_body,
    "adventure": _score_adventure,
}


def score_product(product, answers):
    """Score one coffee against the answers, with the reasons it earned."""
    total = 0.0
    possible = 0.0
    reasons, against = [], []

    for key, weight in WEIGHTS.items():
        answer = answers.get(key)
        if not answer:
            # Unanswered questions are skipped entirely rather than counted as
            # a miss, so a partly-filled questionnaire still ranks sensibly
            # instead of scoring everything near zero.
            continue

        fraction, reason, complaint = SCORERS[key](product, answer)
        total += fraction * weight
        possible += weight
        if reason:
            reasons.append(reason)
        if complaint:
            against.append(complaint)

    # A percentage of what could have been earned, so the number means the
    # same thing however many questions were answered.
    percent = (total / possible * 100) if possible else 0.0
    return Scored(product=product, score=round(percent, 1), reasons=reasons, against=against)


def recommend(answers, *, limit=3, prefer_in_stock=True):
    """Rank the published catalog against the answers.

    Always returns something when the shop has any coffee at all: a customer
    who reaches the end of six questions and is told "nothing matches" has
    been wasted. The score and the `against` notes carry the honesty instead.
    """
    # Lots only. The six questions score acidity, body, process and roast —
    # axes a pantry item does not have, so every one of them would land on the
    # same neutral score and crowd out the coffees the quiz exists to find.
    products = list(
        CoffeeProduct.objects.published().lots().prefetch_related("batches", "images")
    )
    if not products:
        return []

    scored = [score_product(p, answers) for p in products]

    # In-stock coffee first, then by score. Recommending something we cannot
    # ship today would be the one result worse than a weak match.
    if prefer_in_stock:
        scored.sort(key=lambda s: (s.product.is_in_stock, s.score), reverse=True)
    else:
        scored.sort(key=lambda s: s.score, reverse=True)

    return scored[:limit]


def validate_answers(raw):
    """Keep only answers the scorer understands.

    Silently dropping an unknown value rather than raising: this is a taste
    quiz, and a stale client sending a retired option should still get a
    recommendation instead of an error page.
    """
    if not isinstance(raw, dict):
        return {}
    return {
        key: value
        for key, value in raw.items()
        if key in VALID and value in VALID[key]
    }
