from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import migrations, models
import django.db.models.deletion
import tasks.models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('tasks', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50)),
                ('color', models.CharField(default='#6366f1', help_text='Hex color, e.g. #6366f1', max_length=7)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='categories', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['name']},
        ),
        migrations.CreateModel(
            name='Profile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('theme_preference', models.CharField(choices=[('light', 'Light'), ('dark', 'Dark'), ('system', 'System')], default='system', max_length=10)),
                ('default_priority', models.CharField(default='medium', max_length=10)),
                ('default_view', models.CharField(choices=[('all', 'All tasks'), ('today', 'Today'), ('upcoming', 'Upcoming')], default='all', max_length=10)),
                ('default_sort', models.CharField(default='due_date', max_length=10)),
                ('reminders_enabled', models.BooleanField(default=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='profile', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name='category',
            constraint=models.UniqueConstraint(fields=('user', 'name'), name='unique_category_name_per_user'),
        ),
        migrations.RemoveField(
            model_name='task',
            name='category',
        ),
        migrations.AddField(
            model_name='task',
            name='category',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tasks', to='tasks.category'),
        ),
        migrations.AddField(
            model_name='task',
            name='is_recurring',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='task',
            name='recurrence_type',
            field=models.CharField(choices=[('none', 'Never'), ('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly'), ('custom', 'Custom')], default='none', max_length=10),
        ),
        migrations.AddField(
            model_name='task',
            name='recurrence_interval',
            field=models.PositiveSmallIntegerField(default=1, help_text='Used with "Custom": repeat every N days.'),
        ),
        migrations.AddField(
            model_name='task',
            name='recurrence_end_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='task',
            name='parent_task',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='occurrences', to='tasks.task'),
        ),
        migrations.AddField(
            model_name='task',
            name='reminder_offset',
            field=models.CharField(choices=[('none', 'No reminder'), ('10min', '10 minutes before'), ('30min', '30 minutes before'), ('1hour', '1 hour before'), ('1day', '1 day before')], default='none', max_length=10),
        ),
        migrations.AddField(
            model_name='task',
            name='attachment',
            field=models.FileField(blank=True, null=True, upload_to=tasks.models.attachment_upload_path, validators=[FileExtensionValidator(tasks.models.ALLOWED_ATTACHMENT_EXTENSIONS), tasks.models.validate_attachment_size]),
        ),
    ]
