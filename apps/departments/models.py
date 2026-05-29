from django.db import models
from django.conf import settings
from accounts.models import User

#  DEFAULT DEPARTMENT DEFINITIONS

DEFAULT_DEPARTMENTS=[
	{'name':'Administration & Management', 'code':'ADM'},
	{'name':'HR & Payroll', 'code':'HRM'},
	{'name':'Reception & Front Desk', 'code':'REC'},
	{'name':'Clinical Counselling', 'code':'CCO'},
	{'name':'Financial Counselling', 'code':'FCO'},
	{'name':'Department of Advanced Reproduction', 'code':'END'},
	{'name':'Gynaecology', 'code':'GYN'},
	{'name':'Anaesthesiology', 'code':'ANE'},
	{'name':'Embryology & IVF Lab', 'code':'EMB'},
	{'name':'Andrology', 'code':'AND'},
	{'name':'Laboratory(General)', 'code':'TEC'},
	{'name':'Nursing', 'code':'NUR'},
	{'name':'Pharmacy', 'code':'PHA'},
]
ROLE_DEFAULT_DEPARTMENT={
	'ADM': 'ADM',
	'HRM': 'HRM',
	'REC': 'REC',
    'CCO': 'CCO',
    'FCO': 'FCO',
    'END': 'END',
    'GYN': 'GYN',
    'ANE': 'ANE',
    'EMB': 'EMB',
    'AND': 'AND',
    'TEC': 'TEC',
    'NUR': 'NUR',
    'PHA': 'PHA',
}



class Department(models.Model):
	name=models.CharField(max_length=100,unique=True)
	code=models.CharField(max_length=10,unique=True)
	description=models.TextField(blank=True)

	head=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name='headed_departments',limit_choices_to={'is_active':True},)

	is_active=models.BooleanField(default=True)
	created_at=models.DateTimeField(auto_now_add=True)
	updated_at=models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['name']

	def __str__(self):
		return f"{self.name} ({self.code})"
	@property
	def staff_count(self):
		return self.assignments.filter(is_active=True).values('user').distinct().count()
 
	@property
	def primary_staff_count(self):
		return self.assignments.filter(is_active=True, role_in_dept='PRIMARY').count()
	
class StaffDepartmentAssignment(models.Model):
	ROLE_IN_DEPT=[
		('PRIMARY','Primary'),
		('SECONDARY','Secondary'),
		('TEMPORARY','Temporary'),
	]
	user=models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE,related_name='staff_assignments')
	department=models.ForeignKey('Department',on_delete=models.CASCADE,related_name='assignments')
	unit=models.CharField(max_length=100, blank=True, help_text="Optional unit within the department e.g. OT, OPU Room, IVF Lab")
	notes = models.TextField(blank=True)
	role_in_dept=models.CharField(max_length=10,choices=ROLE_IN_DEPT,default='PRIMARY')
	assigned_on=models.DateField(auto_now_add=True)
	assigned_until=models.DateField(null=True,blank=True)
	is_active=models.BooleanField(default=True)

	class Meta:
		unique_together=('user','department')
		ordering=['-assigned_on']
	
	def __str__(self):
		return f"{self.user.full_name} -> {self.department.name} ({self.role_in_dept})"
	
	def save(self, *args, **kwargs):
		if self.role_in_dept == 'PRIMARY':
			StaffDepartmentAssignment.objects.filter(
    	        user=self.user,
        	    role_in_dept='PRIMARY',
            	is_active=True
        	).exclude(pk=self.pk).update(role_in_dept='SECONDARY')
		super().save(*args, **kwargs)