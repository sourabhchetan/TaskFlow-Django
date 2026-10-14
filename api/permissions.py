"""Object-level permission enforcing per-user ownership on API objects.

This is the API's equivalent of the ``get_object_or_404(..., user=request.user)``
pattern used throughout tasks/views.py: it guarantees a user can never
retrieve, update, or delete another user's task or category by manually
changing the ``id`` in the URL, even though the queryset-level filtering in
the viewsets already narrows results to the requesting user.
"""
from rest_framework import permissions


class IsOwner(permissions.BasePermission):
    message = "You do not have permission to access this object."

    def has_object_permission(self, request, view, obj):
        return getattr(obj, 'user_id', None) == request.user.id
