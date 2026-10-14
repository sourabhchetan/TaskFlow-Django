"""Business logic kept out of views.py: task statistics and recurring-task
generation. Isolating this here keeps views.py focused on request/response
handling and makes the logic independently unit-testable.
"""
import calendar as calendar_module
from datetime import date, timedelta

from django.utils import timezone

from .models import ActivityLog, Task

PRIORITY_RANK = {'high': 0, 'medium': 1, 'low': 2}


def get_task_stats(user):
    """Core counts reused by the dashboard and analytics views."""
    qs = Task.objects.filter(user=user)
    today = timezone.localdate()

    active_qs = qs.filter(completed=False)
    completed_qs = qs.filter(completed=True)

    active = active_qs.count()
    completed = completed_qs.count()
    total = active + completed
    overdue = sum(1 for t in active_qs if t.is_overdue)

    return {
        'total': total,
        'active': active,
        'completed': completed,
        'overdue': overdue,
        'today_due': active_qs.filter(due_date=today).count(),
        'completed_today': completed_qs.filter(completed_at__date=today).count(),
        'upcoming': active_qs.filter(due_date__gt=today).count(),
        'progress_pct': int((completed / total) * 100) if total else 0,
    }


def get_priority_summary(user):
    qs = Task.objects.filter(user=user, completed=False)
    return {
        'high': qs.filter(priority=Task.Priority.HIGH).count(),
        'medium': qs.filter(priority=Task.Priority.MEDIUM).count(),
        'low': qs.filter(priority=Task.Priority.LOW).count(),
    }


def get_category_breakdown(user):
    qs = Task.objects.filter(user=user).select_related('category')
    counts = {}
    for task in qs:
        label = task.category_label
        counts[label] = counts.get(label, 0) + 1
    return sorted(counts.items(), key=lambda pair: pair[1], reverse=True)


def get_weekly_productivity(user):
    """Number of tasks completed on each of the last 7 days (oldest first)."""
    today = timezone.localdate()
    days = [today - timedelta(days=offset) for offset in range(6, -1, -1)]
    qs = Task.objects.filter(user=user, completed=True, completed_at__date__in=days)
    counts = {d: 0 for d in days}
    for task in qs:
        d = timezone.localtime(task.completed_at).date()
        if d in counts:
            counts[d] += 1
    return [{'date': d, 'label': d.strftime('%a'), 'count': counts[d]} for d in days]


def get_analytics(user):
    stats = get_task_stats(user)
    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    completed_qs = Task.objects.filter(user=user, completed=True)

    priority_summary = get_priority_summary(user)
    active_total = stats['active'] or 1
    priority_bars = [
        {'label': 'High', 'count': priority_summary['high'], 'pct': int(priority_summary['high'] / active_total * 100)},
        {'label': 'Medium', 'count': priority_summary['medium'], 'pct': int(priority_summary['medium'] / active_total * 100)},
        {'label': 'Low', 'count': priority_summary['low'], 'pct': int(priority_summary['low'] / active_total * 100)},
    ]

    category_breakdown = get_category_breakdown(user)
    max_category_count = max([c for _, c in category_breakdown], default=1) or 1
    category_bars = [
        {'label': name, 'count': count, 'pct': int(count / max_category_count * 100)}
        for name, count in category_breakdown
    ]

    weekly = get_weekly_productivity(user)
    max_weekly_count = max([d['count'] for d in weekly], default=1) or 1
    weekly_bars = [
        {**d, 'pct': max(int(d['count'] / max_weekly_count * 100), 4 if d['count'] else 2)}
        for d in weekly
    ]

    return {
        'stats': stats,
        'completion_rate': stats['progress_pct'],
        'completed_this_week': completed_qs.filter(completed_at__date__gte=week_start).count(),
        'completed_this_month': completed_qs.filter(completed_at__date__gte=month_start).count(),
        'priority_bars': priority_bars,
        'category_bars': category_bars,
        'weekly_bars': weekly_bars,
    }


def build_month_grid(user, year, month):
    """Return a list of weeks (each a list of day dicts) for a calendar
    month view, annotated with how many of the user's tasks fall on each
    date."""
    cal = calendar_module.Calendar(firstweekday=6)  # weeks start on Sunday
    today = timezone.localdate()

    task_counts = {}
    qs = Task.objects.filter(user=user, due_date__year=year, due_date__month=month)
    for task in qs:
        task_counts[task.due_date] = task_counts.get(task.due_date, 0) + 1

    weeks = []
    for week in cal.monthdatescalendar(year, month):
        week_days = []
        for day in week:
            week_days.append({
                'date': day,
                'in_month': day.month == month,
                'is_today': day == today,
                'task_count': task_counts.get(day, 0),
            })
        weeks.append(week_days)
    return weeks


def add_recurrence(base_date, recurrence_type, interval=1):
    """Compute the next due_date for a recurring task. Month arithmetic is
    done manually (no third-party date library needed) and clamps to the
    last valid day of the target month (e.g. Jan 31 -> Feb 28)."""
    if recurrence_type == Task.Recurrence.DAILY:
        return base_date + timedelta(days=1)
    if recurrence_type == Task.Recurrence.WEEKLY:
        return base_date + timedelta(weeks=1)
    if recurrence_type == Task.Recurrence.CUSTOM:
        return base_date + timedelta(days=max(interval, 1))
    if recurrence_type == Task.Recurrence.MONTHLY:
        month = base_date.month + 1
        year = base_date.year + (month - 1) // 12
        month = ((month - 1) % 12) + 1
        last_day = calendar_module.monthrange(year, month)[1]
        return date(year, month, min(base_date.day, last_day))
    return None


def create_next_occurrence(task):
    """When a recurring task is completed, create the next occurrence.
    Returns the new Task, or None if the task isn't recurring, has no due
    date to base the recurrence on, or the recurrence has ended.

    Duplicate-safe: refuses to create an occurrence that already exists for
    the computed date under the same recurrence chain.
    """
    if not task.is_recurring or task.recurrence_type == Task.Recurrence.NONE:
        return None
    if not task.due_date:
        return None

    next_date = add_recurrence(task.due_date, task.recurrence_type, task.recurrence_interval)
    if not next_date:
        return None
    if task.recurrence_end_date and next_date > task.recurrence_end_date:
        return None

    root = task.root_task
    already_exists = Task.objects.filter(
        user=task.user, parent_task=root, due_date=next_date
    ).exists()
    if already_exists:
        return None

    return Task.objects.create(
        user=task.user,
        title=task.title,
        description=task.description,
        category=task.category,
        priority=task.priority,
        due_date=next_date,
        due_time=task.due_time,
        pinned=task.pinned,
        is_recurring=task.is_recurring,
        recurrence_type=task.recurrence_type,
        recurrence_interval=task.recurrence_interval,
        recurrence_end_date=task.recurrence_end_date,
        reminder_offset=task.reminder_offset,
        parent_task=root,
    )

# ---------------------------------------------------------------------------
# Activity history
# ---------------------------------------------------------------------------
def log_activity(user, task, action, description):
    """Record one activity entry. Callers are responsible for only calling
    this when something actually changed (see task_edit in views.py) so the
    log doesn't fill up with no-op entries."""
    return ActivityLog.objects.create(user=user, task=task, action=action, description=description)


# ---------------------------------------------------------------------------
# Productivity streaks
# ---------------------------------------------------------------------------
def get_productivity_streak(user):
    """Current and longest streak of consecutive days with at least one
    completed task, based on ``completed_at``. "Current" streak counts back
    from today (or yesterday, so completing nothing *yet* today doesn't
    reset a streak still in progress)."""
    completed_dates = sorted(set(
        timezone.localtime(dt).date()
        for dt in Task.objects.filter(user=user, completed=True, completed_at__isnull=False)
        .values_list('completed_at', flat=True)
    ))
    if not completed_dates:
        return {'current': 0, 'longest': 0}

    date_set = set(completed_dates)
    today = timezone.localdate()

    # Current streak: walk backwards from today (or yesterday) while dates exist.
    current = 0
    cursor = today
    if cursor not in date_set:
        cursor -= timedelta(days=1)
    while cursor in date_set:
        current += 1
        cursor -= timedelta(days=1)

    # Longest streak: scan the sorted unique dates for the longest run of
    # consecutive days.
    longest = 1
    run = 1
    for prev, curr in zip(completed_dates, completed_dates[1:]):
        if (curr - prev).days == 1:
            run += 1
            longest = max(longest, run)
        else:
            run = 1
    longest = max(longest, current)

    return {'current': current, 'longest': longest}


# ---------------------------------------------------------------------------
# Rule-based productivity insights (no external calls — plain data rules)
# ---------------------------------------------------------------------------
def get_daily_status_message(user):
    """A single always-present status line reflecting today's remaining
    task count specifically — distinct from the broader rule-based insights
    used on the analytics page (overdue backlog, streaks, etc.), and always
    returns exactly one of a few clear states rather than a conditional list."""
    today = timezone.localdate()
    today_qs = Task.objects.filter(user=user, due_date=today)
    total_today = today_qs.count()
    remaining_today = today_qs.filter(completed=False).count()

    if total_today == 0:
        return "Your schedule is clear today."
    if remaining_today == 0:
        return "Everything planned for today is complete."
    if remaining_today == 1:
        return "Great progress! Only 1 task left."
    return f"You have {remaining_today} tasks remaining today."


def get_insights(user):
    """A short list of human-readable insight strings generated from the
    user's real task data. Order is roughly most-to-least actionable."""
    stats = get_task_stats(user)
    priority_summary = get_priority_summary(user)
    streak = get_productivity_streak(user)
    insights = []

    if stats['overdue'] >= 3:
        insights.append(f"You have {stats['overdue']} overdue tasks. Consider completing or rescheduling them.")
    elif stats['overdue'] > 0:
        insights.append(f"You have {stats['overdue']} overdue task{'s' if stats['overdue'] != 1 else ''}. Consider tackling it soon.")

    if priority_summary['high'] >= 2:
        insights.append(f"You have {priority_summary['high']} high-priority tasks. Focus on the most urgent one first.")

    if stats['today_due'] == 0 and stats['overdue'] == 0:
        insights.append("Your schedule is clear today.")

    if stats['completed_today'] >= 3:
        insights.append(f"Great job! You completed {stats['completed_today']} tasks today.")

    if streak['current'] >= 2:
        insights.append(f"You're on a {streak['current']}-day productivity streak. Keep it going!")

    if not insights:
        insights.append("You're all caught up. Nice and steady.")

    return insights


def get_notifications(user):
    """Small, computed-on-the-fly notices for the topbar bell — never
    stored, so there's nothing to accidentally repeat or go stale. Capped
    at a handful of items so it stays a quick glance, not another inbox."""
    stats = get_task_stats(user)
    priority_summary = get_priority_summary(user)
    notifications = []

    if stats['overdue'] > 0:
        notifications.append({
            'type': 'overdue',
            'message': f"{stats['overdue']} task{'s' if stats['overdue'] != 1 else ''} overdue.",
        })
    if stats['today_due'] > 0:
        notifications.append({
            'type': 'today',
            'message': f"{stats['today_due']} task{'s' if stats['today_due'] != 1 else ''} due today.",
        })
    if priority_summary['high'] > 0:
        notifications.append({
            'type': 'priority',
            'message': f"{priority_summary['high']} high-priority task{'s' if priority_summary['high'] != 1 else ''} pending.",
        })

    return notifications[:5]


def group_activity_by_day(entries):
    """Group already-fetched ActivityLog entries (e.g. one page of results)
    into 'Today' / 'Yesterday' / 'Earlier' buckets for display, preserving
    each entry's existing order within its bucket. Takes a plain iterable
    (not a queryset) so it works cleanly on an already-paginated page."""
    today = timezone.localdate()
    yesterday = today - timedelta(days=1)
    buckets = [('Today', []), ('Yesterday', []), ('Earlier', [])]

    for entry in entries:
        entry_date = timezone.localtime(entry.created_at).date()
        if entry_date == today:
            buckets[0][1].append(entry)
        elif entry_date == yesterday:
            buckets[1][1].append(entry)
        else:
            buckets[2][1].append(entry)

    return [(label, items) for label, items in buckets if items]
