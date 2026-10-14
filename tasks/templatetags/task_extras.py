"""Custom template filters for rendering task metadata consistently."""
from django import template

register = template.Library()


@register.filter
def urlencode_preserve(query_dict, exclude_key):
    """Return the current querystring with one key removed, so pagination /
    filter links can toggle a single param without losing the others."""
    qd = query_dict.copy()
    qd.pop(exclude_key, None)
    return qd.urlencode()


@register.simple_tag
def query_transform(request, **kwargs):
    """Build a querystring based on the current request's GET params, with
    the given kwargs overridden. Used so filter/sort/pagination links keep
    each other's state (e.g. clicking 'Upcoming' keeps the active search)."""
    updated = request.GET.copy()
    for key, value in kwargs.items():
        if value is None:
            updated.pop(key, None)
        else:
            updated[key] = value
    return updated.urlencode()
