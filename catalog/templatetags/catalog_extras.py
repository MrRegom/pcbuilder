from django import template

register = template.Library()


@register.filter
def clp(value):
    if value in (None, ""):
        return "-"
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        return "-"
    return "$" + f"{n:,}".replace(",", ".")
