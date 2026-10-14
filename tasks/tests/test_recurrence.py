"""Recurring task generation: daily/weekly/monthly, custom interval, end
date cutoff, and duplicate prevention."""
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from tasks.models import Task
from tasks.services import add_recurrence, create_next_occurrence


class RecurrenceMathTests(TestCase):
    def test_daily(self):
        self.assertEqual(add_recurrence(date(2030, 1, 1), Task.Recurrence.DAILY), date(2030, 1, 2))

    def test_weekly(self):
        self.assertEqual(add_recurrence(date(2030, 1, 1), Task.Recurrence.WEEKLY), date(2030, 1, 8))

    def test_monthly_normal(self):
        self.assertEqual(add_recurrence(date(2030, 1, 15), Task.Recurrence.MONTHLY), date(2030, 2, 15))

    def test_monthly_clamps_to_shorter_month(self):
        # Jan 31 -> Feb has no 31st, should clamp to Feb 28 (2030 not a leap year)
        self.assertEqual(add_recurrence(date(2030, 1, 31), Task.Recurrence.MONTHLY), date(2030, 2, 28))

    def test_monthly_rolls_over_year(self):
        self.assertEqual(add_recurrence(date(2030, 12, 10), Task.Recurrence.MONTHLY), date(2031, 1, 10))

    def test_custom_interval(self):
        self.assertEqual(add_recurrence(date(2030, 1, 1), Task.Recurrence.CUSTOM, interval=5), date(2030, 1, 6))


class CreateNextOccurrenceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='pw12345!')

    def test_non_recurring_task_produces_nothing(self):
        task = Task.objects.create(user=self.user, title='One-off', priority='low', due_date=date(2030, 1, 1))
        self.assertIsNone(create_next_occurrence(task))

    def test_daily_recurrence_creates_next_task(self):
        task = Task.objects.create(
            user=self.user, title='Standup', priority='low', due_date=date(2030, 1, 1),
            is_recurring=True, recurrence_type=Task.Recurrence.DAILY,
        )
        new_task = create_next_occurrence(task)
        self.assertIsNotNone(new_task)
        self.assertEqual(new_task.due_date, date(2030, 1, 2))
        self.assertEqual(new_task.parent_task, task)
        self.assertFalse(new_task.completed)

    def test_recurrence_end_date_stops_generation(self):
        task = Task.objects.create(
            user=self.user, title='Ends soon', priority='low', due_date=date(2030, 1, 1),
            is_recurring=True, recurrence_type=Task.Recurrence.DAILY,
            recurrence_end_date=date(2030, 1, 1),
        )
        self.assertIsNone(create_next_occurrence(task))

    def test_duplicate_occurrence_is_not_created_twice(self):
        task = Task.objects.create(
            user=self.user, title='Weekly review', priority='low', due_date=date(2030, 1, 1),
            is_recurring=True, recurrence_type=Task.Recurrence.WEEKLY,
        )
        first = create_next_occurrence(task)
        self.assertIsNotNone(first)
        # Calling again from the same source task should refuse to create a
        # second occurrence for the same computed date.
        second = create_next_occurrence(task)
        self.assertIsNone(second)
        self.assertEqual(
            Task.objects.filter(user=self.user, parent_task=task, due_date=date(2030, 1, 8)).count(), 1
        )

    def test_monthly_recurrence_chain_shares_root_parent(self):
        root = Task.objects.create(
            user=self.user, title='Monthly report', priority='low', due_date=date(2030, 1, 31),
            is_recurring=True, recurrence_type=Task.Recurrence.MONTHLY,
        )
        occurrence_1 = create_next_occurrence(root)
        occurrence_2 = create_next_occurrence(occurrence_1)
        self.assertEqual(occurrence_1.parent_task, root)
        self.assertEqual(occurrence_2.parent_task, root)


class RecurrenceViewIntegrationTests(TestCase):
    """Completing a recurring task through the normal view flow should
    transparently create the next occurrence."""

    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='pw12345!')
        self.client.login(username='alice', password='pw12345!')

    def test_completing_task_via_view_creates_next_occurrence(self):
        task = Task.objects.create(
            user=self.user, title='Daily journal', priority='low', due_date=date(2030, 1, 1),
            is_recurring=True, recurrence_type=Task.Recurrence.DAILY,
        )
        self.client.post(reverse('task_toggle', args=[task.pk]))
        self.assertTrue(
            Task.objects.filter(user=self.user, parent_task=task, due_date=date(2030, 1, 2)).exists()
        )

    def test_task_form_creates_recurring_task(self):
        response = self.client.post(reverse('task_create'), {
            'title': 'New recurring task',
            'priority': 'low',
            'does_repeat': 'weekly',
            'recurrence_interval': 1,
            'reminder_offset': 'none',
        })
        self.assertRedirects(response, reverse('dashboard'))
        task = Task.objects.get(title='New recurring task')
        self.assertTrue(task.is_recurring)
        self.assertEqual(task.recurrence_type, Task.Recurrence.WEEKLY)
