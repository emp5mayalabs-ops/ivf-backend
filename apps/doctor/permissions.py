# apps/doctor/permissions.py
from rest_framework.permissions import BasePermission

class IsDoctor(BasePermission):
    """Allow access only to doctors (END, GYN, ANE)"""
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['END', 'GYN', 'ANE']


class IsEndocrinologist(BasePermission):
    """Allow access only to Reproductive Endocrinologists (END)"""
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'END'


class IsGynaecologist(BasePermission):
    """Allow access only to Gynaecologists (GYN)"""
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'GYN'


class IsAndrologist(BasePermission):
    """Allow access only to Andrologists (ANE)"""
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'ANE'