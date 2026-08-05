from rest_framework.permissions import BasePermission

class IsAndrologist(BasePermission):
    """
    Allows access only to users with role 'AND' (Andrologist).
    """
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role == 'AND'
        )