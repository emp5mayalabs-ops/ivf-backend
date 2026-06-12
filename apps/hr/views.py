from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import login
from django.utils import timezone
from django.db.models import Q, Count
from datetime import timedelta

from .models import HRManagerProfile, LeaveRequest
from .serializers import (
    HRLoginSerializer, HRProfileSerializer, 
    StaffListSerializer, LeaveRequestSerializer
)
from accounts.models import User


class HRLoginView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        ser = HRLoginSerializer(data=request.data)
        if ser.is_valid():
            user = ser.validated_data['user']
            login(request, user)
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
        return Response(ser.errors, status=400)


class HRDashboardView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        if request.user.role != 'HRM':
            return Response({'error': 'Access denied'}, status=403)
        
        all_staff = User.objects.exclude(role__in=['PAT', 'DON'])
        
        return Response({
            'success': True,
            'stats': {
                'total_staff': all_staff.count(),
                'active_staff': all_staff.filter(is_active=True).count(),
                'pending_leaves': LeaveRequest.objects.filter(status='PENDING').count(),
            }
        })


class StaffManagementView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        if request.user.role != 'HRM':
            return Response({'error': 'Access denied'}, status=403)
        
        staff = User.objects.exclude(role__in=['PAT', 'DON']).order_by('-date_joined')
        ser = StaffListSerializer(staff, many=True)
        return Response({'success': True, 'staff': ser.data})
    
    def post(self, request):
        if request.user.role != 'HRM':
            return Response({'error': 'Access denied'}, status=403)
        
        staff_id = request.data.get('staff_id')
        action = request.data.get('action')
        
        try:
            staff = User.objects.get(id=staff_id)
        except User.DoesNotExist:
            return Response({'error': 'Staff not found'}, status=404)
        
        if staff == request.user:
            return Response({'error': 'Cannot change yourself'}, status=400)
        
        if action == 'deactivate':
            staff.is_active = False
            message = f'{staff.full_name} deactivated'
        elif action == 'activate':
            staff.is_active = True
            message = f'{staff.full_name} activated'
        else:
            return Response({'error': 'Invalid action. Use "activate" or "deactivate"'}, status=400)
        
        staff.save()
        return Response({'success': True, 'message': message})


class LeaveManagementView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        if request.user.role != 'HRM':
            return Response({'error': 'Access denied'}, status=403)
        
        leaves = LeaveRequest.objects.filter(status='PENDING').order_by('-created_at')
        ser = LeaveRequestSerializer(leaves, many=True)
        return Response({'success': True, 'leaves': ser.data})
    
    def post(self, request, leave_id):
        if request.user.role != 'HRM':
            return Response({'error': 'Access denied'}, status=403)
        
        try:
            leave = LeaveRequest.objects.get(id=leave_id)
        except LeaveRequest.DoesNotExist:
            return Response({'error': 'Leave not found'}, status=404)
        
        status_val = request.data.get('status')
        rejection_reason = request.data.get('rejection_reason', '')
        
        if status_val not in ['APPROVED', 'REJECTED']:
            return Response({'error': 'Invalid status. Use "APPROVED" or "REJECTED"'}, status=400)
        
        leave.status = status_val
        leave.approved_by = request.user
        leave.approved_at = timezone.now()
        
        if status_val == 'REJECTED':
            leave.rejection_reason = rejection_reason
        
        leave.save()
        
        return Response({'success': True, 'message': f'Leave {status_val.lower()} successfully'})

class HRProfileView(APIView):
    """Get, update HR profile, and change password"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get HR profile details"""
        if request.user.role != 'HRM':
            return Response({'error': 'Access denied'}, status=403)
        
        try:
            profile = HRManagerProfile.objects.get(user=request.user)
        except HRManagerProfile.DoesNotExist:
            return Response({'error': 'Profile not found'}, status=404)
        
        # Get department assignments
        from departments.models import StaffDepartmentAssignment
        
        primary_dept = StaffDepartmentAssignment.objects.filter(
            user=request.user,
            role_in_dept='PRIMARY',
            is_active=True
        ).select_related('department').first()
        
        secondary_depts = StaffDepartmentAssignment.objects.filter(
            user=request.user,
            role_in_dept='SECONDARY',
            is_active=True
        ).select_related('department')
        
        # Calculate statistics
        total_leaves_taken = LeaveRequest.objects.filter(
            employee=request.user,
            status='APPROVED'
        ).count()
        
        ser = HRProfileSerializer(profile)
        
        response_data = {
            'success': True,
            'profile': {
                **ser.data,
                'primary_department': {
                    'id': primary_dept.department.id if primary_dept else None,
                    'name': primary_dept.department.name if primary_dept else None,
                    'code': primary_dept.department.code if primary_dept else None
                } if primary_dept else None,
                'secondary_departments': [
                    {
                        'id': dept.department.id,
                        'name': dept.department.name,
                        'code': dept.department.code
                    } for dept in secondary_depts
                ] if secondary_depts else [],
                'statistics': {
                    'total_leaves_taken': total_leaves_taken,
                    'pending_leaves': LeaveRequest.objects.filter(
                        employee=request.user,
                        status='PENDING'
                    ).count()
                }
            }
        }
        
        return Response(response_data)
    
    def put(self, request):
        """Update HR profile"""
        if request.user.role != 'HRM':
            return Response({'error': 'Access denied'}, status=403)
        
        try:
            profile = HRManagerProfile.objects.get(user=request.user)
        except HRManagerProfile.DoesNotExist:
            return Response({'error': 'Profile not found'}, status=404)
        
        # Get data from request
        full_name = request.data.get('full_name')
        contact_number = request.data.get('contact_number')
        managed_depts = request.data.get('managed_depts')
        
        # Update user full name
        if full_name:
            request.user.full_name = full_name
            request.user.save()
        
        # Update profile fields
        if contact_number is not None:
            profile.contact_number = contact_number
        if managed_depts is not None:
            profile.managed_depts = managed_depts
        
        profile.save()
        
        # Return updated profile
        ser = HRProfileSerializer(profile)
        
        return Response({
            'success': True,
            'message': 'Profile updated successfully',
            'profile': {
                'id': profile.id,
                'employee_id': profile.employee_id,
                'full_name': request.user.full_name,
                'email': request.user.email,
                'contact_number': profile.contact_number,
                'managed_depts': profile.managed_depts,
                'can_approve_leaves': profile.can_approve_leaves,
                'can_view_salaries': profile.can_view_salaries,
                'can_terminate_staff': profile.can_terminate_staff,
                'can_edit_attendance': profile.can_edit_attendance,
                'can_generate_payslips': profile.can_generate_payslips,
                'can_update_documents': profile.can_update_documents,
                'is_department_head': profile.is_department_head,
                'is_active': profile.is_active,
                'date_assigned': profile.date_assigned
            }
        })


class HRChangePasswordView(APIView):
    """Change HR password"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Change password"""
        if request.user.role != 'HRM':
            return Response({'error': 'Access denied'}, status=403)
        
        # Get data from request
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')
        confirm_password = request.data.get('confirm_password')
        
        # Validate required fields
        if not old_password:
            return Response({'error': 'Current password is required'}, status=400)
        if not new_password:
            return Response({'error': 'New password is required'}, status=400)
        if not confirm_password:
            return Response({'error': 'Please confirm your new password'}, status=400)
        
        # Check if new passwords match
        if new_password != confirm_password:
            return Response({'error': 'New passwords do not match'}, status=400)
        
        # Check password length
        if len(new_password) < 6:
            return Response({'error': 'Password must be at least 6 characters'}, status=400)
        
        # Verify old password
        if not request.user.check_password(old_password):
            return Response({'error': 'Current password is incorrect'}, status=400)
        
        # Set new password
        request.user.set_password(new_password)
        request.user.save()
        
        # Update session to prevent logout
        from django.contrib.auth import update_session_auth_hash
        update_session_auth_hash(request, request.user)
        
        return Response({
            'success': True,
            'message': 'Password changed successfully'
        })


# ========== ADD THESE NEW VIEWS ==========

class HRLeaveStatisticsView(APIView):
    """Get leave statistics with date filters (daily, weekly, monthly, custom)"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        if request.user.role != 'HRM':
            return Response({'error': 'Access denied'}, status=403)
        
        # Get filter parameters
        range_type = request.query_params.get('range', 'daily')
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        
        today = timezone.now().date()
        
        # Calculate date range based on filter
        if range_type == 'daily':
            start_date = today
            end_date = today
            range_label = "Today"
            
        elif range_type == 'weekly':
            start_date = today - timedelta(days=today.weekday())
            end_date = start_date + timedelta(days=6)
            range_label = f"This Week ({start_date.strftime('%d %b')} - {end_date.strftime('%d %b')})"
            
        elif range_type == 'monthly':
            start_date = today.replace(day=1)
            if today.month == 12:
                end_date = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end_date = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
            range_label = f"This Month ({start_date.strftime('%b %Y')})"
            
        elif range_type == 'custom' and start_date_str and end_date_str:
            try:
                start_date = timezone.datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = timezone.datetime.strptime(end_date_str, '%Y-%m-%d').date()
                range_label = f"{start_date.strftime('%d %b %Y')} - {end_date.strftime('%d %b %Y')}"
            except ValueError:
                return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)
        else:
            start_date = today
            end_date = today
            range_label = "Today"
        
        # Query leaves within date range
        leaves = LeaveRequest.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
        
        # Statistics by status
        total_leaves = leaves.count()
        pending_leaves = leaves.filter(status='PENDING').count()
        approved_leaves = leaves.filter(status='APPROVED').count()
        rejected_leaves = leaves.filter(status='REJECTED').count()
        cancelled_leaves = leaves.filter(status='CANCELLED').count()
        
        # Get all employees for total staff count
        all_staff = User.objects.exclude(role__in=['PAT', 'DON'])
        total_staff = all_staff.count()
        
        # Staff on leave during this period
        staff_on_leave = leaves.exclude(status__in=['REJECTED', 'CANCELLED']).values('employee').distinct().count()
        
        # Leave by type
        leave_by_type = {}
        for leave_type, display in LeaveRequest.LEAVE_TYPES:
            count = leaves.filter(leave_type=leave_type).count()
            if count > 0:
                leave_by_type[leave_type] = {
                    'name': display,
                    'count': count,
                    'percentage': round((count / total_leaves) * 100, 1) if total_leaves > 0 else 0
                }
        
        # Daily breakdown
        daily_breakdown = []
        current = start_date
        while current <= end_date:
            day_leaves = leaves.filter(created_at__date=current)
            daily_breakdown.append({
                'date': current.strftime('%Y-%m-%d'),
                'day_name': current.strftime('%A'),
                'total': day_leaves.count(),
                'pending': day_leaves.filter(status='PENDING').count(),
                'approved': day_leaves.filter(status='APPROVED').count(),
                'rejected': day_leaves.filter(status='REJECTED').count()
            })
            current += timedelta(days=1)
        
        return Response({
            'success': True,
            'date_range': {
                'type': range_type,
                'label': range_label,
                'start_date': str(start_date),
                'end_date': str(end_date),
                'total_days': (end_date - start_date).days + 1
            },
            'statistics': {
                'total_leaves': total_leaves,
                'pending_leaves': pending_leaves,
                'approved_leaves': approved_leaves,
                'rejected_leaves': rejected_leaves,
                'cancelled_leaves': cancelled_leaves,
                'total_staff': total_staff,
                'staff_on_leave': staff_on_leave,
                'pending_percentage': round((pending_leaves / total_leaves) * 100, 1) if total_leaves > 0 else 0,
                'approved_percentage': round((approved_leaves / total_leaves) * 100, 1) if total_leaves > 0 else 0,
                'rejected_percentage': round((rejected_leaves / total_leaves) * 100, 1) if total_leaves > 0 else 0
            },
            'leave_by_type': leave_by_type,
            'daily_breakdown': daily_breakdown
        })


class HRLeaveTrendView(APIView):
    """Get leave trend data for charts (last 7 days, 4 weeks, 12 months)"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        if request.user.role != 'HRM':
            return Response({'error': 'Access denied'}, status=403)
        
        trend_type = request.query_params.get('trend', 'weekly')  # weekly, monthly
        
        today = timezone.now().date()
        
        if trend_type == 'weekly':
            # Last 7 days
            data = []
            for i in range(6, -1, -1):
                date = today - timedelta(days=i)
                leaves = LeaveRequest.objects.filter(created_at__date=date)
                data.append({
                    'date': date.strftime('%d %b'),
                    'day': date.strftime('%A'),
                    'total': leaves.count(),
                    'pending': leaves.filter(status='PENDING').count(),
                    'approved': leaves.filter(status='APPROVED').count(),
                    'rejected': leaves.filter(status='REJECTED').count()
                })
        else:
            # Last 12 months
            data = []
            for i in range(11, -1, -1):
                month_date = today - timedelta(days=30 * i)
                month_start = month_date.replace(day=1)
                if month_date.month == 12:
                    month_end = month_date.replace(year=month_date.year + 1, month=1, day=1) - timedelta(days=1)
                else:
                    month_end = month_date.replace(month=month_date.month + 1, day=1) - timedelta(days=1)
                
                leaves = LeaveRequest.objects.filter(
                    created_at__date__gte=month_start,
                    created_at__date__lte=month_end
                )
                data.append({
                    'month': month_start.strftime('%b %Y'),
                    'total': leaves.count(),
                    'pending': leaves.filter(status='PENDING').count(),
                    'approved': leaves.filter(status='APPROVED').count(),
                    'rejected': leaves.filter(status='REJECTED').count()
                })
        
        return Response({
            'success': True,
            'trend_type': trend_type,
            'data': data
        })

# apps/hr/views.py - Add this new view

class HRAddStaffView(APIView):
    """HR can add new staff members"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        if request.user.role != 'HRM':
            return Response({'error': 'Access denied. HR only.'}, status=403)
        
        # Get data from request
        email = request.data.get('email')
        full_name = request.data.get('full_name')
        role = request.data.get('role')
        password = request.data.get('password')
        department_id = request.data.get('department_id')
        contact_number = request.data.get('contact_number', '')
        
        # Validate required fields
        if not email:
            return Response({'error': 'email is required'}, status=400)
        if not full_name:
            return Response({'error': 'full_name is required'}, status=400)
        if not role:
            return Response({'error': 'role is required'}, status=400)
        if not password:
            return Response({'error': 'password is required'}, status=400)
        
        # Check if user already exists
        if User.objects.filter(email=email).exists():
            return Response({'error': 'User with this email already exists'}, status=400)
        
        # Check if role is valid (not patient)
        valid_roles = ['REC', 'END', 'GYN', 'ANE', 'HRM', 'ADM', 'NUR', 'TEC', 'PHA', 'CCO', 'FCO', 'EMB', 'AND']
        if role not in valid_roles:
            return Response({'error': f'Invalid role. Choose from: {", ".join(valid_roles)}'}, status=400)
        
        try:
            # Create user
            user = User.objects.create_user(
                email=email,
                password=password,
                full_name=full_name,
                role=role,
                is_active=True
            )
            
            # Create role-specific profile
            from departments.views import auto_assign_primary
            auto_assign_primary(user)
            
            # Assign department if provided
            if department_id:
                try:
                    from departments.models import Department, StaffDepartmentAssignment
                    department = Department.objects.get(id=department_id)
                    StaffDepartmentAssignment.objects.create(
                        user=user,
                        department=department,
                        role_in_dept='PRIMARY',
                        is_active=True
                    )
                except Department.DoesNotExist:
                    pass
            
            # Update contact number if provided
            if contact_number:
                profile = None
                if role == 'HRM' and hasattr(user, 'hr_profile'):
                    profile = user.hr_profile
                elif role == 'REC' and hasattr(user, 'receptionist_profile'):
                    profile = user.receptionist_profile
                elif role == 'END' and hasattr(user, 'endocrinologist_profile'):
                    profile = user.endocrinologist_profile
                elif role == 'GYN' and hasattr(user, 'gynaec_profile'):
                    profile = user.gynaec_profile
                elif role == 'ANE' and hasattr(user, 'anesth_profile'):
                    profile = user.anesth_profile
                
                if profile:
                    profile.contact_number = contact_number
                    profile.save()
            
            return Response({
                'success': True,
                'message': f'Staff member {full_name} added successfully',
                'staff': {
                    'id': user.id,
                    'name': user.full_name,
                    'email': user.email,
                    'role': user.role,
                    'role_display': user.get_role_display(),
                    'is_active': user.is_active,
                    'date_joined': user.date_joined
                }
            }, status=201)
            
        except Exception as e:
            return Response({'error': str(e)}, status=500)