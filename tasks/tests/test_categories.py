"""Category CRUD and per-user isolation."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from tasks.models import Category, Task


class CategoryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='pw12345!')
        self.client.login(username='alice', password='pw12345!')

    def test_default_categories_exist(self):
        self.assertEqual(Category.objects.filter(user=self.user).count(), len(Category.DEFAULT_NAMES_AND_COLORS))

    def test_create_category(self):
        response = self.client.post(reverse('categories'), {'name': 'Fitness', 'color': '#22c55e'})
        self.assertRedirects(response, reverse('categories'))
        self.assertTrue(Category.objects.filter(user=self.user, name='Fitness').exists())

    def test_cannot_create_duplicate_category_name(self):
        response = self.client.post(reverse('categories'), {'name': 'Work', 'color': '#000000'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Category.objects.filter(user=self.user, name='Work').count(), 1)

    def test_rename_category(self):
        category = Category.objects.get(user=self.user, name='Personal')
        response = self.client.post(reverse('category_edit', args=[category.pk]), {
            'name': 'Life admin', 'color': category.color,
        })
        self.assertRedirects(response, reverse('categories'))
        category.refresh_from_db()
        self.assertEqual(category.name, 'Life admin')

    def test_delete_category_uncategorizes_tasks(self):
        category = Category.objects.get(user=self.user, name='Work')
        task = Task.objects.create(user=self.user, title='Some task', priority='low', category=category)
        self.client.post(reverse('category_delete', args=[category.pk]))
        task.refresh_from_db()
        self.assertIsNone(task.category)


class CategoryIsolationTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username='alice', password='pw12345!')
        self.bob = User.objects.create_user(username='bob', password='pw12345!')
        self.bobs_category = Category.objects.filter(user=self.bob).first()
        self.client.login(username='alice', password='pw12345!')

    def test_cannot_edit_other_users_category(self):
        response = self.client.post(reverse('category_edit', args=[self.bobs_category.pk]), {
            'name': 'Hacked', 'color': '#000000',
        })
        self.assertEqual(response.status_code, 404)

    def test_cannot_delete_other_users_category(self):
        response = self.client.post(reverse('category_delete', args=[self.bobs_category.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Category.objects.filter(pk=self.bobs_category.pk).exists())

    def test_categories_page_only_shows_own_categories(self):
        response = self.client.get(reverse('categories'))
        own_names = [c.name for c in Category.objects.filter(user=self.alice)]
        for name in own_names:
            self.assertContains(response, name)
