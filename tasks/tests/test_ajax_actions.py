"""Feature 1 — AJAX task actions. Every endpoint must behave exactly as
before for a plain (non-AJAX) POST, and return JSON with updated counters
when the request carries the X-Requested-With header. Ownership is checked
identically in both modes."""
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from tasks.models import ActivityLog, Task

AJAX_HEADERS = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}


class AjaxToggleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='pw12345!')
        self.client.login(username='alice', password='pw12345!')
        self.task = Task.objects.create(user=self.user, title='Write report', priority='high')

    def test_ajax_complete_returns_json_with_counters(self):
        response = self.client.post(reverse('task_toggle', args=[self.task.pk]), **AJAX_HEADERS)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertTrue(data['completed'])
        self.assertIn('stats', data)
        self.assertIn('progress_pct', data)
        self.assertIn('sidebar_counts', data)
        self.assertEqual(data['stats']['completed'], 1)

    def test_ajax_reopen_returns_json(self):
        self.task.completed = True
        self.task.save(update_fields=['completed'])
        response = self.client.post(reverse('task_toggle', args=[self.task.pk]), **AJAX_HEADERS)
        data = response.json()
        self.assertFalse(data['completed'])

    def test_non_ajax_toggle_still_redirects_unchanged(self):
        """Regression guard: a plain form POST (no AJAX header) must behave
        exactly as it did before AJAX support was added."""
        response = self.client.post(reverse('task_toggle', args=[self.task.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('dashboard'))

    def test_ajax_toggle_logs_activity(self):
        self.client.post(reverse('task_toggle', args=[self.task.pk]), **AJAX_HEADERS)
        self.assertTrue(
            ActivityLog.objects.filter(user=self.user, task=self.task, action='completed').exists()
        )


class AjaxPinTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='pw12345!')
        self.client.login(username='alice', password='pw12345!')
        self.task = Task.objects.create(user=self.user, title='Pin me', priority='low')

    def test_ajax_pin_returns_json(self):
        response = self.client.post(reverse('task_pin', args=[self.task.pk]), **AJAX_HEADERS)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertTrue(data['pinned'])
        self.task.refresh_from_db()
        self.assertTrue(self.task.pinned)


class AjaxDeleteTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='pw12345!')
        self.client.login(username='alice', password='pw12345!')
        self.task = Task.objects.create(user=self.user, title='Delete me', priority='low')

    def test_ajax_delete_returns_json_and_removes_task(self):
        response = self.client.post(reverse('task_delete', args=[self.task.pk]), **AJAX_HEADERS)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertFalse(Task.objects.filter(pk=self.task.pk).exists())

    def test_ajax_delete_logs_activity_with_task_nulled(self):
        task_id = self.task.pk
        self.client.post(reverse('task_delete', args=[task_id]), **AJAX_HEADERS)
        entry = ActivityLog.objects.get(user=self.user, action='deleted', description__icontains='Delete me')
        self.assertIsNone(entry.task_id)


class AjaxIsolationTests(TestCase):
    """AJAX mode must never bypass ownership checks."""

    def setUp(self):
        self.alice = User.objects.create_user(username='alice', password='pw12345!')
        self.bob = User.objects.create_user(username='bob', password='pw12345!')
        self.bobs_task = Task.objects.create(user=self.bob, title="Bob's task", priority='low')
        self.client.login(username='alice', password='pw12345!')

    def test_ajax_cannot_toggle_other_users_task(self):
        response = self.client.post(reverse('task_toggle', args=[self.bobs_task.pk]), **AJAX_HEADERS)
        self.assertEqual(response.status_code, 404)
        self.bobs_task.refresh_from_db()
        self.assertFalse(self.bobs_task.completed)

    def test_ajax_cannot_pin_other_users_task(self):
        response = self.client.post(reverse('task_pin', args=[self.bobs_task.pk]), **AJAX_HEADERS)
        self.assertEqual(response.status_code, 404)

    def test_ajax_cannot_delete_other_users_task(self):
        response = self.client.post(reverse('task_delete', args=[self.bobs_task.pk]), **AJAX_HEADERS)
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Task.objects.filter(pk=self.bobs_task.pk).exists())
