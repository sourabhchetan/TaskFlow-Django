"""Registration, login, logout, and access-control tests."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from tasks.models import Category, Profile


class RegistrationTests(TestCase):
    def test_register_creates_user_and_logs_in(self):
        response = self.client.post(reverse('register'), {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password1': 'Str0ngPassw0rd!',
            'password2': 'Str0ngPassw0rd!',
        })
        self.assertEqual(User.objects.filter(username='newuser').count(), 1)
        self.assertRedirects(response, reverse('dashboard'))

    def test_register_rejects_mismatched_passwords(self):
        response = self.client.post(reverse('register'), {
            'username': 'baduser',
            'email': 'bad@example.com',
            'password1': 'Str0ngPassw0rd!',
            'password2': 'DoesNotMatch!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='baduser').exists())

    def test_register_creates_profile_and_default_categories(self):
        self.client.post(reverse('register'), {
            'username': 'newuser2',
            'email': 'newuser2@example.com',
            'password1': 'Str0ngPassw0rd!',
            'password2': 'Str0ngPassw0rd!',
        })
        user = User.objects.get(username='newuser2')
        self.assertTrue(Profile.objects.filter(user=user).exists())
        self.assertEqual(Category.objects.filter(user=user).count(), len(Category.DEFAULT_NAMES_AND_COLORS))


class LoginTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='pw12345!')

    def test_login_success_redirects_to_dashboard(self):
        response = self.client.post(reverse('login'), {
            'username': 'alice', 'password': 'pw12345!',
        })
        self.assertRedirects(response, reverse('dashboard'))

    def test_login_failure_shows_form_again(self):
        response = self.client.post(reverse('login'), {
            'username': 'alice', 'password': 'wrong',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_logout(self):
        self.client.login(username='alice', password='pw12345!')
        response = self.client.post(reverse('logout'))
        self.assertRedirects(response, reverse('login'))


class AuthenticationRequiredTests(TestCase):
    """Every meaningful page must redirect an anonymous visitor to login."""

    def test_protected_pages_require_login(self):
        protected_urls = [
            reverse('dashboard'),
            reverse('task_create'),
            reverse('calendar'),
            reverse('analytics'),
            reverse('categories'),
            reverse('profile'),
            reverse('settings'),
        ]
        for url in protected_urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, msg=f'{url} did not redirect')
            self.assertIn(reverse('login'), response.url)
