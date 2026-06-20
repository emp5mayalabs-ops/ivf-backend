# apps/attendance/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
User = get_user_model()

from .models import (
    StaffAttendance, 
    AttendanceSettings, 
    AttendanceCorrectionRequest
)
from .serializers import (
    StaffAttendanceSerializer,
    AttendanceSettingsSerializer,
    AttendanceCorrectionRequestSerializer,
)
from .permissions import IsHRM, IsStaff, IsSelfOrHRM, CanMarkAttendance
from departments.models import Department, StaffDepartmentAssignment


# ============= STAFF ATTENDANCE VIEWS =============

class MyAttendanceView(APIView):
    permission_classes = [IsAuthenticated, IsStaff]
    
    def get(self, request):
        today = timezone.now().date()
        
        try:
            attendance = StaffAttendance.objects.get(user=request.user, date=today)
            serializer = StaffAttendanceSerializer(attendance)
            return Response({
                'success': True,
                'attendance': serializer.data
            })
        except StaffAttendance.DoesNotExist:
            return Response({
                'success': True,
                'attendance': None,
                'message': 'No attendance marked for today'
            })


# apps/attendance/views.py

class MarkMyAttendanceView(APIView):
    permission_classes = [IsAuthenticated, CanMarkAttendance]
    
    def post(self, request):
        today = timezone.now().date()
        
        if StaffAttendance.objects.filter(user=request.user, date=today).exists():
            return Response({
                'error': 'Attendance already marked for today. Use PUT to update.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        check_in = request.data.get('check_in')
        check_out = request.data.get('check_out')
        
        if check_in:
            try:
                check_in = datetime.strptime(check_in, '%H:%M').time()
            except ValueError:
                return Response({
                    'error': 'Invalid check_in format. Use HH:MM'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        if check_out:
            try:
                check_out = datetime.strptime(check_out, '%H:%M').time()
            except ValueError:
                return Response({
                    'error': 'Invalid check_out format. Use HH:MM'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        status_val = request.data.get('status', 'PRESENT')
        remarks = request.data.get('remarks', '')
        
        valid_statuses = ['PRESENT', 'ABSENT', 'LATE', 'ON_LEAVE', 'HALF_DAY', 'WORK_FROM_HOME']
        if status_val not in valid_statuses:
            return Response({
                'error': f'Invalid status. Choose from: {", ".join(valid_statuses)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        attendance = StaffAttendance.objects.create(
            user=request.user,
            date=today,
            check_in=check_in,
            check_out=check_out,
            status=status_val,
            remarks=remarks,
            marked_by=request.user
        )
        
        if request.user.role in ['END', 'GYN', 'ANE']:
            try:
                from hr.models import DoctorShiftAssignment
                shift = DoctorShiftAssignment.objects.filter(
                    doctor=request.user,
                    shift_date=today,
                    status__in=['SCHEDULED', 'SWAPPED']
                ).first()
                
                if shift:
                    attendance.shift_assignment = shift
                    attendance.save()
                    
                    shift.is_present = status_val in ['PRESENT', 'LATE']
                    if check_in:
                        shift.check_in_time = check_in
                    if check_out:
                        shift.check_out_time = check_out
                    shift.save()
            except ImportError:
                pass
        
        serializer = StaffAttendanceSerializer(attendance)
        
        return Response({
            'success': True,
            'message': f'Attendance marked for {request.user.full_name}',
            'attendance': serializer.data
        }, status=status.HTTP_201_CREATED)
    
    def put(self, request):
        today = timezone.now().date()
        
        try:
            attendance = StaffAttendance.objects.get(user=request.user, date=today)
        except StaffAttendance.DoesNotExist:
            return Response({
                'error': 'No attendance record found for today'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # ✅ FIX: Timezone-aware datetime comparison
        if request.user.role != 'HRM':
            if attendance.check_in:
                # Make the datetime timezone-aware
                check_in_dt = timezone.make_aware(
                    datetime.combine(today, attendance.check_in),
                    timezone.get_current_timezone()
                )
                now = timezone.now()
                if (now - check_in_dt).seconds > 1800:  # 30 minutes
                    return Response({
                        'error': 'Cannot update attendance after 30 minutes of check in. Contact HR.'
                    }, status=status.HTTP_400_BAD_REQUEST)
        
        check_in = request.data.get('check_in')
        check_out = request.data.get('check_out')
        status_val = request.data.get('status')
        remarks = request.data.get('remarks')
        
        if check_in:
            try:
                attendance.check_in = datetime.strptime(check_in, '%H:%M').time()
            except ValueError:
                return Response({
                    'error': 'Invalid check_in format. Use HH:MM'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        if check_out:
            try:
                attendance.check_out = datetime.strptime(check_out, '%H:%M').time()
            except ValueError:
                return Response({
                    'error': 'Invalid check_out format. Use HH:MM'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        if status_val:
            valid_statuses = ['PRESENT', 'ABSENT', 'LATE', 'ON_LEAVE', 'HALF_DAY', 'WORK_FROM_HOME']
            if status_val not in valid_statuses:
                return Response({
                    'error': f'Invalid status. Choose from: {", ".join(valid_statuses)}'
                }, status=status.HTTP_400_BAD_REQUEST)
            attendance.status = status_val
        
        if remarks is not None:
            attendance.remarks = remarks
        
        attendance.save()
        
        serializer = StaffAttendanceSerializer(attendance)
        
        return Response({
            'success': True,
            'message': 'Attendance updated successfully',
            'attendance': serializer.data
        })


class MyAttendanceHistoryView(APIView):
    permission_classes = [IsAuthenticated, IsStaff]
    
    def get(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        today = timezone.now().date()
        
        if not start_date:
            start_date = (today - timedelta(days=30)).isoformat()
        if not end_date:
            end_date = today.isoformat()
        
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return Response({
                'error': 'Invalid date format. Use YYYY-MM-DD'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        attendances = StaffAttendance.objects.filter(
            user=request.user,
            date__gte=start,
            date__lte=end
        ).order_by('-date')
        
        total = attendances.count()
        present = attendances.filter(status='PRESENT').count()
        absent = attendances.filter(status='ABSENT').count()
        late = attendances.filter(status='LATE').count()
        on_leave = attendances.filter(status='ON_LEAVE').count()
        half_day = attendances.filter(status='HALF_DAY').count()
        work_from_home = attendances.filter(status='WORK_FROM_HOME').count()
        
        total_days = (end - start).days + 1
        attendance_rate = round((present / total_days) * 100, 2) if total_days > 0 else 0
        total_hours = attendances.aggregate(total=Sum('total_hours'))['total'] or Decimal('0.00')
        
        serializer = StaffAttendanceSerializer(attendances, many=True)
        
        return Response({
            'success': True,
            'date_range': {
                'start_date': start.isoformat(),
                'end_date': end.isoformat(),
                'total_days': total_days
            },
            'statistics': {
                'total_records': total,
                'present': present,
                'absent': absent,
                'late': late,
                'on_leave': on_leave,
                'half_day': half_day,
                'work_from_home': work_from_home,
                'attendance_rate': attendance_rate,
                'total_hours': str(total_hours)
            },
            'history': serializer.data
        })


class MyAttendanceStatsView(APIView):
    permission_classes = [IsAuthenticated, IsStaff]
    
    def get(self, request):
        year = request.query_params.get('year', timezone.now().year)
        month = request.query_params.get('month')
        
        try:
            year = int(year)
        except ValueError:
            return Response({'error': 'Invalid year'}, status=status.HTTP_400_BAD_REQUEST)
        
        monthly_stats = []
        
        if month:
            try:
                month = int(month)
                start_date = datetime(year, month, 1).date()
                if month == 12:
                    end_date = datetime(year + 1, 1, 1).date() - timedelta(days=1)
                else:
                    end_date = datetime(year, month + 1, 1).date() - timedelta(days=1)
            except ValueError:
                return Response({'error': 'Invalid month'}, status=status.HTTP_400_BAD_REQUEST)
            
            attendances = StaffAttendance.objects.filter(
                user=request.user,
                date__gte=start_date,
                date__lte=end_date
            )
            
            total = attendances.count()
            present = attendances.filter(status='PRESENT').count()
            absent = attendances.filter(status='ABSENT').count()
            late = attendances.filter(status='LATE').count()
            on_leave = attendances.filter(status='ON_LEAVE').count()
            half_day = attendances.filter(status='HALF_DAY').count()
            work_from_home = attendances.filter(status='WORK_FROM_HOME').count()
            
            total_days = (end_date - start_date).days + 1
            attendance_rate = round((present / total_days) * 100, 2) if total_days > 0 else 0
            total_hours = attendances.aggregate(total=Sum('total_hours'))['total'] or Decimal('0.00')
            
            return Response({
                'success': True,
                'month': start_date.strftime('%B %Y'),
                'statistics': {
                    'total_days': total_days,
                    'present': present,
                    'absent': absent,
                    'late': late,
                    'on_leave': on_leave,
                    'half_day': half_day,
                    'work_from_home': work_from_home,
                    'attendance_rate': attendance_rate,
                    'total_hours': str(total_hours),
                    'total_records': total
                }
            })
        
        for month_num in range(1, 13):
            start_date = datetime(year, month_num, 1).date()
            if month_num == 12:
                end_date = datetime(year + 1, 1, 1).date() - timedelta(days=1)
            else:
                end_date = datetime(year, month_num + 1, 1).date() - timedelta(days=1)
            
            attendances = StaffAttendance.objects.filter(
                user=request.user,
                date__gte=start_date,
                date__lte=end_date
            )
            
            present = attendances.filter(status='PRESENT').count()
            total_days = (end_date - start_date).days + 1
            attendance_rate = round((present / total_days) * 100, 2) if total_days > 0 else 0
            
            monthly_stats.append({
                'month': start_date.strftime('%B'),
                'month_num': month_num,
                'total_days': total_days,
                'present': present,
                'absent': attendances.filter(status='ABSENT').count(),
                'late': attendances.filter(status='LATE').count(),
                'attendance_rate': attendance_rate
            })
        
        return Response({
            'success': True,
            'year': year,
            'monthly_stats': monthly_stats
        })


# ============= HR ADMIN ATTENDANCE VIEWS =============

# apps/attendance/views.py

class AdminAttendanceDashboardView(APIView):
    permission_classes = [IsAuthenticated, IsHRM]
    
    def get(self, request):
        # ✅ Get filter parameters
        date_filter = request.query_params.get('filter', 'today')  # today, weekly, monthly, custom
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        department_id = request.query_params.get('department_id')
        
        today = timezone.now().date()
        
        # ✅ Calculate date range based on filter
        if date_filter == 'today':
            start_date = today
            end_date = today
            filter_label = 'Today'
            
        elif date_filter == 'weekly':
            start_date = today - timedelta(days=today.weekday())
            end_date = start_date + timedelta(days=6)
            filter_label = f'This Week ({start_date.strftime("%b %d")} - {end_date.strftime("%b %d")})'
            
        elif date_filter == 'monthly':
            start_date = today.replace(day=1)
            if today.month == 12:
                end_date = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end_date = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
            filter_label = f'This Month ({start_date.strftime("%b %Y")})'
            
        elif date_filter == 'custom' and start_date_str and end_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                filter_label = f'{start_date.strftime("%b %d")} - {end_date.strftime("%b %d, %Y")}'
            except ValueError:
                return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)
        else:
            start_date = today
            end_date = today
            filter_label = 'Today'
        
        # ✅ Get all staff (excluding patients and donors)
        all_staff = User.objects.exclude(role__in=['PAT', 'DON']).filter(is_active=True)
        
        # ✅ Filter by department if provided
        if department_id:
            dept_staff = StaffDepartmentAssignment.objects.filter(
                department_id=department_id,
                is_active=True,
                user__is_active=True
            ).values_list('user_id', flat=True)
            all_staff = all_staff.filter(id__in=dept_staff)
        
        total_staff = all_staff.count()
        
        # ✅ Get attendances for the date range
        attendances = StaffAttendance.objects.filter(
            date__gte=start_date,
            date__lte=end_date,
            user__in=all_staff
        )
        
        # ✅ Calculate statistics
        total_attendance = attendances.count()
        present = attendances.filter(status='PRESENT').count()
        absent = attendances.filter(status='ABSENT').count()
        late = attendances.filter(status='LATE').count()
        on_leave = attendances.filter(status='ON_LEAVE').count()
        half_day = attendances.filter(status='HALF_DAY').count()
        work_from_home = attendances.filter(status='WORK_FROM_HOME').count()
        
        # ✅ Staff who have at least one attendance record
        staff_marked = attendances.values('user').distinct().count()
        staff_not_marked = total_staff - staff_marked
        
        # ✅ Calculate attendance rate
        attendance_rate = round((present / total_staff) * 100, 2) if total_staff > 0 else 0
        
        # ✅ Department-wise statistics
        department_stats = []
        departments = Department.objects.filter(is_active=True)
        
        for dept in departments:
            # ✅ Filter by department if provided
            if department_id and dept.id != int(department_id):
                continue
                
            dept_staff = StaffDepartmentAssignment.objects.filter(
                department=dept,
                is_active=True,
                user__is_active=True
            ).values_list('user_id', flat=True)
            
            if dept_staff:
                dept_attendances = attendances.filter(user_id__in=dept_staff)
                dept_present = dept_attendances.filter(status='PRESENT').count()
                dept_total = dept_attendances.count()
                dept_staff_count = dept_staff.count()
                
                department_stats.append({
                    'department_id': dept.id,
                    'department_name': dept.name,
                    'department_code': dept.code,
                    'total_staff': dept_staff_count,
                    'marked': dept_total,
                    'present': dept_present,
                    'absent': dept_total - dept_present,
                    'attendance_rate': round((dept_present / dept_staff_count) * 100, 2) if dept_staff_count > 0 else 0
                })
        
        # ✅ Recent activity (last 10 records in the date range)
        recent_attendances = attendances.select_related('user', 'marked_by').order_by('-date', '-created_at')[:10]
        
        recent_activity = []
        for att in recent_attendances:
            recent_activity.append({
                'id': att.id,
                'user_name': att.user.full_name,
                'user_role': att.user.get_role_display(),
                'date': att.date.strftime('%Y-%m-%d'),
                'check_in': att.check_in,
                'check_out': att.check_out,
                'status': att.status,
                'status_display': att.get_status_display(),
                'marked_by': att.marked_by.full_name if att.marked_by else 'Self'
            })
        
        return Response({
            'success': True,
            'dashboard': {
                'filter': {
                    'type': date_filter,
                    'label': filter_label,
                    'start_date': start_date.strftime('%Y-%m-%d'),
                    'end_date': end_date.strftime('%Y-%m-%d'),
                    'total_days': (end_date - start_date).days + 1
                },
                'date': today.strftime('%Y-%m-%d'),
                'day': today.strftime('%A'),
                'today': {
                    'total_staff': total_staff,
                    'marked': staff_marked,
                    'not_marked': staff_not_marked,
                    'present': present,
                    'absent': absent,
                    'late': late,
                    'on_leave': on_leave,
                    'half_day': half_day,
                    'work_from_home': work_from_home,
                    'attendance_rate': attendance_rate
                },
                'weekly': {
                    'present': present,
                    'total': total_attendance,
                    'attendance_rate': attendance_rate
                },
                'monthly': {
                    'present': present,
                    'total': total_attendance,
                    'attendance_rate': attendance_rate
                },
                'department_stats': department_stats,
                'recent_activity': recent_activity
            }
        })

class AdminAllAttendanceView(APIView):
    permission_classes = [IsAuthenticated, IsHRM]
    
    def get(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        department_id = request.query_params.get('department_id')
        user_id = request.query_params.get('user_id')
        status_filter = request.query_params.get('status')
        search = request.query_params.get('search')
        
        today = timezone.now().date()
        
        if not start_date:
            start_date = (today - timedelta(days=30)).isoformat()
        if not end_date:
            end_date = today.isoformat()
        
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return Response({
                'error': 'Invalid date format. Use YYYY-MM-DD'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        attendances = StaffAttendance.objects.filter(
            date__gte=start,
            date__lte=end
        ).select_related('user', 'marked_by')
        
        if department_id:
            dept_staff = StaffDepartmentAssignment.objects.filter(
                department_id=department_id,
                is_active=True
            ).values_list('user_id', flat=True)
            attendances = attendances.filter(user_id__in=dept_staff)
        
        if user_id:
            attendances = attendances.filter(user_id=user_id)
        
        if status_filter:
            attendances = attendances.filter(status=status_filter)
        
        if search:
            attendances = attendances.filter(
                Q(user__full_name__icontains=search) |
                Q(user__email__icontains=search)
            )
        
        attendances = attendances.order_by('-date', 'user__full_name')
        
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        
        total_count = attendances.count()
        paginated = attendances[start_idx:end_idx]
        
        serializer = StaffAttendanceSerializer(paginated, many=True)
        
        return Response({
            'success': True,
            'data': serializer.data,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_count': total_count,
                'total_pages': (total_count + page_size - 1) // page_size
            },
            'filters': {
                'start_date': start.isoformat(),
                'end_date': end.isoformat(),
                'department_id': department_id,
                'user_id': user_id,
                'status': status_filter,
                'search': search
            }
        })


class AdminMarkAttendanceView(APIView):
    permission_classes = [IsAuthenticated, IsHRM]
    
    def post(self, request):
        user_id = request.data.get('user_id')
        date_str = request.data.get('date')
        check_in = request.data.get('check_in')
        check_out = request.data.get('check_out')
        status_val = request.data.get('status', 'PRESENT')
        remarks = request.data.get('remarks', '')
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if date_str:
            try:
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response({
                    'error': 'Invalid date format. Use YYYY-MM-DD'
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            date = timezone.now().date()
        
        valid_statuses = ['PRESENT', 'ABSENT', 'LATE', 'ON_LEAVE', 'HALF_DAY', 'WORK_FROM_HOME']
        if status_val not in valid_statuses:
            return Response({
                'error': f'Invalid status. Choose from: {", ".join(valid_statuses)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        attendance, created = StaffAttendance.objects.update_or_create(
            user=user,
            date=date,
            defaults={
                'check_in': check_in,
                'check_out': check_out,
                'status': status_val,
                'remarks': remarks,
                'marked_by': request.user
            }
        )
        
        if user.role in ['END', 'GYN', 'ANE']:
            try:
                from hr.models import DoctorShiftAssignment
                shift = DoctorShiftAssignment.objects.filter(
                    doctor=user,
                    shift_date=date,
                    status__in=['SCHEDULED', 'SWAPPED']
                ).first()
                
                if shift:
                    attendance.shift_assignment = shift
                    attendance.save()
                    
                    shift.is_present = status_val in ['PRESENT', 'LATE']
                    if check_in:
                        shift.check_in_time = check_in
                    if check_out:
                        shift.check_out_time = check_out
                    shift.save()
            except ImportError:
                pass
        
        serializer = StaffAttendanceSerializer(attendance)
        
        return Response({
            'success': True,
            'message': f'Attendance {"marked" if created else "updated"} for {user.full_name}',
            'attendance': serializer.data
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class AdminAttendanceDetailView(APIView):
    permission_classes = [IsAuthenticated, IsHRM]
    
    def get(self, request, pk):
        try:
            attendance = StaffAttendance.objects.get(id=pk)
            serializer = StaffAttendanceSerializer(attendance)
            return Response({
                'success': True,
                'attendance': serializer.data
            })
        except StaffAttendance.DoesNotExist:
            return Response({'error': 'Attendance record not found'}, status=status.HTTP_404_NOT_FOUND)
    
    def put(self, request, pk):
        try:
            attendance = StaffAttendance.objects.get(id=pk)
        except StaffAttendance.DoesNotExist:
            return Response({'error': 'Attendance record not found'}, status=status.HTTP_404_NOT_FOUND)
        
        check_in = request.data.get('check_in')
        check_out = request.data.get('check_out')
        status_val = request.data.get('status')
        remarks = request.data.get('remarks')
        
        if check_in:
            attendance.check_in = check_in
        if check_out:
            attendance.check_out = check_out
        if status_val:
            valid_statuses = ['PRESENT', 'ABSENT', 'LATE', 'ON_LEAVE', 'HALF_DAY', 'WORK_FROM_HOME']
            if status_val not in valid_statuses:
                return Response({
                    'error': f'Invalid status. Choose from: {", ".join(valid_statuses)}'
                }, status=status.HTTP_400_BAD_REQUEST)
            attendance.status = status_val
        if remarks is not None:
            attendance.remarks = remarks
        
        attendance.save()
        
        serializer = StaffAttendanceSerializer(attendance)
        
        return Response({
            'success': True,
            'message': 'Attendance updated successfully',
            'attendance': serializer.data
        })
    
    def delete(self, request, pk):
        try:
            attendance = StaffAttendance.objects.get(id=pk)
            user_name = attendance.user.full_name
            attendance.delete()
            
            return Response({
                'success': True,
                'message': f'Attendance record for {user_name} deleted successfully'
            })
        except StaffAttendance.DoesNotExist:
            return Response({'error': 'Attendance record not found'}, status=status.HTTP_404_NOT_FOUND)


class AdminBulkAttendanceView(APIView):
    permission_classes = [IsAuthenticated, IsHRM]
    
    def post(self, request):
        date_str = request.data.get('date')
        attendances_data = request.data.get('attendances', [])
        
        if not attendances_data:
            return Response({'error': 'No attendance data provided'}, status=status.HTTP_400_BAD_REQUEST)
        
        if date_str:
            try:
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response({
                    'error': 'Invalid date format. Use YYYY-MM-DD'
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            date = timezone.now().date()
        
        created = 0
        updated = 0
        errors = []
        success_data = []
        
        for data in attendances_data:
            try:
                user_id = data.get('user_id')
                check_in = data.get('check_in')
                check_out = data.get('check_out')
                status_val = data.get('status', 'PRESENT')
                remarks = data.get('remarks', '')
                
                if not user_id:
                    errors.append('Missing user_id')
                    continue
                
                try:
                    user = User.objects.get(id=user_id)
                except User.DoesNotExist:
                    errors.append(f'User {user_id} not found')
                    continue
                
                valid_statuses = ['PRESENT', 'ABSENT', 'LATE', 'ON_LEAVE', 'HALF_DAY', 'WORK_FROM_HOME']
                if status_val not in valid_statuses:
                    errors.append(f'Invalid status for {user.full_name}')
                    continue
                
                attendance, created_flag = StaffAttendance.objects.update_or_create(
                    user=user,
                    date=date,
                    defaults={
                        'check_in': check_in,
                        'check_out': check_out,
                        'status': status_val,
                        'remarks': remarks,
                        'marked_by': request.user
                    }
                )
                
                if created_flag:
                    created += 1
                else:
                    updated += 1
                
                success_data.append({
                    'user_id': user.id,
                    'user_name': user.full_name,
                    'status': status_val
                })
                
            except Exception as e:
                errors.append(str(e))
        
        return Response({
            'success': True,
            'message': f'Bulk attendance processed: {created} created, {updated} updated',
            'created': created,
            'updated': updated,
            'errors': errors if errors else None,
            'success_data': success_data
        })


class AdminStaffAttendanceView(APIView):
    permission_classes = [IsAuthenticated, IsHRM]
    
    def get(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        today = timezone.now().date()
        
        if not start_date:
            start_date = (today - timedelta(days=30)).isoformat()
        if not end_date:
            end_date = today.isoformat()
        
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return Response({
                'error': 'Invalid date format. Use YYYY-MM-DD'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        attendances = StaffAttendance.objects.filter(
            user=user,
            date__gte=start,
            date__lte=end
        ).order_by('-date')
        
        total = attendances.count()
        present = attendances.filter(status='PRESENT').count()
        absent = attendances.filter(status='ABSENT').count()
        late = attendances.filter(status='LATE').count()
        on_leave = attendances.filter(status='ON_LEAVE').count()
        
        total_days = (end - start).days + 1
        attendance_rate = round((present / total_days) * 100, 2) if total_days > 0 else 0
        
        serializer = StaffAttendanceSerializer(attendances, many=True)
        
        return Response({
            'success': True,
            'staff': {
                'id': user.id,
                'name': user.full_name,
                'email': user.email,
                'role': user.role,
                'role_display': user.get_role_display()
            },
            'date_range': {
                'start_date': start.isoformat(),
                'end_date': end.isoformat(),
                'total_days': total_days
            },
            'statistics': {
                'total_records': total,
                'present': present,
                'absent': absent,
                'late': late,
                'on_leave': on_leave,
                'attendance_rate': attendance_rate
            },
            'attendance': serializer.data
        })