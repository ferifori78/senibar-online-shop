from decimal import Decimal

# The rates live in the ShippingMethod table so the roastery can change them
# without a deploy. The functions here stay the only entry point: callers ask
# for a price, never for a row.
DEFAULT_SHIPPING_METHOD = "standard"


def shipping_cost_for(method, subtotal):
    """Cost of `method` for a given subtotal, honouring the free threshold.

    Raises KeyError for an unknown method so a typo fails loudly rather than
    silently shipping for nothing. Inactive methods still price: a placed order
    references one by key, and it has to keep resolving after it is withdrawn.
    """
    from .models import ShippingMethod

    try:
        config = ShippingMethod.objects.get(key=method)
    except ShippingMethod.DoesNotExist:
        raise KeyError(method) from None
    return config.cost_for(subtotal)


def shipping_options(subtotal=Decimal("0")):
    """The methods as the checkout page renders them, with prices already
    resolved against this cart's subtotal. Withdrawn methods are omitted."""
    from .models import ShippingMethod

    options = []
    for config in ShippingMethod.objects.filter(is_active=True):
        cost = config.cost_for(subtotal)
        options.append(
            {
                "value": config.key,
                "label": config.label,
                "description": config.description,
                "days": config.days,
                "cost": cost,
                "base_cost": config.cost,
                # True only when a normally-paid method became free.
                "is_free": cost == 0 and config.cost > 0,
                "free_over": config.free_over,
            }
        )
    return options


def active_method_keys():
    """Keys a customer may currently choose. Used to build form choices."""
    from .models import ShippingMethod

    return list(ShippingMethod.objects.filter(is_active=True).values_list("key", flat=True))
