# apps/accounts/permissions.py - Add this class

from rest_framework.permissions import IsAuthenticated

class ReceptionistPermission(IsAuthenticated):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return request.user.role in ['REC', 'ADM']


# ✅ ADD THIS NEW PERMISSION CLASS
class DoctorPermission(IsAuthenticated):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return request.user.role in ['END', 'GYN', 'ANE', 'ADM']