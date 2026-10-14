"""IDOR / cross-user isolation tests for tasks (the API's equivalent checks
live in api/tests.py)."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from tasks.models import Task


class TaskIsolationTests(TestCase):
    """Ensures user A can never view, edit, complete, pin, or delete a task
    that belongs to user B, even when guessing/editing the URL's pk."""

    def setUp(self):
        self.alice = User.objects.create_user(username='alice', password='pw12345!')
        self.bob = User.objects.create_user(username='bob', password='pw12345!')
        self.bobs_task = Task.objects.create(user=self.bob, title="Bob's private task", priority='low')
        self.client.login(username='alice', password='pw12345!')

    def test_cannot_view_other_users_task_on_edit_form(self):
        response = self.client.get(reverse('task_edit', args=[self.bobs_task.pk]))
        self.assertEqual(response.status_code, 404)

    def test_cannot_edit_other_users_task(self):
        response = self.client.post(reverse('task_edit', args=[self.bobs_task.pk]), {
            'title': 'Hacked title', 'priority': 'low', 'does_repeat': 'none', 'recurrence_interval': 1,
        })
        self.assertEqual(response.status_code, 404)
        self.bobs_task.refresh_from_db()
        self.assertEqual(self.bobs_task.title, "Bob's private task")

    def test_cannot_complete_other_users_task(self):
        response = self.client.post(reverse('task_toggle', args=[self.bobs_task.pk]))
        self.assertEqual(response.status_code, 404)
        self.bobs_task.refresh_from_db()
        self.assertFalse(self.bobs_task.completed)

    def test_cannot_pin_other_users_task(self):
        response = self.client.post(reverse('task_pin', args=[self.bobs_task.pk]))
        self.assertEqual(response.status_code, 404)
        self.bobs_task.refresh_from_db()
        self.assertFalse(self.bobs_task.pinned)

    def test_cannot_delete_other_users_task(self):
        response = self.client.post(reverse('task_delete', args=[self.bobs_task.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Task.objects.filter(pk=self.bobs_task.pk).exists())

    def test_dashboard_only_shows_own_tasks(self):
        Task.objects.create(user=self.alice, title="Alice's task", priority='low')
        response = self.client.get(reverse('dashboard'))
        # html=True compares as parsed HTML rather than a raw byte substring,
        # so the apostrophe matches regardless of how Django's autoescaping
        # renders it (e.g. "Alice&#x27;s task"). Without html=True this
        # assertion fails even though the page is correct — a test bug, not
        # an app bug.
        self.assertContains(response, "Alice's task", html=True)
        self.assertNotContains(response, "Bob's private task", html=True)

    def test_calendar_agenda_only_shows_own_tasks(self):
        from datetime import date
        Task.objects.create(user=self.alice, title="Alice's calendar task", priority='low', due_date=date(2030, 6, 15))
        Task.objects.create(user=self.bob, title="Bob's calendar task", priority='low', due_date=date(2030, 6, 15))
        response = self.client.get(reverse('calendar'), {'year': 2030, 'month': 6, 'date': '2030-06-15'})
        self.assertContains(response, "Alice's calendar task", html=True)
        self.assertNotContains(response, "Bob's calendar task", html=True)
