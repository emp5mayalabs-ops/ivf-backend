from .models import User,AdminProfile,LoginAuditLog
from .serializer import AdminUserCreateSerializer,LoginSerializer
from rest_framework import viewsets,status
from rest_framework.permissions import IsAdminUser,IsAuthenticated,AllowAny
from django.core.mail import send_mail
from django.conf import settings
from rest_framework.parsers import FormParser,MultiPartParser
from rest_framework.decorators import action
from rest_framework.renderers import TemplateHTMLRenderer,JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import redirect
from django.contrib.auth import login,logout,authenticate
from django.contrib.auth import update_session_auth_hash
from django.middleware.csrf import get_token
from django.urls import reverse_lazy,reverse
from django.db.models import OuterRef,Subquery
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count
from .permissions import StaffPermission
from hr.models import HRManagerProfile
from accounts.models import ReceptionistProfile,ClinicalCounsellorProfile,FinancialCounsellorProfile,EmbryologistProfile,AnesthesiologistProfile,NurseProfile
from adv_reproduction.models import ReproductiveEndocrinologistProfile
from lab.models import LabTechnicianProfile,AndrologyLabTechnician
from pharmacy.models import PharmacistProfile
from patients.models import PatientProfile
from gynaecology.models import GynaecologistProfile
from departments.views import auto_assign_primary
from departments.models import StaffDepartmentAssignment, Department

ROLE_REDIRECTS = {
    'ADM': '/superadmin',
    'HRM': '/hr',
    'REC': '/receptionist',
    'CCO': '/counsellor',
    'FCO': '/finance',
    'END': '/endocrinologist',
    'GYN': '/gynaecologist',
    'ANE': '/anaesthesiologist',
    'EMB': '/embryologist',
    'NUR': '/nurse',
    'PHA': '/pharmacy',
    'TEC': '/lab',
    'AND': '/andrology',
    'PAT': '/patient',
}

def handle_role_change(user,old_role,new_role):
    if old_role==new_role:
        return
    role_profile_map={
        'REC':('receptionist_profile',ReceptionistProfile),
        'CCO':('clinical_counsellor_profile',ClinicalCounsellorProfile),
        'FCO':('financial_counsellor_profile',FinancialCounsellorProfile),
        'END':('endocrinologist_profile',ReproductiveEndocrinologistProfile),
        'GYN':('gynaec_profile',GynaecologistProfile),
        'ANE':('anesthesia_profile',AnesthesiologistProfile),
        'EMB':('embryologist_profile',EmbryologistProfile),
        'NUR':('nurse_profile',NurseProfile),
        'AND':('andrology_technician_profile',AndrologyLabTechnician),
        'TEC':('technician_profile',LabTechnicianProfile),
        'PHA':('pharmacist_profile',PharmacistProfile),
        'PAT': ('patient_profile', PatientProfile),
        'HRM':('hr_profile',HRManagerProfile),
        'ADM':('admin_profile',AdminProfile),
    }
    if old_role in role_profile_map:
        attr,_=role_profile_map[old_role]
        if hasattr(user,attr):
            getattr(user,attr).delete()

    if new_role in role_profile_map:
        _,model=role_profile_map[new_role]
        model.objects.get_or_create(user=user)

def get_role_redirect(role: str) -> str:
    return ROLE_REDIRECTS.get(role, '/dashboard')

def get_client_ip(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')

class CSRFTokenView(APIView):
    permission_classes=[AllowAny]
    def get(self,request):
        return Response({'csrfToken':get_token(request)})

class ClinicLoginView(APIView):
    permission_classes = [AllowAny]
 
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'detail': 'Invalid input.', 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
 
        email = serializer.validated_data['email']
        password = serializer.validated_data['password']
 
        user = authenticate(request, username=email, password=password)
 
        if user is None:
            return Response(
                {'detail': 'Invalid email or password.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if not user.is_active:
            return Response({'detail':'This account has been deactivated. Contact your administrator.'}, status=status.HTTP_403_FORBIDDEN)
        
        login(request,user)

        LoginAuditLog.objects.filter(
            user=user,
            is_active_session=True
        ).update(is_active_session=False,logout_time=timezone.now())

        LoginAuditLog.objects.create(
            user=user,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT',''),
            is_active_session=True
        )
        return Response({
            'user':{
                'id':user.id,
                'email':user.email,
                'full_name':user.full_name,
                'role':user.role,
                'role_display':user.get_role_display(),
                'has_changed_password':user.has_changed_password,
	},
	'redirect_url':get_role_redirect(user.role),
        },status=status.HTTP_200_OK)

    
class ClinicLogoutView(APIView):
    permission_classes=[IsAuthenticated]
    def post(self,request):
        LoginAuditLog.objects.filter(
            user=request.user,
            is_active_session=True,
        ).update(
            is_active_session=False,
            logout_time=timezone.now(),
        )
        logout(request)
        return Response({'detail':'Successfully logged out.'})

class MeView(APIView):
    permission_classes=[IsAuthenticated]
    def get(self,request):
        user=request.user
        return Response({
                'id':user.id,
                'email':user.email,
                'full_name':user.full_name,
                'role':user.role,
                'role_display':user.get_role_display(),
                'has_changed_password':user.has_changed_password,
	})


class StaffManagementViewSet(viewsets.ModelViewSet):
    queryset=User.objects.all()
    serializer_class=AdminUserCreateSerializer
    permission_classes=[StaffPermission]
    parser_classes = [FormParser, MultiPartParser]
    # 1. Add Renderers: JSON for the API, Template for the Browser
    renderer_classes = [JSONRenderer, TemplateHTMLRenderer]
    template_name = 'staff_list.html'

    # 2. Add a custom action to show the "Create" page
    @action(detail=False, methods=['get'], url_path='create-staff')
    def onboard(self, request):
        # This tells DRF to render your html file when someone visits /staff-management/create-staff/
        return Response({}, template_name='create_user.html')

    def get_queryset(self):
        return User.objects.exclude(role__in=['PAT','DON']).order_by('-date_joined')
    def list(self,request,*args,**kwargs):
        response=super().list(request,*args,**kwargs)
        if request.accepted_renderer.format=='html':
            return Response({'staff_members':response.data},template_name='staff_list.html')
        return response
    
    @action(detail=True, methods=['get', 'post'], url_path='edit')
    def edit(self, request, pk=None):
        staff = self.get_object()

        if request.method == 'GET':
            return Response(
                {'staff': staff},
                template_name='edit_staff.html')
        old_role=staff.role

        serializer = self.get_serializer(staff,data=request.data,partial=True)
        serializer.is_valid(raise_exception=True)
        updated_user=serializer.save()
        new_role=updated_user.role
        #to delete the profile and make new profile with updated user role
        if old_role!=new_role:
            handle_role_change(updated_user,old_role,new_role)
            auto_assign_primary(updated_user)

        StaffDepartmentAssignment.objects.filter(
            user=updated_user,
            role_in_dept__in=['SECONDARY','TEMPORARY'],
            is_active=True,
            ).update(is_active=False)
        
        if updated_user.role == 'HRM' and hasattr(updated_user, 'hr_profile'):
            profile = updated_user.hr_profile
            profile.can_approve_leaves    = request.data.get('can_approve_leaves') == 'on'
            profile.can_view_salaries     = request.data.get('can_view_salaries') == 'on'
            profile.can_terminate_staff   = request.data.get('can_terminate_staff') == 'on'
            profile.can_edit_attendance   = request.data.get('can_edit_attendance') == 'on'
            profile.can_generate_payslips = request.data.get('can_generate_payslips') == 'on'
            profile.can_update_documents  = request.data.get('can_update_documents') == 'on'
            profile.is_department_head    = request.data.get('is_department_head') == 'on'
            profile.save()
            is_hod=request.data.get('is_department_head') == 'on'
            if is_hod:
                primary=StaffDepartmentAssignment.objects.filter(
                    user=updated_user,
                    role_in_dept='PRIMARY',
                    is_active=True
                ).select_related('department').first()
                if primary:
                    primary.department.head=updated_user
                    primary.department.save()
            else:
                Department.objects.filter(head=updated_user).update(head=None)
        
        if  updated_user.role == 'REC' and hasattr(updated_user,'receptionist_profile'):
            profile = updated_user.receptionist_profile
            profile.can_register_patient=request.data.get('can_register_patient') == 'on'
            profile.can_access_billing=request.data.get('can_access_billing') == 'on'
            profile.can_modify_patient_records=request.data.get('can_modify_patient_records') == 'on'
            profile.can_schedule_appointment=request.data.get('can_schedule_appointment') == 'on'
            profile.is_department_head=request.data.get('is_department_head') == 'on'
            profile.save()
            is_hod=request.data.get('is_department_head') == 'on'
            if is_hod:
                primary=StaffDepartmentAssignment.objects.filter(
                    user=updated_user,
                    role_in_dept='PRIMARY',
                    is_active=True
                ).select_related('department').first()
                if primary:
                    primary.department.head=updated_user
                    primary.department.save()
            else:
                Department.objects.filter(head=updated_user).update(head=None)

        if updated_user.role == 'CCO' and hasattr(updated_user, 'clinical_counsellor_profile'):
            profile = updated_user.clinical_counsellor_profile
            profile.is_department_head=request.data.get('is_department_head') == 'on'
            profile.save()
            is_hod=request.data.get('is_department_head') == 'on'
            if is_hod:
                primary=StaffDepartmentAssignment.objects.filter(
                    user=updated_user,
                    role_in_dept='PRIMARY',
                    is_active=True
                ).select_related('department').first()
                if primary:
                    primary.department.head=updated_user
                    primary.department.save()
            else:
                Department.objects.filter(head=updated_user).update(head=None)
            
        if updated_user.role == 'FCO' and hasattr(updated_user, 'financial_counsellor_profile'):
            profile = updated_user.financial_counsellor_profile
            profile.can_approve_discounts=request.data.get('can_approve_discounts') == 'on'
            profile.can_override_insurance=request.data.get('can_override_insurance') == 'on'
            profile.is_department_head=request.data.get('is_department_head') == 'on'
            profile.save()
            is_hod=request.data.get('is_department_head') == 'on'
            if is_hod:
                primary=StaffDepartmentAssignment.objects.filter(
                    user=updated_user,
                    role_in_dept='PRIMARY',
                    is_active=True
                ).select_related('department').first()
                if primary:
                    primary.department.head=updated_user
                    primary.department.save()
            else:
                Department.objects.filter(head=updated_user).update(head=None)

        if updated_user.role == 'END' and hasattr(updated_user, 'endocrinologist_profile'):
            profile = updated_user.endocrinologist_profile
            profile.can_perform_egg_retrieval=request.data.get('can_perform_egg_retrieval') == 'on'
            profile.can_perform_embryo_transfer=request.data.get('can_perform_embryo_transfer') == 'on'
            profile.can_design_ivf_protocols=request.data.get('can_design_ivf_protocols') == 'on'
            profile.is_department_head=request.data.get('is_department_head') == 'on'
            profile.save()
            is_hod=request.data.get('is_department_head') == 'on'
            if is_hod:
                primary=StaffDepartmentAssignment.objects.filter(
                    user=updated_user,
                    role_in_dept='PRIMARY',
                    is_active=True
                ).select_related('department').first()
                if primary:
                    primary.department.head=updated_user
                    primary.department.save()
            else:
                Department.objects.filter(head=updated_user).update(head=None)

        if updated_user.role == 'GYN' and hasattr(updated_user, 'gynaec_profile'):
            profile = updated_user.gynaec_profile
            profile.can_perform_egg_retrieval=request.data.get('can_perform_egg_retrieval') == 'on'
            profile.can_assist_ivf=request.data.get('can_assist_ivf') == 'on'
            profile.is_department_head=request.data.get('is_department_head') == 'on'
            profile.save()
            is_hod=request.data.get('is_department_head') == 'on'
            if is_hod:
                primary=StaffDepartmentAssignment.objects.filter(
                    user=updated_user,
                    role_in_dept='PRIMARY',
                    is_active=True
                ).select_related('department').first()
                if primary:
                    primary.department.head=updated_user
                    primary.department.save()
            else:
                Department.objects.filter(head=updated_user).update(head=None)

        if updated_user.role == 'ANE' and hasattr(updated_user, 'anesth_profile'):
            profile = updated_user.anesth_profile
            profile.can_edit_anesthesia_records=request.data.get('can_edit_anesthesia_records') == 'on'
            profile.is_department_head=request.data.get('is_department_head') == 'on'
            profile.save()
            is_hod=request.data.get('is_department_head') == 'on'
            if is_hod:
                primary=StaffDepartmentAssignment.objects.filter(
                    user=updated_user,
                    role_in_dept='PRIMARY',
                    is_active=True
                ).select_related('department').first()
                if primary:
                    primary.department.head=updated_user
                    primary.department.save()
            else:
                Department.objects.filter(head=updated_user).update(head=None)

        if updated_user.role == 'EMB' and hasattr(updated_user, 'embryologist_profile'):
            profile = updated_user.embryologist_profile
            profile.can_perform_icsi=request.data.get('can_perform_icsi') == 'on'
            profile.can_perform_biopsy=request.data.get('can_perform_biopsy') == 'on'
            profile.is_department_head=request.data.get('is_department_head') == 'on'
            profile.save()
            is_hod=request.data.get('is_department_head') == 'on'
            if is_hod:
                primary=StaffDepartmentAssignment.objects.filter(
                    user=updated_user,
                    role_in_dept='PRIMARY',
                    is_active=True
                ).select_related('department').first()
                if primary:
                    primary.department.head=updated_user
                    primary.department.save()
            else:
                Department.objects.filter(head=updated_user).update(head=None)

        if updated_user.role == 'NUR' and hasattr(updated_user, 'nurse_profile'):
            profile = updated_user.nurse_profile
            profile.is_head_nurse=request.data.get('is_head_nurse') == 'on'
            profile.is_department_head=request.data.get('is_department_head') == 'on'
            print("DEBUG is_department_head:", profile.is_department_head)
            profile.save()
            profile.refresh_from_db()  # ← add this to confirm it saved
            print("DEBUG after save:", profile.is_department_head)
            is_hod=request.data.get('is_department_head') == 'on'
            if is_hod:
                primary=StaffDepartmentAssignment.objects.filter(
                    user=updated_user,
                    role_in_dept='PRIMARY',
                    is_active=True
                ).select_related('department').first()
                if primary:
                    primary.department.head=updated_user
                    primary.department.save()
            else:
                Department.objects.filter(head=updated_user).update(head=None)

        if updated_user.role == 'PHA' and hasattr(updated_user, 'pharmacist_profile'):
            profile = updated_user.pharmacist_profile
            profile.can_manage_inventory=request.data.get('can_manage_inventory') == 'on'
            profile.is_department_head=request.data.get('is_department_head') == 'on'
            profile.save()
            is_hod=request.data.get('is_department_head') == 'on'
            if is_hod:
                primary=StaffDepartmentAssignment.objects.filter(
                    user=updated_user,
                    role_in_dept='PRIMARY',
                    is_active=True
                ).select_related('department').first()
                if primary:
                    primary.department.head=updated_user
                    primary.department.save()
            else:
                Department.objects.filter(head=updated_user).update(head=None)

        if updated_user.role == 'TEC' and hasattr(updated_user, 'technician_profile'):
            profile = updated_user.technician_profile
            profile.is_department_head=request.data.get('is_department_head') == 'on'
            profile.save()
            is_hod=request.data.get('is_department_head') == 'on'
            if is_hod:
                primary=StaffDepartmentAssignment.objects.filter(
                    user=updated_user,
                    role_in_dept='PRIMARY',
                    is_active=True
                ).select_related('department').first()
                if primary:
                    primary.department.head=updated_user
                    primary.department.save()
            else:
                Department.objects.filter(head=updated_user).update(head=None)

        if updated_user.role == 'AND' and hasattr(updated_user, 'andrology_technician_profile'):
            profile = updated_user.andrology_technician_profile
            profile.can_perform_dna_frag=request.data.get('can_perform_dna_frag') == 'on'
            profile.can_perform_cryo=request.data.get('can_perform_cryo') == 'on'
            profile.is_department_head=request.data.get('is_department_head') == 'on'
            profile.save()
            is_hod=request.data.get('is_department_head') == 'on'
            if is_hod:
                primary=StaffDepartmentAssignment.objects.filter(
                    user=updated_user,
                    role_in_dept='PRIMARY',
                    is_active=True
                ).select_related('department').first()
                if primary:
                    primary.department.head=updated_user
                    primary.department.save()
            else:
                Department.objects.filter(head=updated_user).update(head=None)


        secondary_dept_id = request.data.get('secondary_department_id')
        secondary_unit=request.data.get('secondary_unit','')
        
        if secondary_dept_id:
            try:
                dept = Department.objects.get(id=int(secondary_dept_id))
                StaffDepartmentAssignment.objects.update_or_create(
                    user=updated_user,
                    department=dept,
                    defaults={
                        'role_in_dept': 'SECONDARY',
                        'unit':         secondary_unit,
                        'is_active':    True,
                    }
                )
            except Department.DoesNotExist:
                pass

        if request.accepted_renderer.format == 'html':
            return redirect('staff-list')
        return Response(serializer.data)

    
    @action(detail=True,methods=['post'],url_path='toggle-status')
    def toggle_status(self,request,pk=None):
        staff=self.get_object()
        if staff == request.user:
            return Response({'detail':'Cannot deactivate yourself.'},status=status.HTTP_400_BAD_REQUEST)
        staff.is_active = not staff.is_active
        staff.save()
        return Response({'is_active':staff.is_active})

    
    def perform_create(self, serializer):
        new_user=serializer.save()
        auto_assign_primary(new_user)
        def is_checked(field_name):
            return self.request.data.get(field_name)=='on'
        if new_user.role=='HRM':
            profile,created=HRManagerProfile.objects.get_or_create(user=new_user)
            profile.can_approve_leaves=is_checked('can_approve_leaves')
            profile.can_view_salaries=is_checked('can_view_salaries')
            profile.can_terminate_staff=is_checked('can_terminate_staff')
            profile.can_edit_attendance=is_checked('can_edit_attendance')
            profile.can_generate_payslips=is_checked('can_generate_payslips')
            profile.can_update_documents=is_checked('can_update_documents')
            profile.is_department_head=is_checked('is_department_head')
            profile.save()

        elif new_user.role=='REC':
            profile,_=ReceptionistProfile.objects.get_or_create(user=new_user)
            profile.can_register_patient=is_checked('can_register_patient')
            profile.can_access_billing=is_checked('can_access_billing')
            profile.can_modify_patient_records=is_checked('can_modify_patient_records')
            profile.can_schedule_appointment=is_checked('can_schedule_appointment')
            profile.is_department_head=is_checked('is_department_head')
            profile.save()
        
        elif new_user.role=='CCO':
            profile,_=ClinicalCounsellorProfile.objects.get_or_create(user=new_user)
            profile.is_department_head=is_checked('is_department_head')
            profile.save()
        
        elif new_user.role=='FCO':
            profile,_=FinancialCounsellorProfile.objects.get_or_create(user=new_user)
            profile.can_approve_discounts=is_checked('can_approve_discounts')
            profile.can_override_insurance=is_checked('can_override_insurance')
            profile.is_department_head=is_checked('is_department_head')
            profile.save()
        
        elif new_user.role=='END':
            profile,_=ReproductiveEndocrinologistProfile.objects.get_or_create(user=new_user)
            profile.can_perform_egg_retrieval=is_checked('can_perform_egg_retrieval')
            profile.can_perform_embryo_transfer=is_checked('can_perform_embryo_transfer')
            profile.can_design_ivf_protocols=is_checked('can_design_ivf_protocols')
            profile.is_department_head=is_checked('is_department_head')
            profile.save()

        elif new_user.role=='GYN':
            profile,_=GynaecologistProfile.objects.get_or_create(user=new_user)
            profile.can_perform_egg_retrieval=is_checked('can_perform_egg_retrieval')
            profile.can_assist_ivf=is_checked('can_assist_ivf')
            profile.is_department_head=is_checked('is_department_head')
            profile.save()

        elif new_user.role=='ANE':
            profile,_=AnesthesiologistProfile.objects.get_or_create(user=new_user)
            profile.edit_anesthesia_records=is_checked('edit_anesthesia_records')
            profile.is_department_head=is_checked('is_department_head')
            profile.save()
        
        elif new_user.role=='EMB':
            profile,_=EmbryologistProfile.objects.get_or_create(user=new_user)
            profile.can_perform_icsi=is_checked('can_perform_icsi')
            profile.can_perform_biopsy=is_checked('can_perform_biopsy')
            profile.is_department_head=is_checked('is_department_head')
            profile.save()
        
        elif new_user.role=='NUR':
            profile,_=NurseProfile.objects.get_or_create(user=new_user)
            profile.is_head_nurse=is_checked('is_head_nurse')
            profile.is_department_head=is_checked('is_department_head')
            profile.save()
        
        elif new_user.role=='PHA':
            profile,_=PharmacistProfile.objects.get_or_create(user=new_user)
            profile.can_manage_inventory=is_checked('can_manage_inventory')
            profile.is_department_head=is_checked('is_department_head')
            profile.save()
        
        elif new_user.role=='TEC':
            profile,_=LabTechnicianProfile.objects.get_or_create(user=new_user)
            profile.is_department_head=is_checked('is_department_head')
            profile.save()
        
        elif new_user.role=='AND':
            profile,_=AndrologyLabTechnician.objects.get_or_create(user=new_user)
            profile.can_perform_dna_frag=is_checked('can_perform_dna_frag')
            profile.can_perform_cryo=is_checked('can_perform_cryo')
            profile.is_department_head=is_checked('is_department_head')
            profile.save()


        staff_roles=['REC','CCO','FCO','END','GYN','EMB','ANE','NUR','PHA','TEC','AND','HRM','ADM']
        if new_user.role in staff_roles:
            admins_to_alert=AdminProfile.objects.filter(is_notified_on_new_user=True).select_related('user')
            recipient_list = [admin.user.email for admin in admins_to_alert if admin.user.email]
            if recipient_list:
                send_mail(subject="New Staff Account Created",
                          message=f"A new staff account has been created.\n\n"
                        f"Name: {new_user.full_name}\n"
                        f"Role: {new_user.get_role_display()}\n"
                        f"Email: {new_user.email}\n"
                        f"Onboarded by: {self.request.user.full_name}",
                          from_email=settings.DEFAULT_FROM_EMAIL,
                          recipient_list=recipient_list,
                          fail_silently=True
                          )



    def create(self,request,*args,**kwargs):
        response=super().create(request,*args,**kwargs)
        role=request.data.get('role')
        user_email=request.data.get('email')
        user=User.objects.get(email=user_email)
        if request.accepted_renderer.format == 'html':
            return redirect('staff-list')
        return response



    @action(detail=False, methods=['get'], url_path='dashboard')
    def dashboard(self, request):
        staff_count = User.objects.exclude(role__in=['PAT', 'DON']).count()
        cutoff=timezone.now() -timedelta(minutes=5)
        patient_today_count=User.objects.filter(role='PAT',date_joined__date=timezone.now().date()).count()
        raw_logs=(LoginAuditLog.objects
            .filter(
                is_active_session=True,
                last_seen__gte=cutoff
                )
            .select_related('user')
            .order_by('user_id','-login_time'))
        seen={}
        for log in raw_logs:
            if log.user_id not in seen:
                seen[log.user_id] = log

        active_sessions=[{
            'user__full_name':log.user.full_name,
            'user__email':log.user.email,
            'user__role':log.user.role,
            'login_time':log.login_time.isoformat() if log.login_time else None,
        } for log in seen.values()
        ][:20]
        new_patients=User.objects.filter(role='PAT',date_joined__date=timezone.now().date()).order_by('-date_joined').values('full_name', 'email', 'date_joined')[:20]
        
        return Response({
                'staff_count': staff_count,
                'active_count': len(active_sessions),
                'patient_today_count': patient_today_count,
                'active_sessions': active_sessions,
                'patients': list(new_patients),
                })

    @action(detail=False,methods=['get','post'], url_path='my-profile')
    def my_profile(self,request):
        user=request.user
        is_editing = request.GET.get('edit') == 'true'
        change_password = request.GET.get('password') == 'true'
        if request.method == 'GET':
            context={
                'user':user,
                'is_editing':is_editing,
                'change_password':change_password
                }
            if user.role=='HRM' :
                profile,_=HRManagerProfile.objects.get_or_create(user=user)
                profile.refresh_from_db()
                context['profile']=user.hr_profile
            elif user.role=='ADM':
                profile,_=AdminProfile.objects.get_or_create(user=user)
                context['profile']=user.admin_profile
            return Response(context,template_name='my_profile.html')

        if request.method == 'POST':
            # print(f"DEBUG: Data received: {request.data}")
            if 'new_password' in request.data:
                old_pass=request.data.get('old_password')
                new_pass=request.data.get('new_password')
                if user.check_password(old_pass):
                    user.set_password(new_pass)
                    user.save()
                    update_session_auth_hash(request,user)
                    return redirect('staff-my-profile')
                else:
                    return Response({'user':user,'error':'Incorrect Old Password'},template_name='my_profile.html')
            if user.role=='HRM':
                profile=user.hr_profile
                profile.managed_depts = request.data.get('managed_departments','')
                profile.contact_number = request.data.get('contact_number','')
                profile.save()
                # print(f"DEBUG: Saved to DB. New Depts: {profile.managed_depts}")
                profile.refresh_from_db()
            return redirect('staff-my-profile')

    @action(detail=False,methods=['get','post'],url_path='force-password-change',permission_classes=[IsAuthenticated])
    def force_password_change(self,request):
        next_url=request.GET.get('next')
        if request.method=='POST':
            new_password=request.data.get('new_password')
            confirm_password=request.data.get('confirm_password')
            if new_password==confirm_password:
                user=request.user
                user.set_password(new_password)
                user.has_changed_password=True
                user.save()

                update_session_auth_hash(request,user)
                return redirect(next_url)
            else:
                return Response({'error':'Passwords do not match'}, template_name='force_password_change.html')
        return Response({},template_name='force_password_change.html')
    
    @action(detail=True,methods=['get'],url_path='audit-log',url_name='audit-log')
    def audit_log(self,request,pk=None):
        staff=self.get_object()
        logs=staff.login_logs.all()
        return Response({'staff':staff,'logs':logs},template_name='staff_audit_log.html')

    @action(detail=False,methods=['post'],url_path='heartbeat',permission_classes=[IsAuthenticated])
    def heartbeat(self,request):
        LoginAuditLog.objects.filter(
            user=request.user,
            is_active_session=True).update(last_seen=timezone.now())
        return Response({'status':'ok'})
    
    @action(detail=False, methods=['get'], url_path='all-logs', url_name='all-logs')
    def all_audit_logs(self, request):
        latest_log = LoginAuditLog.objects.filter(user=OuterRef('user')).order_by('-login_time')
        logs = LoginAuditLog.objects.filter(
            id=Subquery(latest_log.values('id')[:1])
            ).select_related('user').order_by('-login_time')

        cutoff = timezone.now() - timedelta(seconds=60)
    
        data = []
        for log in logs:
            data.append({
                'user__full_name': log.user.full_name,
                'user__email': log.user.email,
                'user__role': log.user.role,
                'login_time': log.login_time.isoformat() if log.login_time else None,
                'is_active_session': log.is_active_session,
                'is_online': log.last_seen >= cutoff,
            })

        return Response({
            'logs': data,
            'total_logs': len(data),
            'active_now': sum(1 for l in data if l['is_active_session']),
            })
    
    @action(detail=False,methods=['get'],url_path='reg-report',url_name='reg-report')
    def registration_report(self,request):
        today=timezone.now().date()
        new_patients=User.objects.filter(role='PAT',date_joined__date=today).order_by('-date_joined')
        stats={'total_today':new_patients.count(),
               'by_gender':new_patients.values('patient_profile__gender').annotate(count=Count('id'))
               }
        if request.accepted_renderer.format=='html':
            return Response({
                'patients':new_patients,
                'report_date':today,
                'stats':stats
            },template_name='reports/registration_daily.html')
        return Response(AdminUserCreateSerializer(new_patients,many=True).data)

    @action(detail=True, methods=['get'], url_path='assignments')
    def assignments(self,request,pk=None):
        user=self.get_object()
        assignments=StaffDepartmentAssignment.objects.filter(
            user=user,
            is_active=True
        ).select_related('department')

        data=[
            {
                'id':a.id,
                'department':a.department.id,
                'department_name':a.department.name,
                'department_code':a.department.code,
                'role_in_dept':a.role_in_dept,
                'unit':a.unit,
                'is_active':a.is_active,
            }
            for a in assignments
        ]
        return Response(data)