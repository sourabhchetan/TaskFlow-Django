from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Task',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('category', models.CharField(choices=[('personal', 'Personal'), ('work', 'Work'), ('study', 'Study'), ('project', 'Project'), ('shopping', 'Shopping'), ('other', 'Other')], default='other', max_length=20)),
                ('priority', models.CharField(choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')], default='medium', max_length=10)),
                ('due_date', models.DateField(blank=True, null=True)),
                ('due_time', models.TimeField(blank=True, null=True)),
                ('completed', models.BooleanField(default=False)),
                ('pinned', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tasks', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-pinned', 'completed', 'due_date', 'due_time', '-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='task',
            index=models.Index(fields=['user', 'completed'], name='tasks_task_user_id_9f7f7c_idx'),
        ),
        migrations.AddIndex(
            model_name='task',
            index=models.Index(fields=['user', 'due_date'], name='tasks_task_user_id_5f1b2a_idx'),
        ),
    ]
