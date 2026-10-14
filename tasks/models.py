"""Models for the To-Do List task management app.

Domain model:

    User
     |-- Profile        (1:1)   per-user preferences (theme, defaults, reminders)
     |-- Category        (1:N)  user-owned task categories
     `-- Task            (1:N)
           |-- Category   (N:1, nullable)
           `-- Task        (self FK) -- parent_task links recurring occurrences
"""
from datetime import datetime, time as time_cls

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

ALLOWED_ATTACHMENT_EXTENSIONS = ['pdf', 'png', 'jpg', 'jpeg', 'docx', 'txt', 'csv', 'xlsx']
MAX_ATTACHMENT_SIZE_MB = 5


def validate_attachment_size(f):
    from django.core.exceptions import ValidationError
    if f.size > MAX_ATTACHMENT_SIZE_MB * 1024 * 1024:
        raise ValidationError(f'File must be smaller than {MAX_ATTACHMENT_SIZE_MB}MB.')


def attachment_upload_path(instance, filename):
    return f'attachments/{instance.user_id}/{filename}'


class Profile(models.Model):
    """Per-user preferences. Created automatically for every user (see
    tasks.signals) so views can always assume ``user.profile`` exists."""

    class Theme(models.TextChoices):
        LIGHT = 'light', 'Light'
        DARK = 'dark', 'Dark'
        SYSTEM = 'system', 'System'

    class DefaultView(models.TextChoices):
        ALL = 'all', 'All tasks'
        TODAY = 'today', 'Today'
        UPCOMING = 'upcoming', 'Upcoming'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile'
    )
    theme_preference = models.CharField(max_length=10, choices=Theme.choices, default=Theme.SYSTEM)
    default_priority = models.CharField(max_length=10, default='medium')
    default_view = models.CharField(max_length=10, choices=DefaultView.choices, default=DefaultView.ALL)
    default_sort = models.CharField(max_length=10, default='due_date')
    reminders_enabled = models.BooleanField(default=True)

    def __str__(self):
        return f'Profile<{self.user.username}>'


class Category(models.Model):
    """A user-owned task category. Each user manages their own set — one
    user can never see or edit another user's categories."""

    DEFAULT_NAMES_AND_COLORS = [
        ('Personal', '#6366f1'),
        ('Work', '#0ea5e9'),
        ('Study', '#a855f7'),
        ('Project', '#f59e0b'),
        ('Shopping', '#10b981'),
        ('Other', '#64748b'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=50)
    color = models.CharField(max_length=7, default='#6366f1', help_text='Hex color, e.g. #6366f1')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['user', 'name'], name='unique_category_name_per_user'),
        ]

    def __str__(self):
        return self.name


class Task(models.Model):
    """A single task belonging to exactly one user.

    Ownership is enforced everywhere tasks are read or written (see
    tasks.views) so that one user can never view, edit, or delete another
    user's task — including by guessing/editing the ``pk`` in a URL, or via
    the REST API (see api.permissions.IsOwner).
    """

    class Priority(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'

    class Recurrence(models.TextChoices):
        NONE = 'none', 'Never'
        DAILY = 'daily', 'Daily'
        WEEKLY = 'weekly', 'Weekly'
        MONTHLY = 'monthly', 'Monthly'
        CUSTOM = 'custom', 'Custom'

    class Reminder(models.TextChoices):
        NONE = 'none', 'No reminder'
        MIN_10 = '10min', '10 minutes before'
        MIN_30 = '30min', '30 minutes before'
        HOUR_1 = '1hour', '1 hour before'
        DAY_1 = '1day', '1 day before'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tasks',
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks'
    )
    priority = models.CharField(
        max_length=10, choices=Priority.choices, default=Priority.MEDIUM
    )
    due_date = models.DateField(null=True, blank=True)
    due_time = models.TimeField(null=True, blank=True)
    completed = models.BooleanField(default=False)
    pinned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # -- Recurrence ------------------------------------------------------
    is_recurring = models.BooleanField(default=False)
    recurrence_type = models.CharField(max_length=10, choices=Recurrence.choices, default=Recurrence.NONE)
    recurrence_interval = models.PositiveSmallIntegerField(
        default=1, help_text='Used with "Custom": repeat every N days.'
    )
    recurrence_end_date = models.DateField(null=True, blank=True)
    parent_task = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='occurrences'
    )

    # -- Reminders & attachments ------------------------------------------
    reminder_offset = models.CharField(max_length=10, choices=Reminder.choices, default=Reminder.NONE)
    attachment = models.FileField(
        upload_to=attachment_upload_path,
        null=True,
        blank=True,
        validators=[
            FileExtensionValidator(ALLOWED_ATTACHMENT_EXTENSIONS),
            validate_attachment_size,
        ],
    )

    class Meta:
        ordering = ['-pinned', 'completed', 'due_date', 'due_time', '-created_at']
        indexes = [
            models.Index(fields=['user', 'completed']),
            models.Index(fields=['user', 'due_date']),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('task_edit', kwargs={'pk': self.pk})

    # -- Derived / display helpers -------------------------------------
    @property
    def due_datetime(self):
        """Combine due_date and due_time into a single aware datetime, or
        None if no due date is set. Missing time defaults to end-of-day so a
        date-only task isn't treated as overdue at 00:00 on its due date."""
        if not self.due_date:
            return None
        t = self.due_time or time_cls(23, 59, 59)
        naive = datetime.combine(self.due_date, t)
        if settings.USE_TZ and timezone.is_naive(naive):
            return timezone.make_aware(naive)
        return naive

    @property
    def is_overdue(self):
        dd = self.due_datetime
        if not dd or self.completed:
            return False
        return dd < timezone.now()

    @property
    def is_due_today(self):
        return bool(self.due_date) and self.due_date == timezone.localdate()

    @property
    def is_due_soon(self):
        """Due within the next 30 minutes and not yet overdue."""
        dd = self.due_datetime
        if not dd or self.completed:
            return False
        delta = (dd - timezone.now()).total_seconds()
        return 0 <= delta <= 1800

    @property
    def countdown_text(self):
        """Human-friendly remaining/overdue time, e.g. 'Due in 2h 35m'."""
        dd = self.due_datetime
        if not dd:
            return ''
        if self.completed:
            return 'Completed'
        delta = dd - timezone.now()
        seconds = int(delta.total_seconds())
        if seconds < 0:
            return 'Overdue'
        days, rem = divmod(seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes = rem // 60
        if days > 0:
            return f'Due in {days}d {hours}h'
        if hours > 0:
            return f'Due in {hours}h {minutes}m'
        if minutes > 0:
            return f'Due in {minutes}m'
        return 'Due now'

    @property
    def priority_label(self):
        return self.get_priority_display()

    @property
    def category_label(self):
        return self.category.name if self.category else 'Uncategorized'

    @property
    def category_color(self):
        return self.category.color if self.category else '#64748b'

    @property
    def root_task(self):
        """The original task in a recurring chain (self if not an occurrence
        generated from another task)."""
        return self.parent_task or self


class ActivityLog(models.Model):
    """A lightweight, append-only record of notable actions a user takes on
    their tasks. Used to power the activity history view.

    ``task`` is SET_NULL on delete (not CASCADE) so a task's history
    survives — including its own "deleted" entry — after the task itself is
    gone.
    """

    class Action(models.TextChoices):
        CREATED = 'created', 'Created'
        COMPLETED = 'completed', 'Completed'
        REOPENED = 'reopened', 'Reopened'
        PRIORITY_CHANGED = 'priority_changed', 'Priority changed'
        DUE_DATE_CHANGED = 'due_date_changed', 'Due date changed'
        PINNED = 'pinned', 'Pinned'
        UNPINNED = 'unpinned', 'Unpinned'
        DELETED = 'deleted', 'Deleted'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='activity_log'
    )
    task = models.ForeignKey(
        Task, on_delete=models.SET_NULL, null=True, blank=True, related_name='activity_entries'
    )
    action = models.CharField(max_length=20, choices=Action.choices)
    description = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', '-created_at'])]

    def __str__(self):
        return self.description
