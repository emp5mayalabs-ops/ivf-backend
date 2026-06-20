# apps/pharmacy/permissions.py
from rest_framework.permissions import BasePermission

class IsPharmacist(BasePermission):
    """
    Custom permission to only allow pharmacists (role='PHA') to access pharmacy views.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'PHA'
    
    def has_object_permission(self, request, view, obj):
        return request.user.is_authenticated and request.user.role == 'PHA'


class IsPharmacistOrReadOnly(BasePermission):
    """
    Custom permission to allow pharmacists full access, others read-only.
    """
    def has_permission(self, request, view):
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return request.user.is_authenticated
        return request.user.is_authenticated and request.user.role == 'PHA'
    
    def has_object_permission(self, request, view, obj):
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True
        return request.user.role == 'PHA'