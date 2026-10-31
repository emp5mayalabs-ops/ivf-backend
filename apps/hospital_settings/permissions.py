# apps/hospital_settings/permissions.py

from rest_framework.permissions import BasePermission

class IsAdminUser(BasePermission):
    """Custom permission to only allow admin users"""
    
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.role == 'ADM'
        )

class IsAdminOrReadOnly(BasePermission):
    """Allow read-only access to all, but only admin can modify"""
    
    def has_permission(self, request, view):
        # Allow GET, HEAD, OPTIONS requests
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True
        
        # For other methods, require admin role
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.role == 'ADM'
        )