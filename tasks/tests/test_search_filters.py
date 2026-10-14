"""Feature 2 (advanced search) and Feature 3 (advanced combinable filters).
These layer on top of the original single ?filter=... quick-pills, which
are covered separately in test_tasks.py and must keep working unchanged."""
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from tasks.models import Category, Task


class AdvancedSearchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='pw12345!')
        self.client.login(username='alice', password='pw12345!')

    def test_search_matches_priority_name(self):
        Task.objects.create(user=self.user, title='Urgent server fix', priority='high')
        Task.objects.create(user=self.user, title='Read a book', priority='low')
        response = self.client.get(reverse('dashboard'), {'filter': 'all', 'q': 'high'})
        self.assertContains(response, 'Urgent server fix')
        self.assertNotContains(response, 'Read a book')

    def test_search_is_scoped_to_current_user(self):
        bob = User.objects.create_user(username='bob', password='pw12345!')
        Task.objects.create(user=bob, title='Bob secret project', priority='low')
        Task.objects.create(user=self.user, title='Alice project', priority='low')
        response = self.client.get(reverse('dashboard'), {'filter': 'all', 'q': 'project'})
        self.assertContains(response, 'Alice project')
        self.assertNotContains(response, 'Bob secret project', html=True)

    def test_search_result_count_reflected_in_paginator(self):
        Task.objects.create(user=self.user, title='Match one', priority='low')
        Task.objects.create(user=self.user, title='Match two', priority='low')
        Task.objects.create(user=self.user, title='No hit here', priority='low')
        response = self.client.get(reverse('dashboard'), {'filter': 'all', 'q': 'match'})
        self.assertEqual(response.context['page_obj'].paginator.count, 2)


class CombinedFilterTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='pw12345!')
        self.client.login(username='alice', password='pw12345!')
        self.category = Category.objects.filter(user=self.user).first()
        self.today = date.today()

    def test_status_filter_active(self):
        Task.objects.create(user=self.user, title='Open task', priority='low')
        Task.objects.create(user=self.user, title='Done task', priority='low', completed=True)
        response = self.client.get(reverse('dashboard'), {'filter': 'all', 'status': 'active'})
        self.assertContains(response, 'Open task')
        self.assertNotContains(response, 'Done task')

    def test_status_filter_completed_overrides_all_pills_implicit_active_only(self):
        """?filter=all normally means "active tasks only" — status=completed
        must be able to override that rather than combining into an
        impossible completed=True AND completed=False query."""
        Task.objects.create(user=self.user, title='Open task', priority='low')
        Task.objects.create(user=self.user, title='Done task', priority='low', completed=True)
        response = self.client.get(reverse('dashboard'), {'filter': 'all', 'status': 'completed'})
        self.assertContains(response, 'Done task')
        self.assertNotContains(response, 'Open task')

    def test_priority_and_category_combine(self):
        matching = Task.objects.create(
            user=self.user, title='Matches both', priority='high', category=self.category,
        )
        Task.objects.create(user=self.user, title='Wrong priority', priority='low', category=self.category)
        other_category = Category.objects.filter(user=self.user).exclude(pk=self.category.pk).first()
        Task.objects.create(user=self.user, title='Wrong category', priority='high', category=other_category)

        response = self.client.get(reverse('dashboard'), {
            'filter': 'all', 'priority': 'high', 'category': self.category.pk,
        })
        self.assertContains(response, 'Matches both')
        self.assertNotContains(response, 'Wrong priority')
        self.assertNotContains(response, 'Wrong category')

    def test_due_today_filter(self):
        Task.objects.create(user=self.user, title='Due today task', priority='low', due_date=self.today)
        Task.objects.create(user=self.user, title='Due later task', priority='low', due_date=self.today + timedelta(days=5))
        response = self.client.get(reverse('dashboard'), {'filter': 'all', 'due': 'today'})
        self.assertContains(response, 'Due today task')
        self.assertNotContains(response, 'Due later task')

    def test_due_none_filter(self):
        Task.objects.create(user=self.user, title='No due date task', priority='low')
        Task.objects.create(user=self.user, title='Has due date task', priority='low', due_date=self.today)
        response = self.client.get(reverse('dashboard'), {'filter': 'all', 'due': 'none'})
        self.assertContains(response, 'No due date task')
        self.assertNotContains(response, 'Has due date task')

    def test_pinned_advanced_filter(self):
        Task.objects.create(user=self.user, title='Pinned one', priority='low', pinned=True)
        Task.objects.create(user=self.user, title='Not pinned', priority='low')
        response = self.client.get(reverse('dashboard'), {'filter': 'all', 'pinned': '1'})
        self.assertContains(response, 'Pinned one')
        self.assertNotContains(response, 'Not pinned')

    def test_advanced_filters_persist_in_url_and_are_flagged_active(self):
        response = self.client.get(reverse('dashboard'), {'filter': 'all', 'priority': 'high'})
        self.assertTrue(response.context['advanced_filters_active'])
        self.assertEqual(response.context['filter_priority'], 'high')

    def test_active_filter_count_reflects_number_of_filters_applied(self):
        response = self.client.get(reverse('dashboard'), {
            'filter': 'all', 'priority': 'high', 'due': 'today', 'pinned': '1',
        })
        self.assertEqual(response.context['active_filter_count'], 3)

    def test_active_filter_count_is_zero_by_default(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['active_filter_count'], 0)

    def test_no_advanced_filters_by_default(self):
        response = self.client.get(reverse('dashboard'))
        self.assertFalse(response.context['advanced_filters_active'])

    def test_legacy_quick_filter_still_works_unchanged(self):
        """Regression guard for the pre-existing ?filter=high behavior."""
        Task.objects.create(user=self.user, title='High one', priority='high')
        Task.objects.create(user=self.user, title='Low one', priority='low')
        response = self.client.get(reverse('dashboard'), {'filter': 'high'})
        self.assertContains(response, 'High one')
        self.assertNotContains(response, 'Low one')
