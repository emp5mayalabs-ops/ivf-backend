# embryology/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth import update_session_auth_hash
from django.utils import timezone
from .serializers import (
    EmbryologistLoginSerializer,
    EmbryologistProfileSerializer,
    EmbryologistProfileUpdateSerializer,
    ChangePasswordSerializer
)
from .permissions import IsEmbryologist
from accounts.models import User, LoginAuditLog
from accounts.views import get_client_ip, handle_role_change


# ============================================================
# 1. EMBRYOLOGIST LOGIN API
# ============================================================

class EmbryologistLoginView(APIView):
    """Embryologist Login API"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = EmbryologistLoginSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': 'Invalid input',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        user = serializer.validated_data['user']
        
        # Login the user
        login(request, user)
        
        # Create login audit log
        LoginAuditLog.objects.filter(
            user=user,
            is_active_session=True
        ).update(is_active_session=False, logout_time=timezone.now())
        
        LoginAuditLog.objects.create(
            user=user,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            is_active_session=True,
            last_seen=timezone.now()
        )
        
        # Get embryo profile - Use correct related_name
        profile = None
        if hasattr(user, 'embryology_profile'):  # ← CORRECTED related_name
            profile = user.embryology_profile     # ← CORRECTED related_name
        else:
            from .models import EmbryologistProfile
            profile = EmbryologistProfile.objects.create(user=user)
        
        # Safe attribute access using getattr
        return Response({
            'success': True,
            'message': 'Login successful',
            'data': {
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'full_name': user.full_name,
                    'role': user.role,
                    'role_display': 'Embryologist',
                    'has_changed_password': user.has_changed_password,
                    'is_active': user.is_active,
                },
                'profile': {
                    'employee_id': getattr(profile, 'employee_id', ''),
                    'contact_number': getattr(profile, 'contact_number', ''),
                    'specialization': getattr(profile, 'specialization', ''),
                    'is_department_head': getattr(profile, 'is_department_head', False),
                },
                'redirect_url': '/embryology/dashboard'
            }
        }, status=status.HTTP_200_OK)


# ============================================================
# 2. EMBRYOLOGIST LOGOUT API
# ============================================================

class EmbryologistLogoutView(APIView):
    """Embryologist Logout API"""
    permission_classes = [IsAuthenticated, IsEmbryologist]
    
    def post(self, request):
        # Update logout log
        LoginAuditLog.objects.filter(
            user=request.user,
            is_active_session=True
        ).update(
            is_active_session=False,
            logout_time=timezone.now()
        )
        
        logout(request)
        
        return Response({
            'success': True,
            'message': 'Logged out successfully'
        }, status=status.HTTP_200_OK)


# ============================================================
# 3. EMBRYOLOGIST PROFILE API
# ============================================================

class EmbryologistProfileView(APIView):
    """Get and Update Embryologist Profile"""
    permission_classes = [IsAuthenticated, IsEmbryologist]
    
    def get(self, request):
        """Get embryologist profile"""
        user = request.user
        
        # Get or create profile
        from .models import EmbryologistProfile
        profile, created = EmbryologistProfile.objects.get_or_create(user=user)
        
        # Role display
        role_display = {
            'EMB': 'Embryologist'
        }.get(user.role, 'Embryologist')
        
        # Department info
        departments = []
        if hasattr(user, 'staff_assignments'):
            for assignment in user.staff_assignments.filter(is_active=True).select_related('department'):
                departments.append({
                    'id': assignment.department.id,
                    'name': assignment.department.name,
                    'code': assignment.department.code,
                    'role': assignment.role_in_dept
                })
        
        return Response({
            'success': True,
            'data': {
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'full_name': user.full_name,
                    'role': user.role,
                    'role_display': role_display,
                    'is_active': user.is_active,
                    'date_joined': user.date_joined,
                    'has_changed_password': user.has_changed_password,
                },
                'profile': {
                    'id': profile.id,
                    'employee_id': getattr(profile, 'employee_id', ''),
                    'contact_number': getattr(profile, 'contact_number', ''),
                    'specialization': getattr(profile, 'specialization', ''),
                    'years_of_experience': getattr(profile, 'years_of_experience', 0),
                    'is_department_head': getattr(profile, 'is_department_head', False),
                    'can_perform_icsi': getattr(profile, 'can_perform_icsi', True),
                    'can_perform_biopsy': getattr(profile, 'can_perform_biopsy', True),
                    'can_perform_embryo_biopsy': getattr(profile, 'can_perform_embryo_biopsy', True),
                    'can_handle_cryo': getattr(profile, 'can_handle_cryo', True),
                },
                'departments': departments
            }
        })
    
    def put(self, request):
        """Update embryologist profile"""
        user = request.user
        from .models import EmbryologistProfile
        profile, created = EmbryologistProfile.objects.get_or_create(user=user)
        
        # Get data
        full_name = request.data.get('full_name')
        contact_number = request.data.get('contact_number')
        specialization = request.data.get('specialization')
        years_of_experience = request.data.get('years_of_experience')
        
        # Update user
        if full_name:
            user.full_name = full_name
            user.save()
        
        # Update profile using setattr for safety
        if contact_number is not None:
            profile.contact_number = contact_number
        if specialization is not None:
            profile.specialization = specialization
        if years_of_experience is not None:
            try:
                profile.years_of_experience = int(years_of_experience)
            except (ValueError, TypeError):
                pass  # Keep existing value if conversion fails
        
        profile.save()
        
        return Response({
            'success': True,
            'message': 'Profile updated successfully',
            'data': {
                'full_name': user.full_name,
                'contact_number': getattr(profile, 'contact_number', ''),
                'specialization': getattr(profile, 'specialization', ''),
                'years_of_experience': getattr(profile, 'years_of_experience', 0),
            }
        })


# ============================================================
# 4. EMBRYOLOGIST CHANGE PASSWORD API
# ============================================================

class EmbryologistChangePasswordView(APIView):
    """Change Embryologist Password"""
    permission_classes = [IsAuthenticated, IsEmbryologist]
    
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': 'Invalid input',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        user = request.user
        
        # Check old password
        if not user.check_password(serializer.validated_data['old_password']):
            return Response({
                'success': False,
                'message': 'Current password is incorrect'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Set new password
        user.set_password(serializer.validated_data['new_password'])
        user.has_changed_password = True
        user.save()
        
        # Keep user logged in
        update_session_auth_hash(request, user)
        
        return Response({
            'success': True,
            'message': 'Password changed successfully'
        }, status=status.HTTP_200_OK)


# ============================================================
# 5. EMBRYOLOGIST HEARTBEAT API (Keep session alive)
# ============================================================

class EmbryologistHeartbeatView(APIView):
    """Update last seen timestamp"""
    permission_classes = [IsAuthenticated, IsEmbryologist]
    
    def post(self, request):
        LoginAuditLog.objects.filter(
            user=request.user,
            is_active_session=True
        ).update(last_seen=timezone.now())
        
        return Response({
            'success': True,
            'message': 'Heartbeat updated'
        }, status=status.HTTP_200_OK)  