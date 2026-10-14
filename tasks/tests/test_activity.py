"""Feature 8 — activity history: logging on the actions that matter, and
strict per-user isolation on the history view itself."""
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from tasks.models import ActivityLog, Task
from tasks.services import group_activity_by_day


class ActivityLoggingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='pw12345!')
        self.client.login(username='alice', password='pw12345!')

    def test_creating_a_task_logs_activity(self):
        self.client.post(reverse('task_create'), {
            'title': 'New task', 'priority': 'low', 'does_repeat': 'none', 'recurrence_interval': 1,
            'reminder_offset': 'none',
        })
        self.assertTrue(ActivityLog.objects.filter(user=self.user, action='created').exists())

    def test_completing_a_task_logs_activity(self):
        task = Task.objects.create(user=self.user, title='Task', priority='low')
        self.client.post(reverse('task_toggle', args=[task.pk]))
        self.assertTrue(ActivityLog.objects.filter(user=self.user, task=task, action='completed').exists())

    def test_reopening_a_task_logs_activity(self):
        task = Task.objects.create(user=self.user, title='Task', priority='low', completed=True)
        self.client.post(reverse('task_toggle', args=[task.pk]))
        self.assertTrue(ActivityLog.objects.filter(user=self.user, task=task, action='reopened').exists())

    def test_pinning_and_unpinning_logs_activity(self):
        task = Task.objects.create(user=self.user, title='Task', priority='low')
        self.client.post(reverse('task_pin', args=[task.pk]))
        self.assertTrue(ActivityLog.objects.filter(user=self.user, task=task, action='pinned').exists())
        self.client.post(reverse('task_pin', args=[task.pk]))
        self.assertTrue(ActivityLog.objects.filter(user=self.user, task=task, action='unpinned').exists())

    def test_deleting_a_task_logs_activity(self):
        task = Task.objects.create(user=self.user, title='Doomed task', priority='low')
        self.client.post(reverse('task_delete', args=[task.pk]))
        self.assertTrue(ActivityLog.objects.filter(user=self.user, action='deleted', description__icontains='Doomed task').exists())

    def test_changing_priority_logs_activity_only_when_it_actually_changes(self):
        task = Task.objects.create(user=self.user, title='Task', priority='low')
        # No-op edit: same priority — should NOT log a priority_changed entry.
        self.client.post(reverse('task_edit', args=[task.pk]), {
            'title': 'Task', 'priority': 'low', 'does_repeat': 'none', 'recurrence_interval': 1,
            'reminder_offset': 'none',
        })
        self.assertFalse(ActivityLog.objects.filter(user=self.user, task=task, action='priority_changed').exists())

        # Real change — should log exactly once.
        self.client.post(reverse('task_edit', args=[task.pk]), {
            'title': 'Task', 'priority': 'high', 'does_repeat': 'none', 'recurrence_interval': 1,
            'reminder_offset': 'none',
        })
        self.assertEqual(
            ActivityLog.objects.filter(user=self.user, task=task, action='priority_changed').count(), 1
        )

    def test_changing_due_date_logs_activity(self):
        task = Task.objects.create(user=self.user, title='Task', priority='low')
        self.client.post(reverse('task_edit', args=[task.pk]), {
            'title': 'Task', 'priority': 'low', 'due_date': '2030-05-01',
            'does_repeat': 'none', 'recurrence_interval': 1, 'reminder_offset': 'none',
        })
        self.assertTrue(ActivityLog.objects.filter(user=self.user, task=task, action='due_date_changed').exists())


class ActivityViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='pw12345!')
        self.client.login(username='alice', password='pw12345!')

    def test_activity_page_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('activity'))
        self.assertEqual(response.status_code, 302)

    def test_activity_page_lists_entries(self):
        task = Task.objects.create(user=self.user, title='Visible task', priority='low')
        self.client.post(reverse('task_toggle', args=[task.pk]))
        response = self.client.get(reverse('activity'))
        self.assertContains(response, 'Visible task')

    def test_empty_activity_shows_empty_state(self):
        response = self.client.get(reverse('activity'))
        self.assertContains(response, 'No activity yet')


class ActivityIsolationTests(TestCase):
    """A user must never see another user's activity history."""

    def setUp(self):
        self.alice = User.objects.create_user(username='alice', password='pw12345!')
        self.bob = User.objects.create_user(username='bob', password='pw12345!')
        self.bobs_task = Task.objects.create(user=self.bob, title="Bob's secret task", priority='low')
        self.client.login(username='bob', password='pw12345!')
        self.client.post(reverse('task_toggle', args=[self.bobs_task.pk]))
        self.client.logout()
        self.client.login(username='alice', password='pw12345!')

    def test_activity_page_only_shows_own_entries(self):
        response = self.client.get(reverse('activity'))
        self.assertNotContains(response, "Bob's secret task", html=True)

    def test_activity_queryset_excludes_other_users(self):
        self.assertFalse(ActivityLog.objects.filter(user=self.alice).exists())
        self.assertTrue(ActivityLog.objects.filter(user=self.bob).exists())


class ActivityGroupingTests(TestCase):
    """Activity entries group into Today / Yesterday / Earlier buckets,
    preserving order within each bucket and omitting empty buckets."""

    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='pw12345!')

    def _entry(self, days_ago, description):
        entry = ActivityLog.objects.create(user=self.user, action='created', description=description)
        if days_ago:
            ActivityLog.objects.filter(pk=entry.pk).update(
                created_at=timezone.now() - timedelta(days=days_ago)
            )
        return entry

    def test_groups_into_today_yesterday_earlier(self):
        self._entry(0, 'Today entry')
        self._entry(1, 'Yesterday entry')
        self._entry(5, 'Older entry')

        entries = ActivityLog.objects.filter(user=self.user).order_by('-created_at')
        grouped = group_activity_by_day(entries)
        labels = [label for label, _ in grouped]
        self.assertEqual(labels, ['Today', 'Yesterday', 'Earlier'])

    def test_empty_buckets_are_omitted(self):
        self._entry(0, 'Only today entry')
        entries = ActivityLog.objects.filter(user=self.user)
        grouped = group_activity_by_day(entries)
        self.assertEqual([label for label, _ in grouped], ['Today'])

    def test_activity_page_renders_group_labels(self):
        self.client.login(username='alice', password='pw12345!')
        self._entry(0, 'A visible entry')
        response = self.client.get(reverse('activity'))
        self.assertContains(response, 'Today')
        self.assertContains(response, 'A visible entry')
