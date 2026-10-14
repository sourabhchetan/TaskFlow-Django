"""Data migration: ensure every pre-existing user (created before Profile/
Category existed) gets a Profile and the default category set too. New
users get these automatically via tasks.signals, so this only matters when
upgrading a database that already had users before this migration ran."""
from django.db import migrations


DEFAULT_NAMES_AND_COLORS = [
    ('Personal', '#6366f1'),
    ('Work', '#0ea5e9'),
    ('Study', '#a855f7'),
    ('Project', '#f59e0b'),
    ('Shopping', '#10b981'),
    ('Other', '#64748b'),
]


def backfill(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    Profile = apps.get_model('tasks', 'Profile')
    Category = apps.get_model('tasks', 'Category')

    for user in User.objects.all():
        Profile.objects.get_or_create(user=user)
        for name, color in DEFAULT_NAMES_AND_COLORS:
            Category.objects.get_or_create(user=user, name=name, defaults={'color': color})


def noop_reverse(apps, schema_editor):
    # Intentionally not destructive: reversing this migration should not
    # delete categories/profiles a user may already be relying on.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0002_categories_recurrence_profile'),
    ]

    operations = [
        migrations.RunPython(backfill, noop_reverse),
    ]
