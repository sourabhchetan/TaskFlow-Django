"""Signal handlers: keep every User in sync with a Profile and a starter
set of Categories, so views never have to special-case a "new" user."""
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Category, Profile


@receiver(post_save, sender=User)
def create_profile_and_default_categories(sender, instance, created, **kwargs):
    if not created:
        return
    Profile.objects.get_or_create(user=instance)
    for name, color in Category.DEFAULT_NAMES_AND_COLORS:
        Category.objects.get_or_create(user=instance, name=name, defaults={'color': color})
