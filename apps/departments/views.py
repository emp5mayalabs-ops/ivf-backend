from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Department, StaffDepartmentAssignment, DEFAULT_DEPARTMENTS, ROLE_DEFAULT_DEPARTMENT
from .serializers import DepartmentSerializer, DepartmentStaffSerializer
from accounts.models import User


def auto_assign_primary(user):
    dept_code = ROLE_DEFAULT_DEPARTMENT.get(user.role)
    if not dept_code:
        return None
    try:
        department = Department.objects.get(code=dept_code)
        assignment, created = StaffDepartmentAssignment.objects.get_or_create(
            user=user,
            department=department,
            defaults={'role_in_dept': 'PRIMARY'}
        )
        if not created and assignment.role_in_dept != 'PRIMARY':
            assignment.role_in_dept = 'PRIMARY'
            assignment.save()
        return assignment
    except Department.DoesNotExist:
        return None  # Dept not seeded yet


def get_employee_id(user):
  profile_map = {
    'REC': 'receptionist_profile',
    'CCO': 'clinical_counsellor_profile',
    'FCO': 'financial_counsellor_profile',
    'END': 'endocrinologist_profile',
    'GYN': 'gynaec_profile',
    'ANE': 'anesth_profile',
    'EMB': 'embryologist_profile',
    'NUR': 'nurse_profile',
    'AND': 'andrology_technician_profile',
    'TEC': 'technician_profile',
    'PHA': 'pharmacist_profile',
    'HRM': 'hr_profile',
    'ADM': 'admin_profile',
  }
  profile_attr = profile_map.get(user.role)
  if profile_attr:
    profile = getattr(user, profile_attr, None)
    if profile:
      return profile.employee_id
  return None


def get_staff_with_unit(assignments):
  result = []
  for a in assignments:
    user = a.user
    result.append({
      'id': user.id,
      'employee_id': get_employee_id(user),
      'full_name': user.full_name,
      'email': user.email,
      'role': user.role,
      'role_display': user.get_role_display(),
      'is_active': user.is_active,
      'date_joined': user.date_joined.isoformat() if user.date_joined else None,
      'unit': a.unit or "",
      'assignment_id': a.id,
    })
  return result

class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Department.objects.all()
        if self.request.query_params.get('active_only'):
            qs = qs.filter(is_active=True)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            self.perform_create(serializer)
            return Response({
                "message": "Department added successfully.",
                "department": serializer.data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        if serializer.is_valid():
            self.perform_update(serializer)
            return Response({
                "message": "Department updated successfully.",
                "department": serializer.data
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # GET /api/departments/<id>/staff
    @action(detail=True, methods=['get'], url_path='staff')
    def staff(self, request, pk=None):
        department = self.get_object()
        base_qs = StaffDepartmentAssignment.objects.filter(
            department=department,
            is_active=True,
        ).select_related('user').order_by('user__full_name')
        primary_assignments = base_qs.filter(role_in_dept='PRIMARY')
        secondary_assignments = base_qs.filter(role_in_dept__in=['SECONDARY', 'TEMPORARY'])
        return Response({
            'department': DepartmentSerializer(department).data,
            'primary_staff': get_staff_with_unit(primary_assignments),
            'secondary_staff': get_staff_with_unit(secondary_assignments),
            'primary_count': primary_assignments.count(),
            'secondary_count': secondary_assignments.count(),
        })

    # POST /api/departments/<id>/assign
    @action(detail=True, methods=['post'], url_path='assign')
    def assign(self, request, pk=None):
        department = self.get_object()
        user_id = request.data.get('user_id')
        role = request.data.get('role_in_dept', 'SECONDARY')
        notes = request.data.get('notes', '')
        until = request.data.get('assigned_until', None)

        if not user_id:
            return Response({'detail': 'user_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        existing = StaffDepartmentAssignment.objects.filter(user=user, department=department).first()
        if existing:
            existing.role_in_dept = role
            existing.is_active = True
            existing.notes = notes
            existing.assigned_until = until
            existing.save()
            msg = "Assignment updated"
        else:
            StaffDepartmentAssignment.objects.create(
                user=user,
                department=department,
                role_in_dept=role,
                notes=notes,
                assigned_until=until
            )
            msg = "Staff Assigned to department"
        return Response({'detail': msg, 'department': department.name, 'user': user.full_name})

    # POST /api/departments/remove/
    @action(detail=True, methods=['post'], url_path='remove-staff')
    def remove_staff(self, request, pk=None):
        department = self.get_object()
        user_id = request.data.get('user_id')
        updated = StaffDepartmentAssignment.objects.filter(
            department=department,
            user_id=user_id,
        ).update(is_active=False)
        if updated:
            return Response({'detail': 'Staff removed from department'})
        return Response({'detail': 'Assignment not found'}, status=status.HTTP_404_NOT_FOUND)

    # POST /api/departments/transfer
    @action(detail=False, methods=['post'], url_path='transfer')
    def transfer(self, request):
        user_id = request.data.get('user_id')
        to_dept_id = request.data.get('to_department_id')
        notes = request.data.get('notes', '')
        if not user_id or not to_dept_id:
            return Response({'detail': 'user_id and to_department_id are required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user = User.objects.get(id=user_id)
            to_dept = Department.objects.get(id=to_dept_id)
        except (User.DoesNotExist, Department.DoesNotExist):
            return Response({'detail': 'User or department not found.'}, status=status.HTTP_404_NOT_FOUND)
        existing = StaffDepartmentAssignment.objects.filter(user=user, department=to_dept).first()

        if existing:
            existing.role_in_dept = 'PRIMARY'
            existing.is_active = True
            existing.notes = notes
            existing.save()
        else:
            StaffDepartmentAssignment.objects.create(
                user=user,
                department=to_dept,
                role_in_dept='PRIMARY',
                notes=notes,
            )
        return Response({
            'detail': f"{user.full_name} transferred to {to_dept.name} as PRIMARY",
        })

    # POST /api/departments/<id>/toggle-status/
    @action(detail=True, methods=['post'], url_path='toggle-status')
    def toggle_status(self, request, pk=None):
        department = self.get_object()
        department.is_active = not department.is_active
        department.save()
        return Response({
            'id': department.id,
            'is_active': department.is_active,
            'message': f"Department {'activated' if department.is_active else 'deactivated'}.",
        })

    # POST /api/departments/seed/
    @action(detail=False, methods=['post'], url_path='seed')
    def seed(self, request):
        created = []
        existing = []

        for dept in DEFAULT_DEPARTMENTS:
            _, was_created = Department.objects.get_or_create(
                code=dept['code'],
                defaults={
                    'name': dept['name'],
                    'description': dept.get('description', ''),
                },
            )
            (created if was_created else existing).append(dept['name'])
        return Response({
            'created': created,
            'existing': existing,
            'message': f"{len(created)} departments created, {len(existing)} already existed."
        })

    # GET /api/departments/<id>/assignments
    @action(detail=True, methods=['get'], url_path='assignments')
    def assignments(self, request, pk=None):
        department = self.get_object()
        assignments = StaffDepartmentAssignment.objects.filter(department=department).select_related('user').order_by('-assigned_on')
        serializer = DepartmentStaffSerializer(assignments, many=True)
        return Response(serializer.data)
    @action(detail=True,methods=['post'],url_path='set-head')
    def set_head(self, request, pk=None):
        dept = self.get_object()
        staff_id = request.data.get('staff_id')
    # --- Clear head ---
        if not staff_id:
            if dept.head:
                self._clear_hod_flag(dept.head)
                dept.head = None
                dept.save()
                return Response({'detail': 'Department head removed.'})
        try:
            new_head = User.objects.get(id=staff_id)
        except User.DoesNotExist:
            return Response({'detail': 'Staff not found.'}, status=status.HTTP_404_NOT_FOUND)
        is_primary = StaffDepartmentAssignment.objects.filter(
            user=new_head,
            department=dept,
            role_in_dept='PRIMARY',
            is_active=True
        ).exists()
        if not is_primary:
            return Response(
            {'detail': 'Staff must be a primary member of this department.'},
            status=status.HTTP_400_BAD_REQUEST
        )
        # Clear old head's flag
        if dept.head and dept.head != new_head:
            self._clear_hod_flag(dept.head)
        # Set new head's flag
        self._set_hod_flag(new_head)
        dept.head = new_head
        dept.save()
        return Response({
        'detail': 'Department head updated.',
        'head_id': new_head.id,
        'head_name': new_head.full_name,
    })
    def _clear_hod_flag(self, user):
        for attr in [
        'receptionist_profile', 'hr_profile', 'clinical_counsellor_profile',
        'financial_counsellor_profile', 'endocrinologist_profile', 'gynaec_profile',
        'anesth_profile', 'embryologist_profile', 'nurse_profile',
        'pharmacist_profile', 'technician_profile', 'andrology_technician_profile'
    ]:
            if hasattr(user, attr):
                profile = getattr(user, attr)
                if hasattr(profile, 'is_department_head'):
                    profile.is_department_head = False
                    profile.save()
                    break
    def _set_hod_flag(self, user):
        for attr in [
        'receptionist_profile', 'hr_profile', 'clinical_counsellor_profile',
        'financial_counsellor_profile', 'endocrinologist_profile', 'gynaec_profile',
        'anesth_profile', 'embryologist_profile', 'nurse_profile',
        'pharmacist_profile', 'technician_profile', 'andrology_technician_profile'
        ]:
            if hasattr(user, attr):
                profile = getattr(user, attr)
                if hasattr(profile, 'is_department_head'):
                    profile.is_department_head = True
                    profile.save()
                    break

