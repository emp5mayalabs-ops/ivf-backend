# apps/lab/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import login, logout
from django.utils import timezone

from .serializers import LabLoginSerializer
from accounts.models import LoginAuditLog


def get_client_ip(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


class LabLoginView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = LabLoginSerializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.validated_data['user']
            login(request, user)
            
            # Log login activity (optional)
            try:
                LoginAuditLog.objects.filter(
                    user=user,
                    is_active_session=True
                ).update(is_active_session=False, logout_time=timezone.now())
                
                LoginAuditLog.objects.create(
                    user=user,
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    is_active_session=True
                )
            except:
                pass
            
            return Response({
                'success': True,
                'user': {
                    'id': user.id,
                    'name': user.full_name,
                    'email': user.email,
                    'role': user.role,
                    'role_display': user.get_role_display()
                }
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LabLogoutView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        # Check lab role
        if request.user.role not in ['TEC', 'AND', 'EMB']:
            return Response({'error': 'Access denied'}, status=403)
        
        try:
            LoginAuditLog.objects.filter(
                user=request.user,
                is_active_session=True
            ).update(
                is_active_session=False,
                logout_time=timezone.now()
            )
        except:
            pass
        
        logout(request)
        return Response({'success': True, 'message': 'Logged out successfully'})