"""API tests: CRUD, authentication, and cross-user isolation (IDOR checks)."""
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from tasks.models import Category, Task


class TaskAPIAuthTests(APITestCase):
    def test_list_requires_authentication(self):
        response = self.client.get('/api/tasks/')
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))


class TaskAPICRUDTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='pw12345!')
        self.client.force_authenticate(user=self.user)
        self.category = Category.objects.filter(user=self.user).first()

    def test_create_task(self):
        response = self.client.post('/api/tasks/', {
            'title': 'Write tests', 'priority': 'high', 'category': self.category.id,
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Task.objects.filter(user=self.user, title='Write tests').count(), 1)

    def test_list_only_returns_own_tasks(self):
        bob = User.objects.create_user(username='bob', password='pw12345!')
        Task.objects.create(user=bob, title="Bob's task", priority='low')
        Task.objects.create(user=self.user, title="Alice's task", priority='low')

        response = self.client.get('/api/tasks/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # DEFAULT_PAGINATION_CLASS wraps list responses as
        # {"count", "next", "previous", "results"}.
        titles = [t['title'] for t in response.data['results']]
        self.assertIn("Alice's task", titles)
        self.assertNotIn("Bob's task", titles)

    def test_retrieve_update_delete_own_task(self):
        task = Task.objects.create(user=self.user, title='Original', priority='low')

        detail_url = f'/api/tasks/{task.id}/'
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.patch(detail_url, {'title': 'Updated'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        task.refresh_from_db()
        self.assertEqual(task.title, 'Updated')

        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Task.objects.filter(pk=task.pk).exists())

    def test_complete_action_generates_next_recurring_occurrence(self):
        task = Task.objects.create(
            user=self.user, title='Daily standup', priority='medium',
            due_date='2030-01-01', is_recurring=True, recurrence_type='daily',
        )
        response = self.client.post(f'/api/tasks/{task.id}/complete/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(Task.objects.filter(user=self.user, parent_task=task, due_date='2030-01-02').exists())

    def test_pin_action_toggles(self):
        task = Task.objects.create(user=self.user, title='Pin me', priority='low')
        response = self.client.post(f'/api/tasks/{task.id}/pin/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        task.refresh_from_db()
        self.assertTrue(task.pinned)

    def test_cannot_assign_another_users_category(self):
        bob = User.objects.create_user(username='bob', password='pw12345!')
        bobs_category = Category.objects.filter(user=bob).first()
        response = self.client.post('/api/tasks/', {'title': 'Sneaky', 'category': bobs_category.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TaskAPIIsolationTests(APITestCase):
    """IDOR checks: user A must never read, modify, or delete user B's task
    by directly hitting its ID."""

    def setUp(self):
        self.alice = User.objects.create_user(username='alice', password='pw12345!')
        self.bob = User.objects.create_user(username='bob', password='pw12345!')
        self.bobs_task = Task.objects.create(user=self.bob, title="Bob's task", priority='low')
        self.client.force_authenticate(user=self.alice)

    def test_cannot_retrieve_other_users_task(self):
        response = self.client.get(f'/api/tasks/{self.bobs_task.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_update_other_users_task(self):
        response = self.client.patch(f'/api/tasks/{self.bobs_task.id}/', {'title': 'Hacked'})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.bobs_task.refresh_from_db()
        self.assertEqual(self.bobs_task.title, "Bob's task")

    def test_cannot_delete_other_users_task(self):
        response = self.client.delete(f'/api/tasks/{self.bobs_task.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Task.objects.filter(pk=self.bobs_task.pk).exists())

    def test_cannot_complete_other_users_task_via_action(self):
        response = self.client.post(f'/api/tasks/{self.bobs_task.id}/complete/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class CategoryAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='pw12345!')
        self.client.force_authenticate(user=self.user)

    def test_default_categories_created_for_new_user(self):
        response = self.client.get('/api/categories/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data['results']), 1)

    def test_create_category(self):
        response = self.client.post('/api/categories/', {'name': 'Fitness', 'color': '#22c55e'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Category.objects.filter(user=self.user, name='Fitness').exists())


class TaskAPIOrderingAndFilteringTests(APITestCase):
    """Feature 16 — API search/filter/ordering, and isolation for each."""

    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='pw12345!')
        self.client.force_authenticate(user=self.user)
        self.work = Category.objects.filter(user=self.user, name='Work').first()
        self.study = Category.objects.filter(user=self.user, name='Study').first()
        Task.objects.create(user=self.user, title='B task', priority='low', category=self.work)
        Task.objects.create(user=self.user, title='A task', priority='high', category=self.study)

    def test_ordering_by_title(self):
        response = self.client.get('/api/tasks/?ordering=title')
        titles = [t['title'] for t in response.data['results']]
        self.assertEqual(titles, ['A task', 'B task'])

    def test_ordering_by_title_descending(self):
        response = self.client.get('/api/tasks/?ordering=-title')
        titles = [t['title'] for t in response.data['results']]
        self.assertEqual(titles, ['B task', 'A task'])

    def test_unrecognized_ordering_value_is_ignored_not_erroring(self):
        response = self.client.get('/api/tasks/?ordering=not_a_real_field')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_filter_by_category(self):
        response = self.client.get(f'/api/tasks/?category={self.work.id}')
        titles = [t['title'] for t in response.data['results']]
        self.assertEqual(titles, ['B task'])

    def test_filter_by_priority(self):
        response = self.client.get('/api/tasks/?priority=high')
        titles = [t['title'] for t in response.data['results']]
        self.assertEqual(titles, ['A task'])

    def test_search_filters_by_title(self):
        response = self.client.get('/api/tasks/?search=B task')
        titles = [t['title'] for t in response.data['results']]
        self.assertEqual(titles, ['B task'])


class TaskAPIFilterIsolationTests(APITestCase):
    """Filtering/searching/ordering must never surface another user's
    tasks or categories, regardless of the query parameters supplied."""

    def setUp(self):
        self.alice = User.objects.create_user(username='alice', password='pw12345!')
        self.bob = User.objects.create_user(username='bob', password='pw12345!')
        Task.objects.create(user=self.alice, title='Alice task', priority='high')
        Task.objects.create(user=self.bob, title='Bob task', priority='high')
        self.client.force_authenticate(user=self.alice)

    def test_priority_filter_stays_scoped_to_requesting_user(self):
        response = self.client.get('/api/tasks/?priority=high')
        titles = [t['title'] for t in response.data['results']]
        self.assertIn('Alice task', titles)
        self.assertNotIn('Bob task', titles)

    def test_search_stays_scoped_to_requesting_user(self):
        response = self.client.get('/api/tasks/?search=task')
        titles = [t['title'] for t in response.data['results']]
        self.assertIn('Alice task', titles)
        self.assertNotIn('Bob task', titles)

    def test_category_filter_cannot_leak_another_users_category_id(self):
        bobs_category = Category.objects.filter(user=self.bob).first()
        response = self.client.get(f'/api/tasks/?category={bobs_category.id}')
        # Alice has no tasks in a category with that id (it belongs to Bob's
        # own categories, which are entirely separate rows), so this must
        # come back empty rather than somehow matching Bob's tasks.
        self.assertEqual(response.data['results'], [])

    def test_ordering_never_exposes_other_users_tasks(self):
        response = self.client.get('/api/tasks/?ordering=title')
        titles = [t['title'] for t in response.data['results']]
        self.assertNotIn('Bob task', titles)
