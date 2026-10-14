"""Calendar, analytics, profile, and settings view tests."""
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from tasks.models import Task


class CalendarViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='pw12345!')
        self.client.login(username='alice', password='pw12345!')

    def test_calendar_loads(self):
        response = self.client.get(reverse('calendar'))
        self.assertEqual(response.status_code, 200)

    def test_calendar_shows_task_count_on_correct_day(self):
        Task.objects.create(user=self.user, title='Meeting', priority='low', due_date=date(2030, 3, 10))
        response = self.client.get(reverse('calendar'), {'year': 2030, 'month': 3})
        day_with_task = next(
            day for week in response.context['weeks'] for day in week if day['date'] == date(2030, 3, 10)
        )
        self.assertEqual(day_with_task['task_count'], 1)

    def test_invalid_month_falls_back_to_today(self):
        response = self.client.get(reverse('calendar'), {'year': 'nope', 'month': 'nope'})
        self.assertEqual(response.status_code, 200)


class AnalyticsViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='pw12345!')
        self.client.login(username='alice', password='pw12345!')

    def test_analytics_loads(self):
        response = self.client.get(reverse('analytics'))
        self.assertEqual(response.status_code, 200)

    def test_analytics_reflects_completed_tasks(self):
        Task.objects.create(user=self.user, title='Done', priority='low', completed=True)
        Task.objects.create(user=self.user, title='Open', priority='low')
        response = self.client.get(reverse('analytics'))
        self.assertEqual(response.context['stats']['total'], 2)
        self.assertEqual(response.context['stats']['completed'], 1)


class ProfileSettingsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='pw12345!', email='old@example.com')
        self.client.login(username='alice', password='pw12345!')

    def test_profile_shows_stats(self):
        Task.objects.create(user=self.user, title='Done', priority='low', completed=True)
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.context['total_tasks'], 1)
        self.assertEqual(response.context['completion_rate'], 100)

    def test_update_email(self):
        response = self.client.post(reverse('profile'), {'email': 'new@example.com'})
        self.assertRedirects(response, reverse('profile'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'new@example.com')

    def test_settings_saves_preferences(self):
        response = self.client.post(reverse('settings'), {
            'theme_preference': 'dark',
            'default_priority': 'high',
            'default_view': 'today',
            'default_sort': 'priority',
        })
        self.assertRedirects(response, reverse('settings'))
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.theme_preference, 'dark')
        self.assertEqual(self.user.profile.default_view, 'today')
        self.assertFalse(self.user.profile.reminders_enabled)  # unchecked checkbox
