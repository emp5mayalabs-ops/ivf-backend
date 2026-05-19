from django.contrib import admin
from .models import OPTicket

@admin.register(OPTicket)
class OPTicketAdmin(admin.ModelAdmin):
	list_display=['token','date','patient','assigned_doctor','department','visit_reason','status','created_by']
	list_filter=['date','status','visit_reason','department']
	search_fields=['patient__patient_id','patient__user__full_name','token_number']
	ordering=['-date','token_number']
