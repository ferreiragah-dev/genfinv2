from decimal import Decimal, InvalidOperation
from django import template

register = template.Library()


@register.filter
def money(value):
    try:
        formatted = f"{Decimal(value):,.2f}"
        return formatted.replace(",", "_").replace(".", ",").replace("_", ".")
    except (InvalidOperation, TypeError, ValueError):
        return "0,00"


@register.filter
def absolute(value):
    return abs(value) if value is not None else 0


@register.filter
def initials(user):
    return ((user.first_name or user.username)[:1] + user.last_name[:1]).upper()


@register.filter
def widget_visible(preferences, key):
    return preferences.get(key, True)
