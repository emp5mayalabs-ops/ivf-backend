from django.db import models
from django.conf import settings
from django.utils import timezone

class OPTicket(models.Model):
	VISIT_REASONS = [
		('CONSULTATION','Consultation'),
		('FOLLOW_UP','Follow-up'),
		('LAB_COLLECTION','Lab Sample Collection'),
		('SCAN','Scan/Ultrasound'),
		('PROCEDURE','Procedure'),
		('MEDICATION','Medication'),
		('OTHER','Other'),
	]

	STATUS_CHOICES = [
		('WAITING','Waiting'),
		('IN_CONSULT','In Consult'),
		('DONE','Done'),
		('CANCELLED','Cancelled'),
	]

	#Auto Incremented token per day
	token_number=models.PositiveIntegerField()
	date=models.DateField(default=timezone.localdate)
	patient=models.ForeignKey('patients.PatientProfile',on_delete=models.CASCADE,related_name='op_tickets',)
	assigned_doctor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,blank=True,null=True,related_name='op_tickets_as_doctor',limit_choices_to={'role__in':['END','GYN','ANE']},)
	department=models.ForeignKey('departments.Department',on_delete=models.SET_NULL,null=True,blank=True,related_name='op_tickets',)
	visit_reason=models.CharField(max_length=50,choices=VISIT_REASONS,default='CONSULTATION')
	status = models.CharField(max_length=20,choices=STATUS_CHOICES,default='WAITING')
	notes=models.TextField(blank=True)
	payment_done=models.BooleanField(default=True)
	created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,related_name='op_tickets_created',)
	created_at=models.DateTimeField(auto_now_add=True)
	updated_at=models.DateTimeField(auto_now=True)

	class Meta:
		ordering=['date','token_number']
		unique_together=('date','token_number')

	def __str__(self):
		return f"Token {self.token_number} - {self.patient.patient_id} - {self.date}"
	@property
	def token(self):
		return self.token_number
	
	@classmethod
	def next_token_for_today(cls):
		today=timezone.now().date()
		last=cls.objects.filter(date=today).order_by('-token_number').first()
		return (last.token_number + 1) if last else 1

