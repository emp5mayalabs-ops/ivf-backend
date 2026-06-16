from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import login
from django.utils import timezone
from django.db.models import Q, Count, Sum
from datetime import datetime, timedelta

from .models import (
    HRManagerProfile, 
    LeaveRequest,
    Shift,
    DoctorShiftAssignment,
    ShiftSwapRequest,
    ShiftAttendance,
    LeaveBalance,
    Holiday
)
from .serializers import (
    HRLoginSerializer,
    HRProfileSerializer,
    StaffListSerializer,
    LeaveRequestSerializer,
    ShiftSerializer,
    DoctorShiftAssignmentSerializer,
    ShiftSwapRequestSerializer,
    ShiftAttendanceSerializer,
    LeaveBalanceSerializer,
    HolidaySerializer
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


# apps/hr/views.py - Add this enhanced dashboard view

class HRDashboardView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        if request.user.role != 'HRM':
            return Response({'error': 'Access denied'}, status=403)
        
        from accounts.models import ROLES, LoginAuditLog
        from departments.models import StaffDepartmentAssignment, Department
        from django.db.models import Count, Q
        from datetime import timedelta
        
        all_staff = User.objects.exclude(role__in=['PAT', 'DON'])
        today = timezone.now().date()
        last_month = today - timedelta(days=30)
        last_week = today - timedelta(days=7)
        
        # Get role mapping from accounts.models.ROLES
        role_map = dict(ROLES)
        
        # 1. Staff Statistics
        total_staff = all_staff.count()
        active_staff = all_staff.filter(is_active=True).count()
        inactive_staff = all_staff.filter(is_active=False).count()
        
        # 2. Staff by Role (using ROLES from accounts)
        staff_by_role = {}
        role_counts = all_staff.values('role').annotate(count=Count('id')).order_by('-count')
        
        for item in role_counts:
            role_code = item['role']
            role_name = role_map.get(role_code, role_code)
            staff_by_role[role_code] = {
                'name': role_name,
                'count': item['count'],
                'percentage': round((item['count'] / total_staff) * 100, 1) if total_staff > 0 else 0
            }
        
        # 3. Department-wise Staff Distribution
        department_stats = []
        departments = Department.objects.filter(is_active=True)
        
        for dept in departments:
            staff_count = StaffDepartmentAssignment.objects.filter(
                department=dept,
                is_active=True,
                user__is_active=True,
                user__role__in=[r[0] for r in ROLES if r[0] not in ['PAT', 'DON']]
            ).values('user').distinct().count()
            
            if staff_count > 0:
                department_stats.append({
                    'id': dept.id,
                    'name': dept.name,
                    'code': dept.code,
                    'staff_count': staff_count,
                    'percentage': round((staff_count / total_staff) * 100, 1) if total_staff > 0 else 0
                })
        
        # 4. Online/Active Staff (from LoginAuditLog)
        cutoff = timezone.now() - timedelta(minutes=5)
        online_staff = LoginAuditLog.objects.filter(
            is_active_session=True,
            last_seen__gte=cutoff,
            user__role__in=[r[0] for r in ROLES if r[0] not in ['PAT', 'DON']]
        ).values('user').distinct().count()
        
        # 5. Leave Statistics
        pending_leaves = LeaveRequest.objects.filter(status='PENDING').count()
        
        # Leaves this month
        current_month_start = today.replace(day=1)
        if today.month == 12:
            next_month = today.replace(year=today.year + 1, month=1, day=1)
        else:
            next_month = today.replace(month=today.month + 1, day=1)
        current_month_end = next_month - timedelta(days=1)
        
        leaves_this_month = LeaveRequest.objects.filter(
            created_at__date__gte=current_month_start,
            created_at__date__lte=current_month_end
        )
        
        leaves_this_month_count = leaves_this_month.count()
        approved_leaves_this_month = leaves_this_month.filter(status='APPROVED').count()
        rejected_leaves_this_month = leaves_this_month.filter(status='REJECTED').count()
        
        # 6. Staff Turnover (New joiners in last 30 days)
        recent_joiners = all_staff.filter(
            date_joined__date__gte=last_month,
            date_joined__date__lte=today
        ).count()
        
        # 7. Department Heads
        department_heads = Department.objects.filter(
            head__isnull=False,
            head__is_active=True
        ).select_related('head').count()
        
        # 8. Recent Leave Requests (Last 5 pending)
        recent_leaves = LeaveRequest.objects.filter(
            status='PENDING'
        ).select_related('employee').order_by('-created_at')[:5]
        
        recent_leaves_data = []
        for leave in recent_leaves:
            recent_leaves_data.append({
                'id': leave.id,
                'employee_name': leave.employee.full_name,
                'employee_id': leave.employee.id,
                'leave_type': leave.get_leave_type_display(),
                'start_date': leave.start_date,
                'end_date': leave.end_date,
                'days': (leave.end_date - leave.start_date).days + 1 if leave.end_date and leave.start_date else 0,
                'status': leave.status,
                'created_at': leave.created_at
            })
        
        # 9. Staff with Most Leaves (Top 5)
        top_leave_takers = LeaveRequest.objects.filter(
            status='APPROVED'
        ).values(
            'employee__id',
            'employee__full_name',
            'employee__email',
            'employee__role'
        ).annotate(
            total_leaves=Count('id')
        ).order_by('-total_leaves')[:5]
        
        top_leave_takers_data = []
        for item in top_leave_takers:
            top_leave_takers_data.append({
                'id': item['employee__id'],
                'name': item['employee__full_name'],
                'email': item['employee__email'],
                'role': role_map.get(item['employee__role'], item['employee__role']),
                'total_leaves': item['total_leaves']
            })
        
        # 10. Upcoming Birthdays (if date_of_birth field exists)
        upcoming_birthdays = []
        # Check if date_of_birth field exists on User model
        if hasattr(User, 'date_of_birth'):
            from datetime import date
            current_month = today.month
            current_day = today.day
            
            # Get birthdays in current and next month
            staff_with_birthdays = all_staff.filter(
                date_of_birth__isnull=False,
                is_active=True
            )
            
            for staff in staff_with_birthdays:
                bday_month = staff.date_of_birth.month
                bday_day = staff.date_of_birth.day
                
                # Check if birthday is in next 30 days
                bday_this_year = date(today.year, bday_month, bday_day)
                if bday_this_year >= today and bday_this_year <= today + timedelta(days=30):
                    upcoming_birthdays.append({
                        'name': staff.full_name,
                        'role': role_map.get(staff.role, staff.role),
                        'birthday': bday_this_year.strftime('%b %d'),
                        'days_left': (bday_this_year - today).days
                    })
                elif bday_this_year < today:
                    # Next year's birthday
                    bday_next_year = date(today.year + 1, bday_month, bday_day)
                    if bday_next_year <= today + timedelta(days=30):
                        upcoming_birthdays.append({
                            'name': staff.full_name,
                            'role': role_map.get(staff.role, staff.role),
                            'birthday': bday_next_year.strftime('%b %d'),
                            'days_left': (bday_next_year - today).days
                        })
            
            # Sort by days left and limit to 5
            upcoming_birthdays = sorted(upcoming_birthdays, key=lambda x: x['days_left'])[:5]
        
        # 11. Gender Distribution (if gender field exists)
        gender_distribution = []
        if hasattr(User, 'gender'):
            gender_counts = all_staff.values('gender').annotate(count=Count('id'))
            gender_map = {'M': 'Male', 'F': 'Female', 'O': 'Other', None: 'Not Specified'}
            for item in gender_counts:
                gender_distribution.append({
                    'gender': gender_map.get(item['gender'], 'Not Specified'),
                    'count': item['count'],
                    'percentage': round((item['count'] / total_staff) * 100, 1) if total_staff > 0 else 0
                })
        
        # 12. Leave Balance Summary (if LeaveBalance model exists)
        leave_balance_summary = {
            'total_allocated': 0,
            'total_used': 0,
            'total_remaining': 0
        }
        
        # Check if LeaveBalance model exists
        try:
            from .models import LeaveBalance
            leave_balance_summary = {
                'total_allocated': LeaveBalance.objects.filter(
                    user__in=all_staff
                ).aggregate(total=Sum('allocated_leaves'))['total'] or 0,
                'total_used': LeaveBalance.objects.filter(
                    user__in=all_staff
                ).aggregate(total=Sum('used_leaves'))['total'] or 0,
                'total_remaining': LeaveBalance.objects.filter(
                    user__in=all_staff
                ).aggregate(total=Sum('remaining_leaves'))['total'] or 0
            }
        except:
            pass
        
        return Response({
            'success': True,
            'dashboard': {
                'summary': {
                    'total_staff': total_staff,
                    'active_staff': active_staff,
                    'inactive_staff': inactive_staff,
                    'online_staff': online_staff,
                    'pending_leaves': pending_leaves,
                    'recent_joiners': recent_joiners,
                    'department_heads': department_heads,
                },
                'leave_stats': {
                    'this_month': {
                        'total': leaves_this_month_count,
                        'approved': approved_leaves_this_month,
                        'rejected': rejected_leaves_this_month,
                        'pending': leaves_this_month_count - approved_leaves_this_month - rejected_leaves_this_month
                    },
                    'approval_rate': round((approved_leaves_this_month / leaves_this_month_count) * 100, 1) if leaves_this_month_count > 0 else 0
                },
                'staff_breakdown': {
                    'by_role': staff_by_role,
                    'by_department': department_stats,
                    'by_gender': gender_distribution
                },
                'recent_activity': {
                    'recent_leaves': recent_leaves_data,
                    'top_leave_takers': top_leave_takers_data
                },
                'upcoming_birthdays': upcoming_birthdays,
                'leave_balance_summary': leave_balance_summary
            }
        })


class StaffManagementView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        if request.user.role != 'HRM':
            return Response({'error': 'Access denied'}, status=403)
        
        # Get role filter from query params
        roles = request.query_params.get('role')
        
        # Base queryset - exclude patients and donors
        staff = User.objects.exclude(role__in=['PAT', 'DON'])
        
        # Apply role filter if provided
        if roles:
            # Split by comma if multiple roles (e.g., "END,GYN,ANE")
            role_list = [r.strip() for r in roles.split(',')]
            staff = staff.filter(role__in=role_list)
        
        staff = staff.order_by('-date_joined')
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
        
# ========== SHIFT MANAGEMENT VIEWS ==========

class HRShiftManagementView(APIView):
    """HR can manage shifts (create, edit, delete shifts)"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, shift_id=None):
        """Get all shifts or specific shift"""
        if request.user.role != 'HRM':
            return Response({'error': 'Access denied. HR only.'}, status=403)
        
        # If shift_id is provided, get single shift
        if shift_id:
            try:
                shift = Shift.objects.get(id=shift_id)
                serializer = ShiftSerializer(shift)
                return Response({'success': True, 'shift': serializer.data})
            except Shift.DoesNotExist:
                return Response({'error': 'Shift not found'}, status=404)
        
        # Get all active shifts
        shifts = Shift.objects.filter(is_active=True)
        serializer = ShiftSerializer(shifts, many=True)
        return Response({'success': True, 'shifts': serializer.data})
    
    def post(self, request):
        """Create a new shift"""
        if request.user.role != 'HRM':
            return Response({'error': 'Access denied. HR only.'}, status=403)
        
        serializer = ShiftSerializer(data=request.data)
        if serializer.is_valid():
            shift = serializer.save()
            return Response({
                'success': True,
                'message': f'Shift "{shift.name}" created successfully',
                'shift': serializer.data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def put(self, request, shift_id):
        """Update an existing shift"""
        if request.user.role != 'HRM':
            return Response({'error': 'Access denied. HR only.'}, status=403)
        
        try:
            shift = Shift.objects.get(id=shift_id)
        except Shift.DoesNotExist:
            return Response({'error': 'Shift not found'}, status=404)
        
        serializer = ShiftSerializer(shift, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                'success': True,
                'message': f'Shift updated successfully',
                'shift': serializer.data
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, shift_id):
        """Delete a shift (soft delete)"""
        if request.user.role != 'HRM':
            return Response({'error': 'Access denied. HR only.'}, status=403)
        
        try:
            shift = Shift.objects.get(id=shift_id)
            shift.is_active = False
            shift.save()
            return Response({
                'success': True,
                'message': f'Shift "{shift.name}" deactivated'
            })
        except Shift.DoesNotExist:
            return Response({'error': 'Shift not found'}, status=404)

class HRShiftAssignmentView(APIView):
    """HR can assign doctors to shifts"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get shift assignments for a date range"""
        if request.user.role != 'HRM':
            return Response({'error': 'Access denied. HR only.'}, status=403)
        
        # Get query parameters
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        doctor_id = request.query_params.get('doctor_id')
        
        if not start_date or not end_date:
            return Response({
                'error': 'start_date and end_date are required',
                'format': 'YYYY-MM-DD'
            }, status=400)
        
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Invalid date format'}, status=400)
        
        # Build query
        assignments = DoctorShiftAssignment.objects.filter(
            shift_date__gte=start,
            shift_date__lte=end,
            status__in=['SCHEDULED', 'PENDING_SWAP']
        ).select_related('doctor', 'shift')
        
        if doctor_id:
            assignments = assignments.filter(doctor_id=doctor_id)
        
        serializer = DoctorShiftAssignmentSerializer(assignments, many=True)
        
        return Response({
            'success': True,
            'assignments': serializer.data,
            'total': len(serializer.data)
        })
    
    def post(self, request):
        """Assign a doctor to a shift"""
        if request.user.role != 'HRM':
            return Response({'error': 'Access denied. HR only.'}, status=403)
        
        doctor_id = request.data.get('doctor_id')
        shift_id = request.data.get('shift_id')
        shift_date = request.data.get('shift_date')
        
        # Validate inputs
        if not all([doctor_id, shift_id, shift_date]):
            return Response({'error': 'doctor_id, shift_id, and shift_date are required'}, status=400)
        
        # Validate doctor role
        try:
            doctor = User.objects.get(id=doctor_id)
            if doctor.role not in ['END', 'GYN', 'ANE']:
                return Response({'error': 'Only doctors (END, GYN, ANE) can be assigned shifts'}, status=400)
        except User.DoesNotExist:
            return Response({'error': 'Doctor not found'}, status=404)
        
        # Validate shift
        try:
            shift = Shift.objects.get(id=shift_id, is_active=True)
        except Shift.DoesNotExist:
            return Response({'error': 'Shift not found'}, status=404)
        
        # Validate date
        try:
            shift_date_obj = datetime.strptime(shift_date, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)
        
        # Check for conflicts
        existing = DoctorShiftAssignment.objects.filter(
            doctor=doctor,
            shift_date=shift_date_obj,
            status__in=['SCHEDULED', 'PENDING_SWAP']
        ).exists()
        
        if existing:
            return Response({
                'error': f'Doctor {doctor.full_name} already has a shift on {shift_date}'
            }, status=400)
        
        # Create assignment
        assignment = DoctorShiftAssignment.objects.create(
            doctor=doctor,
            shift=shift,
            shift_date=shift_date_obj,
            assigned_by=request.user,
            status='SCHEDULED'
        )
        
        serializer = DoctorShiftAssignmentSerializer(assignment)
        
        return Response({
            'success': True,
            'message': f'{doctor.full_name} assigned to {shift.name} on {shift_date}',
            'assignment': serializer.data
        }, status=status.HTTP_201_CREATED)
    
    def delete(self, request, assignment_id):
        """Cancel a shift assignment"""
        if request.user.role != 'HRM':
            return Response({'error': 'Access denied. HR only.'}, status=403)
        
        try:
            assignment = DoctorShiftAssignment.objects.get(id=assignment_id)
            
            # Don't allow cancelling completed shifts
            if assignment.status == 'COMPLETED':
                return Response({'error': 'Cannot cancel completed shift'}, status=400)
            
            assignment.status = 'CANCELLED'
            assignment.save()
            
            return Response({
                'success': True,
                'message': f'Shift cancelled for {assignment.doctor.full_name} on {assignment.shift_date}'
            })
        except DoctorShiftAssignment.DoesNotExist:
            return Response({'error': 'Assignment not found'}, status=404)

class HRBulkShiftAssignmentView(APIView):
    """HR can assign multiple doctors to shifts in bulk"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Bulk assign shifts"""
        if request.user.role != 'HRM':
            return Response({'error': 'Access denied. HR only.'}, status=403)
        
        assignments_data = request.data.get('assignments', [])
        
        if not assignments_data:
            return Response({'error': 'No assignments provided'}, status=400)
        
        created = 0
        errors = []
        
        for data in assignments_data:
            try:
                doctor = User.objects.get(id=data.get('doctor_id'), role__in=['END', 'GYN', 'ANE'])
                shift = Shift.objects.get(id=data.get('shift_id'), is_active=True)
                shift_date = timezone.datetime.strptime(data.get('shift_date'), '%Y-%m-%d').date()
                
                # Check for conflicts
                existing = DoctorShiftAssignment.objects.filter(
                    doctor=doctor,
                    shift_date=shift_date,
                    status__in=['SCHEDULED', 'PENDING_SWAP']
                ).exists()
                
                if not existing:
                    DoctorShiftAssignment.objects.create(
                        doctor=doctor,
                        shift=shift,
                        shift_date=shift_date,
                        assigned_by=request.user,
                        status='SCHEDULED'
                    )
                    created += 1
                else:
                    errors.append(f"{doctor.full_name} already has shift on {shift_date}")
                    
            except Exception as e:
                errors.append(str(e))
        
        return Response({
            'success': True,
            'message': f'Successfully created {created} shift assignments',
            'errors': errors if errors else None,
            'created_count': created
        })


class HRShiftSwapApprovalView(APIView):
    """HR can approve/reject shift swap requests"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get all pending swap requests"""
        if request.user.role != 'HRM':
            return Response({'error': 'Access denied. HR only.'}, status=403)
        
        pending_swaps = ShiftSwapRequest.objects.filter(status='PENDING')
        serializer = ShiftSwapRequestSerializer(pending_swaps, many=True)
        
        return Response({
            'success': True,
            'pending_swaps': serializer.data,
            'count': len(serializer.data)
        })
    
    def post(self, request, swap_id):
        """Approve or reject a swap request"""
        if request.user.role != 'HRM':
            return Response({'error': 'Access denied. HR only.'}, status=403)
        
        try:
            swap = ShiftSwapRequest.objects.get(id=swap_id)
        except ShiftSwapRequest.DoesNotExist:
            return Response({'error': 'Swap request not found'}, status=404)
        
        action = request.data.get('action')
        rejection_reason = request.data.get('rejection_reason', '')
        
        if action == 'approve':
            # Execute the swap
            requesting_orig = swap.requesting_assignment
            target_orig = swap.target_assignment
            
            # Create new assignments for swapped doctors
            DoctorShiftAssignment.objects.create(
                doctor=swap.target_doctor,
                shift=requesting_orig.shift,
                shift_date=requesting_orig.shift_date,
                assigned_by=request.user,
                status='SWAPPED'
            )
            
            DoctorShiftAssignment.objects.create(
                doctor=swap.requesting_doctor,
                shift=target_orig.shift,
                shift_date=target_orig.shift_date,
                assigned_by=request.user,
                status='SWAPPED'
            )
            
            # Cancel original assignments
            requesting_orig.status = 'CANCELLED'
            target_orig.status = 'CANCELLED'
            requesting_orig.save()
            target_orig.save()
            
            swap.status = 'APPROVED'
            swap.approved_by = request.user
            swap.approved_at = timezone.now()
            swap.save()
            
            message = f'Shift swap approved between {swap.requesting_doctor.full_name} and {swap.target_doctor.full_name}'
            
        elif action == 'reject':
            swap.status = 'REJECTED'
            swap.rejection_reason = rejection_reason
            swap.save()
            
            # Reset assignment status
            swap.requesting_assignment.status = 'SCHEDULED'
            swap.requesting_assignment.swap_requested_with = None
            swap.requesting_assignment.save()
            
            message = 'Shift swap request rejected'
        else:
            return Response({'error': 'Action must be "approve" or "reject"'}, status=400)
        
        return Response({
            'success': True,
            'message': message
        })


class HRShiftAttendanceView(APIView):
    """HR can mark and track doctor attendance"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Mark attendance for a doctor's shift"""
        if request.user.role != 'HRM':
            return Response({'error': 'Access denied. HR only.'}, status=403)
        
        assignment_id = request.data.get('assignment_id')
        status_attendance = request.data.get('status')
        check_in = request.data.get('check_in')
        check_out = request.data.get('check_out')
        remarks = request.data.get('remarks', '')
        
        try:
            assignment = DoctorShiftAssignment.objects.get(id=assignment_id)
        except DoctorShiftAssignment.DoesNotExist:
            return Response({'error': 'Assignment not found'}, status=404)
        
        # Create or update attendance record
        attendance, created = ShiftAttendance.objects.update_or_create(
            assignment=assignment,
            date=assignment.shift_date,
            defaults={
                'status': status_attendance,
                'check_in': check_in,
                'check_out': check_out,
                'marked_by': request.user,
                'remarks': remarks
            }
        )
        
        # Update assignment status
        if status_attendance == 'PRESENT':
            assignment.is_present = True
            assignment.check_in_time = check_in
            assignment.check_out_time = check_out
        else:
            assignment.is_present = False
        assignment.save()
        
        return Response({
            'success': True,
            'message': f'Attendance marked for {assignment.doctor.full_name} on {assignment.shift_date}'
        })
    
    def get(self, request):
        """Get attendance report"""
        if request.user.role != 'HRM':
            return Response({'error': 'Access denied. HR only.'}, status=403)
        
        # Get date range
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if not start_date or not end_date:
            today = timezone.now().date()
            start_date = (today - timedelta(days=30)).isoformat()
            end_date = today.isoformat()
        
        attendances = ShiftAttendance.objects.filter(
            date__gte=start_date,
            date__lte=end_date
        ).select_related('assignment__doctor', 'assignment__shift')
        
        # Statistics
        total = attendances.count()
        present = attendances.filter(status='PRESENT').count()
        absent = attendances.filter(status='ABSENT').count()
        late = attendances.filter(status='LATE').count()
        
        return Response({
            'success': True,
            'statistics': {
                'total': total,
                'present': present,
                'absent': absent,
                'late': late,
                'attendance_rate': round((present / total) * 100, 1) if total > 0 else 0
            },
            'attendances': ShiftAttendanceSerializer(attendances, many=True).data
        })


class HRShiftDashboardView(APIView):
    """HR shift management dashboard statistics"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        if request.user.role != 'HRM':
            return Response({'error': 'Access denied'}, status=403)
        
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        month_start = today.replace(day=1)
        
        # Today's shifts summary
        today_assignments = DoctorShiftAssignment.objects.filter(shift_date=today)
        total_today = today_assignments.count()
        present_today = today_assignments.filter(is_present=True).count()
        
        # Weekly coverage
        weekly_assignments = DoctorShiftAssignment.objects.filter(
            shift_date__gte=week_start,
            shift_date__lte=week_end
        )
        
        # Monthly coverage
        monthly_assignments = DoctorShiftAssignment.objects.filter(
            shift_date__gte=month_start,
            shift_date__lte=today
        )
        
        # Pending swap requests
        pending_swaps = ShiftSwapRequest.objects.filter(status='PENDING').count()
        
        # Shift type distribution
        shift_distribution = {}
        for shift in Shift.objects.filter(is_active=True):
            count = DoctorShiftAssignment.objects.filter(
                shift=shift,
                shift_date__gte=today
            ).count()
            if count > 0:
                shift_distribution[shift.name] = count
        
        # Calculate attendance rate
        attendances = ShiftAttendance.objects.filter(date__gte=week_start, date__lte=week_end)
        total_attendance = attendances.count()
        present_attendance = attendances.filter(status='PRESENT').count()
        attendance_rate = round((present_attendance / total_attendance) * 100, 1) if total_attendance > 0 else 0
        
        return Response({
            'success': True,
            'today_summary': {
                'total_shifts': total_today,
                'present': present_today,
                'absent': total_today - present_today,
                'attendance_rate': round((present_today / total_today) * 100, 1) if total_today > 0 else 0
            },
            'weekly_summary': {
                'total_shifts': weekly_assignments.count(),
                'unique_doctors': weekly_assignments.values('doctor').distinct().count(),
                'total_hours': weekly_assignments.aggregate(total=Sum('shift__duration_hours'))['total'] or 0
            },
            'monthly_summary': {
                'total_shifts': monthly_assignments.count(),
                'unique_doctors': monthly_assignments.values('doctor').distinct().count()
            },
            'shift_distribution': shift_distribution,
            'attendance_rate': attendance_rate,
            'pending_swaps': pending_swaps
        })


class HolidayManagementView(APIView):
    """HR can manage company holidays"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get all holidays for a year"""
        if request.user.role != 'HRM':
            return Response({'error': 'Access denied. HR only.'}, status=403)
        
        year = request.query_params.get('year', timezone.now().year)
        
        try:
            holidays = Holiday.objects.filter(date__year=year)
            serializer = HolidaySerializer(holidays, many=True)
            return Response({
                'success': True,
                'year': year,
                'holidays': serializer.data,
                'count': len(serializer.data)
            })
        except Exception as e:
            return Response({'error': str(e)}, status=400)
    
    def post(self, request):
        """Create a new holiday"""
        if request.user.role != 'HRM':
            return Response({'error': 'Access denied. HR only.'}, status=403)
        
        serializer = HolidaySerializer(data=request.data)
        if serializer.is_valid():
            holiday = serializer.save()
            return Response({
                'success': True,
                'message': f'Holiday "{holiday.name}" created successfully',
                'holiday': serializer.data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, holiday_id):
        """Delete a holiday"""
        if request.user.role != 'HRM':
            return Response({'error': 'Access denied. HR only.'}, status=403)
        
        try:
            holiday = Holiday.objects.get(id=holiday_id)
            holiday.delete()
            return Response({
                'success': True,
                'message': f'Holiday "{holiday.name}" deleted successfully'
            })
        except Holiday.DoesNotExist:
            return Response({'error': 'Holiday not found'}, status=404)


class LeaveBalanceManagementView(APIView):
    """HR can manage employee leave balances"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get leave balances for all employees or specific one"""
        if request.user.role != 'HRM':
            return Response({'error': 'Access denied. HR only.'}, status=403)
        
        user_id = request.query_params.get('user_id')
        year = request.query_params.get('year', timezone.now().year)
        
        balances = LeaveBalance.objects.filter(year=year).select_related('user')
        
        if user_id:
            balances = balances.filter(user_id=user_id)
        
        serializer = LeaveBalanceSerializer(balances, many=True)
        
        return Response({
            'success': True,
            'year': year,
            'balances': serializer.data
        })
    
    def post(self, request):
        """Create or update leave balance for an employee"""
        if request.user.role != 'HRM':
            return Response({'error': 'Access denied. HR only.'}, status=403)
        
        user_id = request.data.get('user_id')
        year = request.data.get('year', timezone.now().year)
        
        if not user_id:
            return Response({'error': 'user_id is required'}, status=400)
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=404)
        
        balance, created = LeaveBalance.objects.update_or_create(
            user=user,
            year=year,
            defaults={
                'annual_allocated': request.data.get('annual_allocated', 20),
                'sick_allocated': request.data.get('sick_allocated', 12),
                'casual_allocated': request.data.get('casual_allocated', 10),
                'annual_used': request.data.get('annual_used', 0),
                'sick_used': request.data.get('sick_used', 0),
                'casual_used': request.data.get('casual_used', 0)
            }
        )
        
        serializer = LeaveBalanceSerializer(balance)
        
        return Response({
            'success': True,
            'message': f'Leave balance {"created" if created else "updated"} for {user.full_name}',
            'balance': serializer.data
        })