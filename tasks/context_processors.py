"""Template context processors for the tasks app."""
from django.utils import timezone

from .models import Task
from .services import get_notifications


def sidebar_counts(request):
    """Expose per-filter task counts to every template (used by the sidebar
    nav badges) without every view having to compute them manually."""
    if not request.user.is_authenticated:
        return {}

    qs = Task.objects.filter(user=request.user)
    today = timezone.localdate()

    active = qs.filter(completed=False)
    overdue_count = sum(1 for t in active if t.is_overdue)

    return {
        'sidebar_counts': {
            'all': qs.count(),
            'today': active.filter(due_date=today).count(),
            'upcoming': active.filter(due_date__gt=today).count(),
            'overdue': overdue_count,
            'high': active.filter(priority=Task.Priority.HIGH).count(),
            'pinned': active.filter(pinned=True).count(),
            'completed': qs.filter(completed=True).count(),
        }
    }


def notification_bell(request):
    """Computed-on-the-fly notices for the topbar bell (see
    tasks.services.get_notifications) — nothing is stored, so there's
    nothing to mark as read or accidentally repeat."""
    if not request.user.is_authenticated:
        return {}
    return {'topbar_notifications': get_notifications(request.user)}
