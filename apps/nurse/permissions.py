# apps/nurse/permissions.py
from rest_framework import permissions


class IsNurse(permissions.BasePermission):
    """
    Custom permission to only allow nurses to access
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'NUR'
    
    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'user'):
            return obj.user == request.user
        if hasattr(obj, 'nurse'):
            return obj.nurse.user == request.user
        return False


class IsHeadNurse(permissions.BasePermission):
    """
    Custom permission to only allow head nurses
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        try:
            profile = request.user.nurse_profile
            return profile.is_head_nurse or profile.is_department_head
        except:
            return False
    
    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False
        try:
            profile = request.user.nurse_profile
            return profile.is_head_nurse or profile.is_department_head
        except:
            return False


class IsNurseOrAdmin(permissions.BasePermission):
    """
    Custom permission to allow nurses and admin users
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.is_staff or request.user.is_superuser:
            return True
        return request.user.role == 'NUR'