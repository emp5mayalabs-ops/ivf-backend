from rest_framework.permissions import IsAuthenticated

class ReceptionistPermission(IsAuthenticated):
	def has_permission(self, request, view):
		if not super().has_permission(request, view):
			return False
		return request.user.role in ['REC','ADM']

