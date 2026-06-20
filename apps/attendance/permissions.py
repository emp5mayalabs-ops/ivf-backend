# apps/attendance/permissions.py

from rest_framework import permissions


class IsHRM(permissions.BasePermission):
    """Only HRM and ADM can access admin features"""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.user.role in ['HRM', 'ADM']  # ✅ Added 'ADM'


class IsStaff(permissions.BasePermission):
    """All staff can access (excluding patients and donors)"""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.user.role not in ['PAT', 'DON']


class IsSelfOrHRM(permissions.BasePermission):
    """Allow access if user is HRM/ADM or the object belongs to the user"""
    def has_object_permission(self, request, view, obj):
        if request.user.role in ['HRM', 'ADM']:  # ✅ Added 'ADM'
            return True
        return obj.user == request.user


class CanMarkAttendance(permissions.BasePermission):
    """Can mark attendance (all staff except patients/donors)"""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.user.role not in ['PAT', 'DON']