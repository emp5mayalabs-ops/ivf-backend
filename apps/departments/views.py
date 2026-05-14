from django.shortcuts import render
from rest_framework import viewsets,status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Department,StaffDepartmentAssignment,DEFAULT_DEPARTMENTS,ROLE_DEFAULT_DEPARTMENT
from .serializers import DepartmentSerializer,DepartmentStaffSerializer
from accounts.models import User



def auto_assign_primary(user):
	dept_code=ROLE_DEFAULT_DEPARTMENT.get(user.role)
	if not dept_code:
		return None
	try:
		department=Department.objects.get(code=dept_code)
		assignment,created=StaffDepartmentAssignment.objects.get_or_create(
			user=user,
			department=department,
			defaults={'role_in_dept':'PRIMARY'}
			)
		if not created and assignment.role_in_dept!='PRIMARY':
			assignment.role_in_dept='PRIMARY'
			assignment.save()
		return assignment
	except Department.DoesNotExist:
		return None                     #Dept not seeded yet

def get_staff_with_unit(assignments):
    result = []
    for a in assignments:
        user = a.user
        result.append({
            'id':            user.id,
            'full_name':     user.full_name,
            'email':         user.email,
            'role':          user.role,
            'role_display':  user.get_role_display(),
            'is_active':     user.is_active,
            'date_joined':   user.date_joined.isoformat() if user.date_joined else None,
            'unit':          a.unit or "",
            'assignment_id': a.id,
        })
    return result


class DepartmentViewSet(viewsets.ModelViewSet):
	queryset=Department.objects.all()
	serializer_class=DepartmentSerializer
	permission_classes=[IsAuthenticated]

	def get_queryset(self):
		qs=Department.objects.all()
		if self.request.query_params.get('active_only'):
			qs=qs.filter(is_active=True)
		return qs
	#GET /api/departments/<id>/staff
	@action(detail=True, methods=['get'], url_path='staff')
	def staff(self, request, pk=None):
		department = self.get_object()
		base_qs=StaffDepartmentAssignment.objects.filter(
      	  department=department,
        	is_active=True,
    			).select_related('user').order_by('user__full_name')
		primary_assignments   = base_qs.filter(role_in_dept='PRIMARY')
		secondary_assignments = base_qs.filter(role_in_dept__in=['SECONDARY', 'TEMPORARY'])
		return Response({
      	  'department':      DepartmentSerializer(department).data,
        	'primary_staff':   get_staff_with_unit(primary_assignments),
        	'secondary_staff': get_staff_with_unit(secondary_assignments),
    	    'primary_count':   primary_assignments.count(),
      	  'secondary_count': secondary_assignments.count(),
    })

	# POST /api/departments/<id>/assign
	@action(detail=True, methods=['post'],url_path='assign')
	def assign(self,request,pk=None):
		department=self.get_object()
		user_id=request.data.get('user_id')
		role=request.data.get('role_in_dept','SECONDARY')
		notes=request.data.get('notes','')
		until=request.data.get('assigned_until',None)

		if not user_id:
			return Response({'detail':'user_id is required'},status=status.HTTP_400_BAD_REQUEST)
		try:
			user=User.objects.get(id=user_id)
		except User.DoesNotExist:
			return Response({'detail':'User not found.'},status=status.HTTP_404_NOT_FOUND)
		existing=StaffDepartmentAssignment.objects.filter(user=user,department=department).first()
		if existing:
			existing.role_in_dept=role
			existing.is_active=True
			existing.notes=notes
			existing.assigned_until=until
			existing.save()
			msg="Assignment updated"
		else:
			StaffDepartmentAssignment.objects.create(
				user=user,
				department=department,
				role_in_dept=role,
				notes=notes,
				assigned_until=until
			)
			msg="Staff Assigned to department"
		return Response({'detail':msg,'department':department.name,'user':user.full_name})
	#POST /api/departments/remove/
	@action(detail=True,methods=['post'],url_path='remove-staff')
	def remove_staff(self,request,pk=None):
		department=self.get_object()
		user_id=request.data.get('user_id')
		updated=StaffDepartmentAssignment.objects.filter(
			department=department,
			user_id=user_id,
		).update(is_active=False)
		if updated:
			return Response({'detail':'Staff removed from department'})
		return Response({'detail':'Assignment not found'},status=status.HTTP_404_NOT_FOUND)
	
	#POST /api/departments/transfer
	@action(detail=False, methods=['post'],url_path='transfer')
	def transfer(self,request):
		user_id=request.data.get('user_id')
		to_dept_id=request.data.get('to_department_id')
		notes=request.data.get('notes','')
		if not user_id or not to_dept_id:
			return Response({'detail':'user_id and to_department_id are required'},status=status.HTTP_400_BAD_REQUEST)
		try:
			user=User.objects.get(id=user_id)
			to_dept=Department.objects.get(id=to_dept_id)
		except (User.DoesNotExist, Department.DoesNotExist):
			return Response({'detail':'User or department not found.'},status=status.HTTP_404_NOT_FOUND)
		existing=StaffDepartmentAssignment.objects.filter(user=user,department=to_dept).first()

		if existing:
			existing.role_in_dept = 'PRIMARY'
			existing.is_active =True
			existing.notes=notes
			existing.save()
		else:
			StaffDepartmentAssignment.objects.create(
				user=user,
				department=to_dept,
				role_in_dept='PRIMARY',
				notes=notes,
			)
		return Response({
			'detail':f"{user.full_name} transferred to {to_dept.name} as PRIMARY",
		})
	
	#POST /api/departments/<id>/toggle-status/
	@action(detail=True,methods=['post'],url_path='toggle-status')
	def toggle_status(self,request,pk=None):
		department=self.get_object()
		department.is_active= not department.is_active
		department.save()
		return Response({
			'id':department.id,
			'is_active':department.is_active,
			'message': f"Department {'activated' if department.is_active else 'deactivated'}.",
		})
	
	#POST /api/departments/seed/
	@action(detail=False,methods=['post'],url_path='seed')
	def seed(self,request):
		created=[]
		existing=[]

		for dept in DEFAULT_DEPARTMENTS:
			_, was_created =Department.objects.get_or_create(
				code=dept['code'],
				defaults={
					'name': dept['name'],
					'description': dept.get('description',''),
				},
			)
			(created if was_created else existing).append(dept['name'])
		return Response({
			'created':created,
			'existing':existing,
			'message':f"{len(created)} departments created, {len(existing)} already existed."
		})
	
	#GET /api/departments/<id>/assignments
	@action(detail=True, methods=['get'],url_path='assignments')
	def assignments(self,request,pk=None):
		department=self.get_object()
		assignments=StaffDepartmentAssignment.objects.filter(department=department).select_related('user').order_by('-assigned_on')

		serializer=DepartmentStaffSerializer(assignments,many=True)
		return Response(serializer.data)

