from rest_framework.permissions import BasePermission

from .models import ProducerProfile


class IsProducerUser(BasePermission):
    """Allow access only to authenticated users that have a producer profile."""

    message = "Only producer accounts can access this endpoint."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return ProducerProfile.objects.filter(user=request.user).exists()
