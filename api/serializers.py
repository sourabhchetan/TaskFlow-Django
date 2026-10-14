"""DRF serializers for the To-Do List API."""
from rest_framework import serializers

from tasks.models import Category, Task


class CategorySerializer(serializers.ModelSerializer):
    task_count = serializers.IntegerField(source='tasks.count', read_only=True)

    class Meta:
        model = Category
        fields = ['id', 'name', 'color', 'created_at', 'task_count']
        read_only_fields = ['id', 'created_at', 'task_count']


class TaskSerializer(serializers.ModelSerializer):
    """The user is never accepted from the client — it's always taken from
    the authenticated request (see TaskViewSet.perform_create), so a user
    can never create a task on someone else's behalf.

    Category is validated against the requesting user's own categories only,
    so a task can't be tagged with another user's category.
    """
    category_name = serializers.CharField(source='category.name', read_only=True, default=None)
    priority_label = serializers.CharField(source='get_priority_display', read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    countdown_text = serializers.CharField(read_only=True)

    class Meta:
        model = Task
        fields = [
            'id', 'title', 'description', 'category', 'category_name',
            'priority', 'priority_label', 'due_date', 'due_time',
            'completed', 'pinned', 'created_at', 'updated_at', 'completed_at',
            'is_recurring', 'recurrence_type', 'recurrence_interval', 'recurrence_end_date',
            'reminder_offset', 'is_overdue', 'countdown_text',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'completed_at']

    def validate_category(self, category):
        request = self.context.get('request')
        if category is not None and request and category.user_id != request.user.id:
            raise serializers.ValidationError("You can only assign your own categories.")
        return category
