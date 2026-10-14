"""Django Admin configuration for the tasks app."""
from django.contrib import admin

from .models import ActivityLog, Category, Profile, Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'user', 'category', 'priority',
        'due_date', 'due_time', 'completed', 'pinned', 'is_recurring', 'created_at',
    )
    list_filter = ('priority', 'completed', 'pinned', 'is_recurring', 'category')
    search_fields = ('title', 'description', 'user__username', 'user__email')
    ordering = ('-created_at',)
    date_hierarchy = 'due_date'
    list_select_related = ('user', 'category')
    readonly_fields = ('created_at', 'updated_at', 'completed_at')
    fieldsets = (
        (None, {'fields': ('user', 'title', 'description', 'attachment')}),
        ('Classification', {'fields': ('category', 'priority')}),
        ('Scheduling', {'fields': ('due_date', 'due_time', 'reminder_offset')}),
        ('Recurrence', {'fields': ('is_recurring', 'recurrence_type', 'recurrence_interval', 'recurrence_end_date', 'parent_task')}),
        ('Status', {'fields': ('completed', 'pinned', 'completed_at')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'color', 'created_at')
    search_fields = ('name', 'user__username')
    list_filter = ('color',)
    ordering = ('user', 'name')


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'theme_preference', 'default_view', 'default_sort', 'reminders_enabled')
    search_fields = ('user__username',)
    list_filter = ('theme_preference', 'default_view', 'reminders_enabled')


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('description', 'user', 'action', 'task', 'created_at')
    list_filter = ('action',)
    search_fields = ('description', 'user__username', 'task__title')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    list_select_related = ('user', 'task')
    readonly_fields = ('created_at',)
