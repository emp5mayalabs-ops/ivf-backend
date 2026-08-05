# embryology/permissions.py

from rest_framework import permissions

class IsEmbryologist(permissions.BasePermission):
    """Allow only Embryologist users"""
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'EMB'
    
    def has_object_permission(self, request, view, obj):
        return request.user.is_authenticated and request.user.role == 'EMB'