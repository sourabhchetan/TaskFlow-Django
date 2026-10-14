"""Feature 4 — bulk task actions. Every action must be scoped to the
requesting user's own tasks, even when other users' ids are mixed into the
submitted list."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from tasks.models import Task


class BulkActionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='pw12345!')
        self.client.login(username='alice', password='pw12345!')
        self.t1 = Task.objects.create(user=self.user, title='Task 1', priority='low')
        self.t2 = Task.objects.create(user=self.user, title='Task 2', priority='low')
        self.t3 = Task.objects.create(user=self.user, title='Task 3', priority='low')

    def test_bulk_complete(self):
        response = self.client.post(reverse('bulk_action'), {
            'action': 'complete', 'task_ids': [self.t1.pk, self.t2.pk],
        })
        self.assertRedirects(response, reverse('dashboard'))
        self.t1.refresh_from_db()
        self.t2.refresh_from_db()
        self.t3.refresh_from_db()
        self.assertTrue(self.t1.completed)
        self.assertTrue(self.t2.completed)
        self.assertFalse(self.t3.completed)
        self.assertIsNotNone(self.t1.completed_at)

    def test_bulk_reopen(self):
        Task.objects.filter(pk__in=[self.t1.pk, self.t2.pk]).update(completed=True)
        self.client.post(reverse('bulk_action'), {'action': 'reopen', 'task_ids': [self.t1.pk]})
        self.t1.refresh_from_db()
        self.t2.refresh_from_db()
        self.assertFalse(self.t1.completed)
        self.assertTrue(self.t2.completed)

    def test_bulk_pin_and_unpin(self):
        self.client.post(reverse('bulk_action'), {'action': 'pin', 'task_ids': [self.t1.pk, self.t2.pk]})
        self.t1.refresh_from_db()
        self.t2.refresh_from_db()
        self.assertTrue(self.t1.pinned)
        self.assertTrue(self.t2.pinned)

        self.client.post(reverse('bulk_action'), {'action': 'unpin', 'task_ids': [self.t1.pk]})
        self.t1.refresh_from_db()
        self.t2.refresh_from_db()
        self.assertFalse(self.t1.pinned)
        self.assertTrue(self.t2.pinned)

    def test_bulk_priority_change(self):
        response = self.client.post(reverse('bulk_action'), {
            'action': 'priority', 'priority': 'high', 'task_ids': [self.t1.pk, self.t2.pk, self.t3.pk],
        })
        self.assertRedirects(response, reverse('dashboard'))
        for task in (self.t1, self.t2, self.t3):
            task.refresh_from_db()
            self.assertEqual(task.priority, 'high')

    def test_bulk_priority_rejects_invalid_value(self):
        response = self.client.post(reverse('bulk_action'), {
            'action': 'priority', 'priority': 'urgent', 'task_ids': [self.t1.pk],
        })
        self.assertRedirects(response, reverse('dashboard'))
        self.t1.refresh_from_db()
        self.assertEqual(self.t1.priority, 'low')  # unchanged

    def test_bulk_delete(self):
        self.client.post(reverse('bulk_action'), {'action': 'delete', 'task_ids': [self.t1.pk, self.t2.pk]})
        self.assertFalse(Task.objects.filter(pk=self.t1.pk).exists())
        self.assertFalse(Task.objects.filter(pk=self.t2.pk).exists())
        self.assertTrue(Task.objects.filter(pk=self.t3.pk).exists())

    def test_bulk_action_requires_task_ids(self):
        response = self.client.post(reverse('bulk_action'), {'action': 'complete', 'task_ids': []})
        self.assertRedirects(response, reverse('dashboard'))
        for task in (self.t1, self.t2, self.t3):
            task.refresh_from_db()
            self.assertFalse(task.completed)

    def test_bulk_action_rejects_unknown_action(self):
        response = self.client.post(reverse('bulk_action'), {'action': 'launch_rockets', 'task_ids': [self.t1.pk]})
        self.assertRedirects(response, reverse('dashboard'))
        self.t1.refresh_from_db()
        self.assertFalse(self.t1.completed)

    def test_bulk_action_ajax_returns_json(self):
        response = self.client.post(
            reverse('bulk_action'),
            {'action': 'complete', 'task_ids': [self.t1.pk]},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertIn(self.t1.pk, data['task_ids'])
        self.assertIn('stats', data)


class BulkActionIsolationTests(TestCase):
    """A user must never be able to bulk-modify another user's tasks, even
    by mixing valid and invalid ids in the same request."""

    def setUp(self):
        self.alice = User.objects.create_user(username='alice', password='pw12345!')
        self.bob = User.objects.create_user(username='bob', password='pw12345!')
        self.alice_task = Task.objects.create(user=self.alice, title="Alice's task", priority='low')
        self.bob_task = Task.objects.create(user=self.bob, title="Bob's task", priority='low')
        self.client.login(username='alice', password='pw12345!')

    def test_bulk_complete_only_affects_own_tasks(self):
        self.client.post(reverse('bulk_action'), {
            'action': 'complete', 'task_ids': [self.alice_task.pk, self.bob_task.pk],
        })
        self.alice_task.refresh_from_db()
        self.bob_task.refresh_from_db()
        self.assertTrue(self.alice_task.completed)
        self.assertFalse(self.bob_task.completed)

    def test_bulk_delete_only_affects_own_tasks(self):
        self.client.post(reverse('bulk_action'), {
            'action': 'delete', 'task_ids': [self.alice_task.pk, self.bob_task.pk],
        })
        self.assertFalse(Task.objects.filter(pk=self.alice_task.pk).exists())
        self.assertTrue(Task.objects.filter(pk=self.bob_task.pk).exists())

    def test_bulk_action_with_only_other_users_tasks_affects_nothing(self):
        response = self.client.post(reverse('bulk_action'), {
            'action': 'complete', 'task_ids': [self.bob_task.pk],
        })
        self.assertEqual(response.status_code, 302)
        self.bob_task.refresh_from_db()
        self.assertFalse(self.bob_task.completed)

    def test_bulk_action_requires_login(self):
        self.client.logout()
        response = self.client.post(reverse('bulk_action'), {'action': 'complete', 'task_ids': [self.alice_task.pk]})
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)
