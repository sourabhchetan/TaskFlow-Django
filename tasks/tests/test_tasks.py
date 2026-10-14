"""Task CRUD, completion, pinning, filtering, sorting, search, and pagination."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from tasks.models import Category, Task


class TaskCRUDTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='pw12345!')
        self.client.login(username='alice', password='pw12345!')
        self.category = Category.objects.filter(user=self.user).first()

    def test_create_task(self):
        response = self.client.post(reverse('task_create'), {
            'title': 'Write report',
            'description': 'Quarterly report',
            'category': self.category.id,
            'priority': 'high',
            'due_date': '2030-01-01',
            'due_time': '09:00',
            'does_repeat': 'none',
            'recurrence_interval': 1,
            'reminder_offset': 'none',
        })
        self.assertRedirects(response, reverse('dashboard'))
        self.assertEqual(Task.objects.filter(user=self.user, title='Write report').count(), 1)

    def test_create_task_requires_title(self):
        response = self.client.post(reverse('task_create'), {
            'title': '',
            'priority': 'high',
            'does_repeat': 'none',
            'recurrence_interval': 1,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Task.objects.count(), 0)

    def test_edit_task(self):
        task = Task.objects.create(user=self.user, title='Old title', priority='low')
        response = self.client.post(reverse('task_edit', args=[task.pk]), {
            'title': 'New title',
            'description': '',
            'priority': 'medium',
            'does_repeat': 'none',
            'recurrence_interval': 1,
            'reminder_offset': 'none',
        })
        self.assertRedirects(response, reverse('dashboard'))
        task.refresh_from_db()
        self.assertEqual(task.title, 'New title')

    def test_complete_task_sets_completed_at(self):
        task = Task.objects.create(user=self.user, title='Task', priority='low')
        self.client.post(reverse('task_toggle', args=[task.pk]))
        task.refresh_from_db()
        self.assertTrue(task.completed)
        self.assertIsNotNone(task.completed_at)

        self.client.post(reverse('task_toggle', args=[task.pk]))
        task.refresh_from_db()
        self.assertFalse(task.completed)
        self.assertIsNone(task.completed_at)

    def test_delete_task(self):
        task = Task.objects.create(user=self.user, title='Delete me', priority='low')
        self.client.post(reverse('task_delete', args=[task.pk]))
        self.assertFalse(Task.objects.filter(pk=task.pk).exists())

    def test_pin_task_toggle(self):
        task = Task.objects.create(user=self.user, title='Pin me', priority='low')
        self.client.post(reverse('task_pin', args=[task.pk]))
        task.refresh_from_db()
        self.assertTrue(task.pinned)
        self.client.post(reverse('task_pin', args=[task.pk]))
        task.refresh_from_db()
        self.assertFalse(task.pinned)

    def test_cannot_assign_another_users_category(self):
        bob = User.objects.create_user(username='bob', password='pw12345!')
        bobs_category = Category.objects.filter(user=bob).first()
        response = self.client.post(reverse('task_create'), {
            'title': 'Sneaky',
            'category': bobs_category.id,
            'priority': 'low',
            'does_repeat': 'none',
            'recurrence_interval': 1,
        })
        # The category field's queryset is scoped to the user's own
        # categories, so submitting someone else's category id is an
        # invalid choice and the form re-renders with an error.
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Task.objects.filter(title='Sneaky').exists())


class TaskFilterSortSearchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='pw12345!')
        self.client.login(username='alice', password='pw12345!')

    def test_search_by_title(self):
        Task.objects.create(user=self.user, title='Django project', priority='low')
        Task.objects.create(user=self.user, title='Buy groceries', priority='low')
        response = self.client.get(reverse('dashboard'), {'q': 'django'})
        self.assertContains(response, 'Django project')
        self.assertNotContains(response, 'Buy groceries')

    def test_filter_high_priority(self):
        Task.objects.create(user=self.user, title='Urgent', priority='high')
        Task.objects.create(user=self.user, title='Later', priority='low')
        response = self.client.get(reverse('dashboard'), {'filter': 'high'})
        self.assertContains(response, 'Urgent')
        self.assertNotContains(response, 'Later')

    def test_filter_pinned(self):
        Task.objects.create(user=self.user, title='Pinned task', priority='low', pinned=True)
        Task.objects.create(user=self.user, title='Regular task', priority='low')
        response = self.client.get(reverse('dashboard'), {'filter': 'pinned'})
        self.assertContains(response, 'Pinned task')
        self.assertNotContains(response, 'Regular task')

    def test_filter_completed(self):
        Task.objects.create(user=self.user, title='Done task', priority='low', completed=True)
        Task.objects.create(user=self.user, title='Open task', priority='low')
        response = self.client.get(reverse('dashboard'), {'filter': 'completed'})
        self.assertContains(response, 'Done task')
        self.assertNotContains(response, 'Open task')

    def test_sort_by_priority(self):
        Task.objects.create(user=self.user, title='Low one', priority='low')
        Task.objects.create(user=self.user, title='High one', priority='high')
        response = self.client.get(reverse('dashboard'), {'sort': 'priority'})
        content = response.content.decode()
        self.assertLess(content.index('High one'), content.index('Low one'))

    def test_pagination(self):
        for i in range(15):
            Task.objects.create(user=self.user, title=f'Task {i}', priority='low')
        response = self.client.get(reverse('dashboard'), {'filter': 'all'})
        self.assertEqual(len(response.context['tasks']), 9)
        self.assertTrue(response.context['page_obj'].has_next())


class TaskCreateQuickStartTests(TestCase):
    """The empty-state 'Study / Work / Personal' quick-start links pre-fill
    the category on the create form via an optional ?category= param."""

    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='pw12345!')
        self.client.login(username='alice', password='pw12345!')

    def test_category_hint_prefills_matching_category(self):
        study = Category.objects.get(user=self.user, name='Study')
        response = self.client.get(reverse('task_create'), {'category': 'Study'})
        self.assertEqual(response.context['form'].initial.get('category'), study.pk)

    def test_category_hint_is_case_insensitive(self):
        work = Category.objects.get(user=self.user, name='Work')
        response = self.client.get(reverse('task_create'), {'category': 'work'})
        self.assertEqual(response.context['form'].initial.get('category'), work.pk)

    def test_unknown_category_hint_is_ignored_gracefully(self):
        response = self.client.get(reverse('task_create'), {'category': 'Not A Real Category'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('category', response.context['form'].initial)

    def test_category_hint_never_matches_another_users_category(self):
        bob = User.objects.create_user(username='bob', password='pw12345!')
        # Bob's own "Study" category has a different pk than Alice's.
        bobs_study = Category.objects.get(user=bob, name='Study')
        alice_study = Category.objects.get(user=self.user, name='Study')
        self.assertNotEqual(bobs_study.pk, alice_study.pk)

        response = self.client.get(reverse('task_create'), {'category': 'Study'})
        self.assertEqual(response.context['form'].initial.get('category'), alice_study.pk)
