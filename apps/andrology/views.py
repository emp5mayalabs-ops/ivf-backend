from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import login, logout
from django.contrib.auth import update_session_auth_hash
from django.utils import timezone

from .serializers import (
    AndrologistLoginSerializer,
    ChangePasswordSerializer,
)
from .permissions import IsAndrologist

from accounts.models import LoginAuditLog
from accounts.views import get_client_ip
from lab.models import AndrologyLabTechnician


# ============================================================
# 1. ANDROLOGIST LOGIN
# ============================================================

class AndrologistLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AndrologistLoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': 'Invalid input',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.validated_data['user']
        login(request, user)

        # Invalidate previous active sessions
        LoginAuditLog.objects.filter(
            user=user,
            is_active_session=True
        ).update(is_active_session=False, logout_time=timezone.now())

        # Create new login audit log
        LoginAuditLog.objects.create(
            user=user,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            is_active_session=True,
            last_seen=timezone.now()
        )

        # Get or create the Andrology profile
        profile = None
        if hasattr(user, 'andrology_technician_profile'):
            profile = user.andrology_technician_profile
        else:
            profile = AndrologyLabTechnician.objects.create(user=user)

        return Response({
            'success': True,
            'message': 'Login successful',
            'data': {
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'full_name': user.full_name,
                    'role': user.role,
                    'role_display': 'Andrologist',
                    'has_changed_password': user.has_changed_password,
                    'is_active': user.is_active,
                },
                'profile': {
                    'employee_id': getattr(profile, 'employee_id', ''),
                    'contact_number': getattr(profile, 'contact_number', ''),
                    'specialization': getattr(profile, 'specialization', ''),
                    'is_department_head': getattr(profile, 'is_department_head', False),
                    'can_perform_dna_frag': getattr(profile, 'can_perform_dna_frag', False),
                    'can_perform_cryo': getattr(profile, 'can_perform_cryo', False),
                },
                'redirect_url': '/andrology/dashboard'   # adjust to your frontend route
            }
        }, status=status.HTTP_200_OK)


# ============================================================
# 2. ANDROLOGIST LOGOUT
# ============================================================

class AndrologistLogoutView(APIView):
    permission_classes = [IsAuthenticated, IsAndrologist]

    def post(self, request):
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
# 3. PROFILE (GET & UPDATE)
# ============================================================

class AndrologistProfileView(APIView):
    permission_classes = [IsAuthenticated, IsAndrologist]

    def get(self, request):
        user = request.user
        profile, created = AndrologyLabTechnician.objects.get_or_create(user=user)

        # Optional department assignments (if you have them)
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
                    'role_display': 'Andrologist',
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
                    'can_perform_dna_frag': getattr(profile, 'can_perform_dna_frag', True),
                    'can_perform_cryo': getattr(profile, 'can_perform_cryo', True),
                },
                'departments': departments
            }
        })

    def put(self, request):
        user = request.user
        profile, created = AndrologyLabTechnician.objects.get_or_create(user=user)

        # Update user fields
        full_name = request.data.get('full_name')
        if full_name:
            user.full_name = full_name
            user.save()

        # Update profile fields
        contact_number = request.data.get('contact_number')
        specialization = request.data.get('specialization')
        years_of_experience = request.data.get('years_of_experience')

        if contact_number is not None:
            profile.contact_number = contact_number
        if specialization is not None:
            profile.specialization = specialization
        if years_of_experience is not None:
            try:
                profile.years_of_experience = int(years_of_experience)
            except (ValueError, TypeError):
                pass

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
# 4. CHANGE PASSWORD
# ============================================================

class AndrologistChangePasswordView(APIView):
    permission_classes = [IsAuthenticated, IsAndrologist]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': 'Invalid input',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        if not user.check_password(serializer.validated_data['old_password']):
            return Response({
                'success': False,
                'message': 'Current password is incorrect'
            }, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(serializer.validated_data['new_password'])
        user.has_changed_password = True
        user.save()
        update_session_auth_hash(request, user)   # keep user logged in

        return Response({
            'success': True,
            'message': 'Password changed successfully'
        }, status=status.HTTP_200_OK)


# ============================================================
# 5. HEARTBEAT (keep session alive)
# ============================================================

class AndrologistHeartbeatView(APIView):
    permission_classes = [IsAuthenticated, IsAndrologist]

    def post(self, request):
        LoginAuditLog.objects.filter(
            user=request.user,
            is_active_session=True
        ).update(last_seen=timezone.now())
        return Response({
            'success': True,
            'message': 'Heartbeat updated'
        }, status=status.HTTP_200_OK)