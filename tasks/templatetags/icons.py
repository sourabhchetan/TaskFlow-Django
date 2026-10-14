"""A tiny, dependency-free icon system: a handful of hand-drawn, generic
outline icons (not sourced from any third-party icon library) exposed as a
single template tag so templates never embed raw emoji or duplicate SVG
markup. Usage: {% icon "check" %} or {% icon "trash" class="small" %}
"""
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

_STROKE = 'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" fill="none"'

ICONS = {
    'menu': f'<line x1="3" y1="6" x2="21" y2="6" {_STROKE}/><line x1="3" y1="12" x2="21" y2="12" {_STROKE}/><line x1="3" y1="18" x2="21" y2="18" {_STROKE}/>',
    'sun': f'<circle cx="12" cy="12" r="4" {_STROKE}/><line x1="12" y1="1.5" x2="12" y2="4" {_STROKE}/><line x1="12" y1="20" x2="12" y2="22.5" {_STROKE}/><line x1="4.2" y1="4.2" x2="6" y2="6" {_STROKE}/><line x1="18" y1="18" x2="19.8" y2="19.8" {_STROKE}/><line x1="1.5" y1="12" x2="4" y2="12" {_STROKE}/><line x1="20" y1="12" x2="22.5" y2="12" {_STROKE}/><line x1="4.2" y1="19.8" x2="6" y2="18" {_STROKE}/><line x1="18" y1="6" x2="19.8" y2="4.2" {_STROKE}/>',
    'moon': f'<path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a6.8 6.8 0 0 0 10.5 10.5Z" {_STROKE}/>',
    'plus': f'<line x1="12" y1="5" x2="12" y2="19" {_STROKE}/><line x1="5" y1="12" x2="19" y2="12" {_STROKE}/>',
    'search': f'<circle cx="10.5" cy="10.5" r="6.5" {_STROKE}/><line x1="15.5" y1="15.5" x2="21" y2="21" {_STROKE}/>',
    'star': f'<path d="M12 3.5l2.5 5.4 5.8.6-4.4 4 1.3 5.8L12 16.6 6.8 19.3l1.3-5.8-4.4-4 5.8-.6z" {_STROKE}/>',
    'edit': f'<path d="M4 20h4L19.5 8.5a2.1 2.1 0 0 0-3-3L4.5 17z" {_STROKE}/><line x1="14.5" y1="6" x2="18" y2="9.5" {_STROKE}/>',
    'trash': f'<line x1="4" y1="7" x2="20" y2="7" {_STROKE}/><path d="M6 7l1 13h10l1-13" {_STROKE}/><line x1="9" y1="11" x2="9" y2="17" {_STROKE}/><line x1="15" y1="11" x2="15" y2="17" {_STROKE}/><path d="M9 7V4h6v3" {_STROKE}/>',
    'check': f'<polyline points="4,13 9,18 20,6" {_STROKE}/>',
    'calendar': f'<rect x="3.5" y="5" width="17" height="16" rx="2" {_STROKE}/><line x1="3.5" y1="10" x2="20.5" y2="10" {_STROKE}/><line x1="8" y1="3" x2="8" y2="7" {_STROKE}/><line x1="16" y1="3" x2="16" y2="7" {_STROKE}/>',
    'chart': f'<line x1="4" y1="21" x2="20" y2="21" {_STROKE}/><rect x="6" y="12" width="3" height="9" {_STROKE}/><rect x="11" y="7" width="3" height="14" {_STROKE}/><rect x="16" y="15" width="3" height="6" {_STROKE}/>',
    'home': f'<path d="M4 11.5 12 4l8 7.5" {_STROKE}/><path d="M6 10v10h12V10" {_STROKE}/>',
    'clock': f'<circle cx="12" cy="12" r="8.5" {_STROKE}/><polyline points="12,7 12,12 16,14.5" {_STROKE}/>',
    'warning': f'<path d="M12 4 21 20H3z" {_STROKE}/><line x1="12" y1="10" x2="12" y2="14.5" {_STROKE}/><circle cx="12" cy="17.3" r="0.15" {_STROKE}/>',
    'logout': f'<path d="M9 4H5a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h4" {_STROKE}/><line x1="21" y1="12" x2="10" y2="12" {_STROKE}/><polyline points="16,7 21,12 16,17" {_STROKE}/>',
    'user': f'<circle cx="12" cy="8" r="3.6" {_STROKE}/><path d="M4.5 20c1.4-3.6 4.4-5.5 7.5-5.5s6.1 1.9 7.5 5.5" {_STROKE}/>',
    'settings': f'<circle cx="12" cy="12" r="3" {_STROKE}/><path d="M19.4 13.5a7.6 7.6 0 0 0 0-3l2-1.4-2-3.4-2.3.8a7.6 7.6 0 0 0-2.6-1.5L14 2.5h-4l-.5 2.5a7.6 7.6 0 0 0-2.6 1.5l-2.3-.8-2 3.4 2 1.4a7.6 7.6 0 0 0 0 3l-2 1.4 2 3.4 2.3-.8a7.6 7.6 0 0 0 2.6 1.5l.5 2.5h4l.5-2.5a7.6 7.6 0 0 0 2.6-1.5l2.3.8 2-3.4z" {_STROKE}/>',
    'chevron-left': f'<polyline points="15,5 8,12 15,19" {_STROKE}/>',
    'chevron-right': f'<polyline points="9,5 16,12 9,19" {_STROKE}/>',
    'chevrons-left': f'<polyline points="12,5 6,12 12,19" {_STROKE}/><polyline points="18,5 12,12 18,19" {_STROKE}/>',
    'pin': f'<path d="M12 2v6.5L17 12l-5 1v8.5l-1-1V13L6 12l5-3.5Z" {_STROKE}/>',
    'flag-high': f'<line x1="6" y1="3" x2="6" y2="21" {_STROKE}/><path d="M6 4h12l-3 4 3 4H6" {_STROKE}/>',
    'list': f'<line x1="9" y1="6" x2="21" y2="6" {_STROKE}/><line x1="9" y1="12" x2="21" y2="12" {_STROKE}/><line x1="9" y1="18" x2="21" y2="18" {_STROKE}/><circle cx="4.5" cy="6" r="1" {_STROKE}/><circle cx="4.5" cy="12" r="1" {_STROKE}/><circle cx="4.5" cy="18" r="1" {_STROKE}/>',
    'tag': f'<path d="M11 3H4v7l10 10 7-7z" {_STROKE}/><circle cx="7.5" cy="7.5" r="1.2" {_STROKE}/>',
    'filter': f'<path d="M3 4h18l-7 8v6l-4 2v-8Z" {_STROKE}/>',
    'chevron-down': f'<polyline points="6,9 12,15 18,9" {_STROKE}/>',
    'bell': f'<path d="M18 16V11a6 6 0 1 0-12 0v5l-1.5 2.5h15L18 16Z" {_STROKE}/><path d="M10 20.5a2.2 2.2 0 0 0 4 0" {_STROKE}/>',
    'paperclip': f'<path d="M8 12.5 15 5.6a3 3 0 0 1 4.2 4.2L11 18a5 5 0 0 1-7-7L11.5 3.5" {_STROKE}/>',
    'repeat': f'<polyline points="17,2 21,6 17,10" {_STROKE}/><path d="M3 12V9a3 3 0 0 1 3-3h15" {_STROKE}/><polyline points="7,22 3,18 7,14" {_STROKE}/><path d="M21 12v3a3 3 0 0 1-3 3H3" {_STROKE}/>',
    'close': f'<line x1="5" y1="5" x2="19" y2="19" {_STROKE}/><line x1="19" y1="5" x2="5" y2="19" {_STROKE}/>',
    'eye': f'<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" {_STROKE}/><circle cx="12" cy="12" r="3" {_STROKE}/>',
    'eye-off': f'<path d="M3 3l18 18" {_STROKE}/><path d="M10.6 5.2A10.4 10.4 0 0 1 12 5c6.5 0 10 7 10 7a17.5 17.5 0 0 1-3.5 4.5M6.3 6.3C3.5 8.2 2 12 2 12s3.5 7 10 7a10 10 0 0 0 4.2-.9" {_STROKE}/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" {_STROKE}/>',
    'rocket': f'<path d="M12 2.5c3 1 5 4.3 5 8 0 2.7-1 5-2 6.5l-1.5 1.5-1.5-1.5-1.5 1.5-1.5-1.5c-1-1.5-2-3.8-2-6.5 0-3.7 2-7 5-8Z" {_STROKE}/><circle cx="12" cy="9.5" r="1.6" {_STROKE}/><path d="M9 15.5 6.5 18m8.5-2.5 2.5 2.5" {_STROKE}/>',
}


@register.simple_tag(name='icon')
def render_icon(name, css_class=''):
    path = ICONS.get(name, '')
    classes = f'icon icon-{name} {css_class}'.strip()
    return mark_safe(f'<svg class="{classes}" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">{path}</svg>')
