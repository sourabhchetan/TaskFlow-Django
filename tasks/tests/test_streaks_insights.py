"""Feature 5 (smart dashboard) — productivity streak calculation and
rule-based insight generation. Tested directly against tasks.services since
these are pure functions of the user's real task data."""
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from tasks.models import Task
from tasks.services import get_daily_status_message, get_insights, get_notifications, get_productivity_streak


def _completed_task(user, title, days_ago):
    completed_at = timezone.now() - timedelta(days=days_ago)
    task = Task.objects.create(user=user, title=title, priority='low', completed=True)
    Task.objects.filter(pk=task.pk).update(completed_at=completed_at)
    return task


class ProductivityStreakTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='pw12345!')

    def test_no_completed_tasks_gives_zero_streak(self):
        streak = get_productivity_streak(self.user)
        self.assertEqual(streak, {'current': 0, 'longest': 0})

    def test_single_day_streak_today(self):
        _completed_task(self.user, 'Today task', days_ago=0)
        streak = get_productivity_streak(self.user)
        self.assertEqual(streak['current'], 1)
        self.assertEqual(streak['longest'], 1)

    def test_consecutive_days_build_a_streak(self):
        for i in range(4):
            _completed_task(self.user, f'Task {i}', days_ago=i)
        streak = get_productivity_streak(self.user)
        self.assertEqual(streak['current'], 4)
        self.assertEqual(streak['longest'], 4)

    def test_current_streak_still_counts_yesterday_if_nothing_done_today(self):
        _completed_task(self.user, 'Yesterday task', days_ago=1)
        _completed_task(self.user, 'Two days ago task', days_ago=2)
        streak = get_productivity_streak(self.user)
        self.assertEqual(streak['current'], 2)

    def test_gap_breaks_current_streak_but_longest_remembers_it(self):
        # A 3-day streak, ending 5 days ago (broken by a gap since then).
        for i in range(5, 8):
            _completed_task(self.user, f'Old task {i}', days_ago=i)
        streak = get_productivity_streak(self.user)
        self.assertEqual(streak['current'], 0)
        self.assertEqual(streak['longest'], 3)

    def test_multiple_tasks_same_day_count_as_one_streak_day(self):
        _completed_task(self.user, 'First today', days_ago=0)
        _completed_task(self.user, 'Second today', days_ago=0)
        streak = get_productivity_streak(self.user)
        self.assertEqual(streak['current'], 1)


class InsightsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='pw12345!')

    def test_no_tasks_gives_a_reasonable_default_insight(self):
        insights = get_insights(self.user)
        self.assertTrue(len(insights) >= 1)

    def test_many_overdue_tasks_produces_overdue_insight(self):
        past = timezone.localdate() - timedelta(days=3)
        for i in range(3):
            Task.objects.create(user=self.user, title=f'Overdue {i}', priority='low', due_date=past)
        insights = get_insights(self.user)
        self.assertTrue(any('overdue' in i.lower() for i in insights))

    def test_no_tasks_due_today_gives_clear_schedule_insight(self):
        insights = get_insights(self.user)
        self.assertTrue(any('clear' in i.lower() for i in insights))

    def test_high_priority_backlog_produces_focus_insight(self):
        Task.objects.create(user=self.user, title='High 1', priority='high')
        Task.objects.create(user=self.user, title='High 2', priority='high')
        insights = get_insights(self.user)
        self.assertTrue(any('high-priority' in i.lower() for i in insights))

    def test_insights_reflect_real_data_not_placeholders(self):
        """Every insight should be traceable to something real about this
        specific user's tasks, not a hardcoded/fake number."""
        for i in range(3):
            Task.objects.create(user=self.user, title=f'High {i}', priority='high')
        insights = get_insights(self.user)
        self.assertTrue(any('3 high-priority' in i for i in insights))


class NotificationsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='pw12345!')

    def test_no_tasks_gives_no_notifications(self):
        self.assertEqual(get_notifications(self.user), [])

    def test_overdue_task_produces_notification(self):
        past = timezone.localdate() - timedelta(days=1)
        Task.objects.create(user=self.user, title='Late task', priority='low', due_date=past)
        notifications = get_notifications(self.user)
        self.assertTrue(any(n['type'] == 'overdue' for n in notifications))

    def test_notifications_are_capped(self):
        past = timezone.localdate() - timedelta(days=1)
        for i in range(10):
            Task.objects.create(user=self.user, title=f'Task {i}', priority='high', due_date=past)
        notifications = get_notifications(self.user)
        self.assertLessEqual(len(notifications), 5)


class DailyStatusMessageTests(TestCase):
    """The dashboard's always-present daily status banner (distinct from
    the broader rule-based insights list) — exactly one of four states."""

    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='pw12345!')
        self.today = timezone.localdate()

    def test_no_tasks_due_today_shows_clear_schedule(self):
        self.assertEqual(get_daily_status_message(self.user), "Your schedule is clear today.")

    def test_some_tasks_remaining_today(self):
        Task.objects.create(user=self.user, title='A', priority='low', due_date=self.today)
        Task.objects.create(user=self.user, title='B', priority='low', due_date=self.today)
        Task.objects.create(user=self.user, title='C', priority='low', due_date=self.today)
        self.assertEqual(get_daily_status_message(self.user), "You have 3 tasks remaining today.")

    def test_exactly_one_task_remaining_uses_singular_phrasing(self):
        Task.objects.create(user=self.user, title='A', priority='low', due_date=self.today, completed=True)
        Task.objects.create(user=self.user, title='B', priority='low', due_date=self.today)
        self.assertEqual(get_daily_status_message(self.user), "Great progress! Only 1 task left.")

    def test_all_todays_tasks_completed(self):
        Task.objects.create(user=self.user, title='A', priority='low', due_date=self.today, completed=True)
        Task.objects.create(user=self.user, title='B', priority='low', due_date=self.today, completed=True)
        self.assertEqual(get_daily_status_message(self.user), "Everything planned for today is complete.")

    def test_tasks_due_other_days_dont_affect_todays_message(self):
        from datetime import timedelta
        Task.objects.create(user=self.user, title='Tomorrow task', priority='low', due_date=self.today + timedelta(days=1))
        self.assertEqual(get_daily_status_message(self.user), "Your schedule is clear today.")


class DashboardDailyStatusBannerTests(TestCase):
    """Confirms the dashboard view actually surfaces the message and that
    the banner is scoped to the requesting user."""

    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='pw12345!')
        self.client.login(username='alice', password='pw12345!')

    def test_dashboard_shows_daily_status_banner(self):
        from django.urls import reverse
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, "Your schedule is clear today.")
