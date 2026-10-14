"""Views for the To-Do List app.

Every task/category lookup is scoped with ``user=request.user`` (via
``get_object_or_404``) so a user can never read, edit, complete, pin, or
delete a task/category belonging to someone else — including by editing the
``pk`` in the URL. The REST API applies the equivalent check in
``api.permissions.IsOwner``.

Several endpoints below (task_toggle, task_pin, task_delete, bulk_action)
support an optional AJAX mode: when the request carries the
``X-Requested-With: XMLHttpRequest`` header, they return JSON instead of
redirecting, so the dashboard can update in place without a full page
reload. Every one of these endpoints behaves *exactly* as it did before for
a plain (non-AJAX) form POST — the JSON branch is purely additive — so
JavaScript-disabled clients (and the existing test suite, which posts
without that header) get the original redirect-based behavior unchanged.
"""
import calendar as calendar_module
from datetime import date, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .context_processors import sidebar_counts
from .forms import CategoryForm, ProfileEmailForm, ProfileForm, RegisterForm, TaskForm
from .models import ActivityLog, Category, Task
from .services import (
    build_month_grid,
    create_next_occurrence,
    get_analytics,
    get_daily_status_message,
    get_insights,
    get_priority_summary,
    get_productivity_streak,
    get_task_stats,
    group_activity_by_day,
    log_activity,
)

SORT_OPTIONS = {
    'due_date': ('due_date', 'Due date'),
    'priority': ('priority_rank', 'Priority'),
    'created': ('-created_at', 'Recently created'),
    'updated': ('-updated_at', 'Recently updated'),
}

FILTER_LABELS = {
    'all': 'All tasks',
    'today': "Today's tasks",
    'upcoming': 'Upcoming tasks',
    'overdue': 'Overdue tasks',
    'high': 'High priority tasks',
    'completed': 'Completed tasks',
    'pinned': 'Pinned tasks',
}

PRIORITY_RANK = {'high': 0, 'medium': 1, 'low': 2}

BULK_ACTIONS = {'complete', 'reopen', 'delete', 'pin', 'unpin', 'priority'}

BULK_ACTION_LOG_TYPE = {
    'complete': ActivityLog.Action.COMPLETED,
    'reopen': ActivityLog.Action.REOPENED,
    'pin': ActivityLog.Action.PINNED,
    'unpin': ActivityLog.Action.UNPINNED,
    'priority': ActivityLog.Action.PRIORITY_CHANGED,
    'delete': ActivityLog.Action.DELETED,
}


def _is_ajax(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


def _dashboard_counters(request):
    """The small set of numbers an AJAX response needs to refresh the
    dashboard in place, without re-rendering the page: headline stats, the
    progress bar percentage, and the sidebar nav badges."""
    stats = get_task_stats(request.user)
    return {
        'stats': stats,
        'progress_pct': stats['progress_pct'],
        'sidebar_counts': sidebar_counts(request).get('sidebar_counts', {}),
    }


def _greeting():
    hour = timezone.localtime().hour
    if hour < 12:
        return 'Good morning'
    if hour < 18:
        return 'Good afternoon'
    return 'Good evening'


@login_required
def dashboard(request):
    base_qs = Task.objects.filter(user=request.user).select_related('category')
    # date.today() (not timezone.localdate()) deliberately: TIME_ZONE defaults
    # to UTC (see config/settings.py) unless DJANGO_TIME_ZONE is set, so
    # timezone.localdate() can be a day behind the server's actual wall-clock
    # date for any user east of UTC during their evening/night hours — e.g.
    # a task due_date=date.today() would silently fail every due=today /
    # ?filter=today / ?filter=upcoming comparison below during that window.
    today = date.today()

    stats = get_task_stats(request.user)
    priority_summary = get_priority_summary(request.user)
    active_total = stats['active'] or 1
    priority_pct = {k: int((v / active_total) * 100) for k, v in priority_summary.items()}

    default_filter = getattr(getattr(request.user, 'profile', None), 'default_view', 'all')
    active_filter = request.GET.get('filter', default_filter)
    sort_key = request.GET.get('sort', 'due_date')
    query = request.GET.get('q', '').strip()

    # Read this before the quick-filter pills below so the 'all' pill (the
    # only one that doesn't already imply a completion state) can defer to
    # it instead of always forcing completed=False — otherwise ?filter=all
    # combined with ?status=completed would silently return nothing.
    filter_status = request.GET.get('status', '')

    tasks = base_qs
    if active_filter == 'today':
        tasks = tasks.filter(completed=False, due_date=today)
    elif active_filter == 'upcoming':
        tasks = tasks.filter(completed=False, due_date__gt=today)
    elif active_filter == 'overdue':
        overdue_ids = [t.id for t in tasks.filter(completed=False) if t.is_overdue]
        tasks = tasks.filter(id__in=overdue_ids)
    elif active_filter == 'high':
        tasks = tasks.filter(completed=False, priority=Task.Priority.HIGH)
    elif active_filter == 'completed':
        tasks = tasks.filter(completed=True)
    elif active_filter == 'pinned':
        tasks = tasks.filter(completed=False, pinned=True)
    else:
        active_filter = 'all'
        if not filter_status:
            tasks = tasks.filter(completed=False)

    # --- Advanced, combinable filters -----------------------------------
    # These layer *on top of* the quick-filter pill above (which most people
    # use most of the time) rather than replacing it, so every existing
    # ?filter=... URL and test keeps behaving exactly as before. A person
    # can combine any of these — e.g. ?filter=all&priority=high&due=today.
    if filter_status == 'active':
        tasks = tasks.filter(completed=False)
    elif filter_status == 'completed':
        tasks = tasks.filter(completed=True)

    filter_priority = request.GET.get('priority', '')
    if filter_priority in dict(Task.Priority.choices):
        tasks = tasks.filter(priority=filter_priority)

    filter_category = request.GET.get('category', '')
    if filter_category.isdigit():
        tasks = tasks.filter(category_id=int(filter_category))

    filter_due = request.GET.get('due', '')
    if filter_due == 'today':
        tasks = tasks.filter(due_date=today)
    elif filter_due == 'tomorrow':
        tasks = tasks.filter(due_date=today + timedelta(days=1))
    elif filter_due == 'week':
        tasks = tasks.filter(due_date__gte=today, due_date__lte=today + timedelta(days=7))
    elif filter_due == 'overdue':
        due_overdue_ids = [t.id for t in tasks if t.is_overdue]
        tasks = tasks.filter(id__in=due_overdue_ids)
    elif filter_due == 'none':
        tasks = tasks.filter(due_date__isnull=True)

    filter_pinned = request.GET.get('pinned', '')
    if filter_pinned == '1':
        tasks = tasks.filter(pinned=True)

    advanced_filters_active = any([filter_status, filter_priority, filter_category, filter_due, filter_pinned])
    active_filter_count = sum(1 for v in [filter_status, filter_priority, filter_category, filter_due, filter_pinned] if v)

    if query:
        search_conditions = (
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(category__name__icontains=query)
        )
        # A query that matches a priority name (e.g. "high") also pulls in
        # tasks of that priority, in addition to the usual text match.
        priority_match = query.lower()
        if priority_match in dict(Task.Priority.choices):
            search_conditions |= Q(priority=priority_match)
        tasks = tasks.filter(search_conditions)

    tasks = list(tasks)
    if sort_key == 'priority':
        tasks.sort(key=lambda t: PRIORITY_RANK.get(t.priority, 3))
    elif sort_key == 'created':
        tasks.sort(key=lambda t: t.created_at, reverse=True)
    elif sort_key == 'updated':
        tasks.sort(key=lambda t: t.updated_at, reverse=True)
    else:
        sort_key = 'due_date'
        tasks.sort(key=lambda t: (t.due_date is None, t.due_date, t.due_time or timezone.datetime.min.time()))
    # Pinned tasks always float to the top of the active view.
    tasks.sort(key=lambda t: not t.pinned)

    paginator = Paginator(tasks, getattr(settings, 'TASKS_PER_PAGE', 9))
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'greeting': _greeting(),
        'today': today,
        'stats': stats,
        'priority_summary': priority_summary,
        'priority_pct': priority_pct,
        'progress_pct': stats['progress_pct'],
        'page_obj': page_obj,
        'tasks': page_obj.object_list,
        'active_filter': active_filter,
        'filter_label': FILTER_LABELS.get(active_filter, 'All tasks'),
        'sort_key': sort_key,
        'sort_options': SORT_OPTIONS,
        'query': query,
        'filter_status': filter_status,
        'filter_priority': filter_priority,
        'filter_category': filter_category,
        'filter_due': filter_due,
        'filter_pinned': filter_pinned,
        'advanced_filters_active': advanced_filters_active,
        'active_filter_count': active_filter_count,
        'categories': Category.objects.filter(user=request.user),
        'daily_status': get_daily_status_message(request.user),
    }
    return render(request, 'tasks/dashboard.html', context)


@login_required
def task_create(request):
    if request.method == 'POST':
        form = TaskForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            task = form.save(commit=False)
            task.user = request.user
            task.save()
            log_activity(request.user, task, ActivityLog.Action.CREATED, f'Created "{task.title}"')
            messages.success(request, 'Task created successfully.')
            return redirect('dashboard')
        messages.error(request, 'Please fix the errors below.')
    else:
        initial = {'priority': getattr(getattr(request.user, 'profile', None), 'default_priority', 'medium')}
        # Optional quick-start pre-fill (e.g. from an empty-state shortcut
        # like "Study" / "Work" / "Personal") — matches by category name
        # among the user's own categories only, and is silently ignored if
        # it doesn't match anything.
        category_hint = request.GET.get('category', '').strip()
        if category_hint:
            matched = Category.objects.filter(user=request.user, name__iexact=category_hint).first()
            if matched:
                initial['category'] = matched.pk
        form = TaskForm(user=request.user, initial=initial)
    return render(request, 'tasks/task_form.html', {'form': form, 'is_edit': False})


@login_required
def task_edit(request, pk):
    task = get_object_or_404(Task, pk=pk, user=request.user)
    if request.method == 'POST':
        previous_priority = task.priority
        previous_due_date = task.due_date
        form = TaskForm(request.POST, request.FILES, instance=task, user=request.user)
        if form.is_valid():
            updated = form.save()
            if updated.priority != previous_priority:
                log_activity(
                    request.user, updated, ActivityLog.Action.PRIORITY_CHANGED,
                    f'Changed priority of "{updated.title}" from '
                    f'{dict(Task.Priority.choices).get(previous_priority, previous_priority)} to '
                    f'{updated.priority_label}',
                )
            if updated.due_date != previous_due_date:
                log_activity(
                    request.user, updated, ActivityLog.Action.DUE_DATE_CHANGED,
                    f'Changed due date of "{updated.title}" to '
                    f'{updated.due_date.strftime("%b %d, %Y") if updated.due_date else "no due date"}',
                )
            messages.success(request, 'Task updated.')
            return redirect('dashboard')
        messages.error(request, 'Please fix the errors below.')
    else:
        form = TaskForm(instance=task, user=request.user)
    return render(request, 'tasks/task_form.html', {'form': form, 'is_edit': True, 'task': task})


@login_required
@require_POST
def task_toggle(request, pk):
    task = get_object_or_404(Task, pk=pk, user=request.user)
    task.completed = not task.completed
    task.completed_at = timezone.now() if task.completed else None
    task.save(update_fields=['completed', 'completed_at', 'updated_at'])

    new_task = None
    if task.completed:
        log_activity(request.user, task, ActivityLog.Action.COMPLETED, f'Completed "{task.title}"')
        new_task = create_next_occurrence(task)
        if new_task:
            success_message = f'Task completed. Next occurrence scheduled for {new_task.due_date}.'
        else:
            success_message = 'Task completed.'
    else:
        log_activity(request.user, task, ActivityLog.Action.REOPENED, f'Reopened "{task.title}"')
        success_message = 'Task marked active again.'

    if _is_ajax(request):
        return JsonResponse({
            'ok': True,
            'task_id': task.id,
            'completed': task.completed,
            'countdown_text': task.countdown_text,
            'is_overdue': task.is_overdue,
            'message': success_message,
            'next_occurrence_due_date': str(new_task.due_date) if new_task else None,
            **_dashboard_counters(request),
        })

    messages.success(request, success_message)
    return redirect(request.POST.get('next') or 'dashboard')


@login_required
@require_POST
def task_pin(request, pk):
    task = get_object_or_404(Task, pk=pk, user=request.user)
    task.pinned = not task.pinned
    task.save(update_fields=['pinned', 'updated_at'])
    action = ActivityLog.Action.PINNED if task.pinned else ActivityLog.Action.UNPINNED
    log_activity(request.user, task, action, f'{"Pinned" if task.pinned else "Unpinned"} "{task.title}"')

    if _is_ajax(request):
        return JsonResponse({
            'ok': True,
            'task_id': task.id,
            'pinned': task.pinned,
            'message': 'Task pinned.' if task.pinned else 'Task unpinned.',
            **_dashboard_counters(request),
        })

    return redirect(request.POST.get('next') or 'dashboard')


@login_required
@require_POST
def task_delete(request, pk):
    task = get_object_or_404(Task, pk=pk, user=request.user)
    title = task.title
    task_id = task.id
    # Logged before deletion (with the title captured above) since the
    # ActivityLog row's task FK will be nulled out by on_delete=SET_NULL —
    # the description text is what keeps the record meaningful afterwards.
    log_activity(request.user, task, ActivityLog.Action.DELETED, f'Deleted "{title}"')
    task.delete()

    if _is_ajax(request):
        return JsonResponse({
            'ok': True,
            'task_id': task_id,
            'message': 'Task deleted.',
            **_dashboard_counters(request),
        })

    messages.success(request, 'Task deleted.')
    return redirect(request.POST.get('next') or 'dashboard')


@login_required
@require_POST
def bulk_action(request):
    """Apply one action to a batch of the user's own tasks in a single
    query. ``task_ids`` are always intersected with the requesting user's
    own tasks (Task.objects.filter(user=request.user, pk__in=...)) so a
    crafted request can never touch another user's tasks, no matter what
    ids are submitted.
    """
    action = request.POST.get('action', '')
    task_ids = request.POST.getlist('task_ids')
    next_url = request.POST.get('next') or 'dashboard'

    if action not in BULK_ACTIONS or not task_ids:
        if _is_ajax(request):
            return JsonResponse({'ok': False, 'message': 'No tasks selected.'}, status=400)
        messages.error(request, 'No tasks selected.')
        return redirect(next_url)

    queryset = Task.objects.filter(user=request.user, pk__in=task_ids)
    affected_ids = list(queryset.values_list('id', flat=True))
    count = len(affected_ids)

    if count == 0:
        if _is_ajax(request):
            return JsonResponse({'ok': False, 'message': 'No matching tasks found.'}, status=404)
        messages.error(request, 'No matching tasks found.')
        return redirect(next_url)

    if action == 'complete':
        queryset.update(completed=True, completed_at=timezone.now())
        message = f'Completed {count} task{"s" if count != 1 else ""}.'
    elif action == 'reopen':
        queryset.update(completed=False, completed_at=None)
        message = f'Reopened {count} task{"s" if count != 1 else ""}.'
    elif action == 'pin':
        queryset.update(pinned=True)
        message = f'Pinned {count} task{"s" if count != 1 else ""}.'
    elif action == 'unpin':
        queryset.update(pinned=False)
        message = f'Unpinned {count} task{"s" if count != 1 else ""}.'
    elif action == 'priority':
        new_priority = request.POST.get('priority', '')
        if new_priority not in dict(Task.Priority.choices):
            if _is_ajax(request):
                return JsonResponse({'ok': False, 'message': 'Invalid priority.'}, status=400)
            messages.error(request, 'Invalid priority.')
            return redirect(next_url)
        queryset.update(priority=new_priority)
        message = f'Updated priority for {count} task{"s" if count != 1 else ""}.'
    elif action == 'delete':
        queryset.delete()
        message = f'Deleted {count} task{"s" if count != 1 else ""}.'
    else:
        message = ''  # unreachable — action is already validated against BULK_ACTIONS above

    log_activity(request.user, None, BULK_ACTION_LOG_TYPE[action], message)

    if _is_ajax(request):
        return JsonResponse({
            'ok': True,
            'action': action,
            'task_ids': affected_ids,
            'message': message,
            **_dashboard_counters(request),
        })

    messages.success(request, message)
    return redirect(next_url)


@login_required
def calendar_view(request):
    today = timezone.localdate()
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
        date(year, month, 1)
    except (ValueError, TypeError):
        year, month = today.year, today.month

    prev_month = month - 1 or 12
    prev_year = year - 1 if month == 1 else year
    next_month = month % 12 + 1
    next_year = year + 1 if month == 12 else year

    selected_str = request.GET.get('date')
    try:
        selected_date = date.fromisoformat(selected_str) if selected_str else today
    except ValueError:
        selected_date = today

    agenda = list(
        Task.objects.filter(user=request.user, due_date=selected_date)
        .select_related('category')
        .order_by('due_time')
    )

    context = {
        'weeks': build_month_grid(request.user, year, month),
        'year': year,
        'month': month,
        'month_name': calendar_module.month_name[month],
        'prev_year': prev_year,
        'prev_month': prev_month,
        'next_year': next_year,
        'next_month': next_month,
        'today': today,
        'selected_date': selected_date,
        'agenda': agenda,
        'weekday_labels': ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'],
    }
    return render(request, 'tasks/calendar.html', context)


@login_required
def analytics_view(request):
    context = get_analytics(request.user)
    context['streak'] = get_productivity_streak(request.user)
    context['insights'] = get_insights(request.user)
    return render(request, 'tasks/analytics.html', context)


@login_required
def activity_view(request):
    entries = ActivityLog.objects.filter(user=request.user).select_related('task')
    paginator = Paginator(entries, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    grouped = group_activity_by_day(page_obj.object_list)
    return render(request, 'tasks/activity.html', {
        'page_obj': page_obj, 'entries': page_obj.object_list, 'grouped_entries': grouped,
    })


@login_required
def category_list(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST, user=request.user)
        if form.is_valid():
            category = form.save(commit=False)
            category.user = request.user
            category.save()
            messages.success(request, f'Category "{category.name}" created.')
            return redirect('categories')
        messages.error(request, 'Please fix the errors below.')
    else:
        form = CategoryForm(user=request.user)

    categories = Category.objects.filter(user=request.user).annotate(task_count=Count('tasks'))
    return render(request, 'tasks/categories.html', {
        'form': form,
        'categories': [{'obj': c, 'task_count': c.task_count} for c in categories],
    })


@login_required
def category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk, user=request.user)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category updated.')
            return redirect('categories')
        messages.error(request, 'Please fix the errors below.')
    else:
        form = CategoryForm(instance=category, user=request.user)
    return render(request, 'tasks/category_form.html', {'form': form, 'category': category})


@login_required
@require_POST
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk, user=request.user)
    category.delete()
    messages.success(request, 'Category deleted. Tasks in it are now uncategorized.')
    return redirect('categories')


@login_required
def profile(request):
    qs = Task.objects.filter(user=request.user)
    total = qs.count()
    completed = qs.filter(completed=True).count()

    if request.method == 'POST':
        email_form = ProfileEmailForm(request.POST, instance=request.user)
        if email_form.is_valid():
            email_form.save()
            messages.success(request, 'Profile updated.')
            return redirect('profile')
        messages.error(request, 'Please fix the errors below.')
    else:
        email_form = ProfileEmailForm(instance=request.user)

    context = {
        'total_tasks': total,
        'completed_tasks': completed,
        'active_tasks': total - completed,
        'completion_rate': int((completed / total) * 100) if total else 0,
        'email_form': email_form,
    }
    return render(request, 'tasks/profile.html', context)


@login_required
def settings_view(request):
    profile_obj = request.user.profile
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=profile_obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'Settings saved.')
            return redirect('settings')
        messages.error(request, 'Please fix the errors below.')
    else:
        form = ProfileForm(instance=profile_obj)
    return render(request, 'tasks/settings.html', {'form': form})


def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Welcome, {user.username}! Your account has been created.')
            return redirect('dashboard')
        messages.error(request, 'Please fix the errors below.')
    else:
        form = RegisterForm()
    return render(request, 'registration/register.html', {'form': form})


# ---------------------------------------------------------------------------
# Custom error views (rendered automatically by Django when DEBUG=False, as
# long as these templates exist).
# ---------------------------------------------------------------------------
def error_404(request, exception=None):
    return render(request, '404.html', status=404)


def error_403(request, exception=None):
    return render(request, '403.html', status=403)


def error_500(request):
    return render(request, '500.html', status=500)
