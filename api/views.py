"""DRF viewsets for the To-Do List API.

Ownership is enforced twice, deliberately:
1. ``get_queryset`` never returns rows belonging to other users, so list/
   search results are already scoped.
2. ``IsOwner`` re-checks ownership on every single-object action (retrieve,
   update, partial_update, destroy, and the custom actions below), so even a
   guessed/enumerated ID that somehow bypassed the queryset can't be read or
   modified.
"""
from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from tasks.models import Category, Task
from tasks.services import create_next_occurrence

from .permissions import IsOwner
from .serializers import CategorySerializer, TaskSerializer

# Fields a client may sort by via ?ordering=. Prefixing with "-" reverses
# the order (e.g. ?ordering=-created_at). Deliberately a fixed allow-list —
# never pass the raw query param straight to .order_by().
TASK_ORDERING_FIELDS = {
    'due_date', '-due_date',
    'priority', '-priority',
    'created_at', '-created_at',
    'updated_at', '-updated_at',
    'title', '-title',
}


class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        return Category.objects.filter(user=self.request.user).order_by('name')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        qs = Task.objects.filter(user=self.request.user).select_related('category')

        completed = self.request.query_params.get('completed')
        if completed is not None:
            qs = qs.filter(completed=completed.lower() == 'true')

        priority = self.request.query_params.get('priority')
        if priority:
            qs = qs.filter(priority=priority)

        category = self.request.query_params.get('category')
        if category and category.isdigit():
            qs = qs.filter(category_id=int(category))

        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(title__icontains=search)
                | Q(description__icontains=search)
                | Q(category__name__icontains=search)
            )

        ordering = self.request.query_params.get('ordering')
        if ordering in TASK_ORDERING_FIELDS:
            qs = qs.order_by(ordering)

        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        task = self.get_object()
        task.completed = True
        task.completed_at = timezone.now()
        task.save(update_fields=['completed', 'completed_at', 'updated_at'])
        create_next_occurrence(task)
        return Response(self.get_serializer(task).data)

    @action(detail=True, methods=['post'])
    def pin(self, request, pk=None):
        task = self.get_object()
        task.pinned = not task.pinned
        task.save(update_fields=['pinned', 'updated_at'])
        return Response(self.get_serializer(task).data)
