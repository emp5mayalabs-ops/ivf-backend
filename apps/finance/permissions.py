from rest_framework.permissions import BasePermission

class IsAdminOrBillingStaff(BasePermission):
    """
    Custom permission:
    - POST: Allowed for Admin (ADM), Pharmacy (PHA), Lab (TEC), Radiology (RAD)
    - GET/PUT/DELETE: Allowed only for Admin (ADM)
    """
    def has_permission(self, request, view):
        # If user is not authenticated, deny
        if not request.user or not request.user.is_authenticated:
            return False

        # For POST requests (creating bills), allow billing staff
        if request.method == 'POST':
            allowed_roles = ['ADM', 'PHA', 'TEC', 'AND', 'RAD']  # Add 'OPD' or others later
            return request.user.role in allowed_roles

        # For GET, PUT, DELETE (viewing/modifying data), ONLY Admins
        return request.user.role == 'ADM'