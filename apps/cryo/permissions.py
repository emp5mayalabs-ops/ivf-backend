# cryo/permissions.py

from rest_framework import permissions


class IsCryoStaff(permissions.BasePermission):
    """
    Allow access only to Cryo Staff (Embryologists & Andrologists)
    """
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['EMB', 'ANE']
    
    def has_object_permission(self, request, view, obj):
        return request.user.is_authenticated and request.user.role in ['EMB', 'ANE']