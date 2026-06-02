from .models import User,AdminProfile,LoginAuditLog
from .serializer import AdminUserCreateSerializer,LoginSerializer
from rest_framework import viewsets,status
from rest_framework.permissions import IsAdminUser,IsAuthenticated,AllowAny
from django.core.mail import send_mail
from django.conf import settings
from rest_framework.parsers import FormParser,MultiPartParser
from rest_framework.decorators import action
from rest_framework.renderers import JSONRenderer, BrowsableAPIRenderer
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
from .models import User, LoginAuditLog, ROLES

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
    renderer_classes = [JSONRenderer,BrowsableAPIRenderer]

    @action(detail=False, methods=['get'], url_path='create-staff')
    def onboard(self, request):
        return Response({'message': 'Onboard API'})

    def get_queryset(self):
        return User.objects.exclude(role__in=['PAT','DON']).order_by('-date_joined')
    def list(self,request,*args,**kwargs):
        return super().list(request,*args,**kwargs)
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        staff = self.get_object()

        old_role = staff.role
        serializer = self.get_serializer(staff, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        updated_user = serializer.save()
        new_role = updated_user.role

        if old_role != new_role:
            handle_role_change(updated_user, old_role, new_role)
            auto_assign_primary(updated_user)

        StaffDepartmentAssignment.objects.filter(
            user=updated_user,
            role_in_dept__in=['SECONDARY', 'TEMPORARY'],
            is_active=True,
        ).update(is_active=False)

        # ── Role-specific permissions ──────────────────────────────────
        def get_bool(field): return request.data.get(field) == 'on'

        if updated_user.role == 'HRM' and hasattr(updated_user, 'hr_profile'):
            p = updated_user.hr_profile
            p.can_approve_leaves    = get_bool('can_approve_leaves')
            p.can_view_salaries     = get_bool('can_view_salaries')
            p.can_terminate_staff   = get_bool('can_terminate_staff')
            p.can_edit_attendance   = get_bool('can_edit_attendance')
            p.can_generate_payslips = get_bool('can_generate_payslips')
            p.can_update_documents  = get_bool('can_update_documents')
            p.is_department_head    = get_bool('is_department_head')
            p.save()

        elif updated_user.role == 'REC' and hasattr(updated_user, 'receptionist_profile'):
            p = updated_user.receptionist_profile
            p.can_register_patient      = get_bool('can_register_patient')
            p.can_access_billing        = get_bool('can_access_billing')
            p.can_modify_patient_records= get_bool('can_modify_patient_records')
            p.can_schedule_appointment  = get_bool('can_schedule_appointment')
            p.is_department_head        = get_bool('is_department_head')
            p.save()

        elif updated_user.role == 'CCO' and hasattr(updated_user, 'clinical_counsellor_profile'):
            p = updated_user.clinical_counsellor_profile
            p.is_department_head = get_bool('is_department_head')
            p.save()

        elif updated_user.role == 'FCO' and hasattr(updated_user, 'financial_counsellor_profile'):
            p = updated_user.financial_counsellor_profile
            p.can_approve_discounts  = get_bool('can_approve_discounts')
            p.can_override_insurance = get_bool('can_override_insurance')
            p.is_department_head     = get_bool('is_department_head')
            p.save()

        elif updated_user.role == 'END' and hasattr(updated_user, 'endocrinologist_profile'):
            p = updated_user.endocrinologist_profile
            p.can_perform_egg_retrieval   = get_bool('can_perform_egg_retrieval')
            p.can_perform_embryo_transfer = get_bool('can_perform_embryo_transfer')
            p.can_design_ivf_protocols    = get_bool('can_design_ivf_protocols')
            p.is_department_head          = get_bool('is_department_head')
            p.save()

        elif updated_user.role == 'GYN' and hasattr(updated_user, 'gynaec_profile'):
            p = updated_user.gynaec_profile
            p.can_perform_egg_retrieval = get_bool('can_perform_egg_retrieval')
            p.can_assist_ivf            = get_bool('can_assist_ivf')
            p.is_department_head        = get_bool('is_department_head')
            p.save()

        elif updated_user.role == 'ANE' and hasattr(updated_user, 'anesth_profile'):
            p = updated_user.anesth_profile
            p.can_edit_anesthesia_records = get_bool('can_edit_anesthesia_records')
            p.is_department_head          = get_bool('is_department_head')
            p.save()

        elif updated_user.role == 'EMB' and hasattr(updated_user, 'embryologist_profile'):
            p = updated_user.embryologist_profile
            p.can_perform_icsi   = get_bool('can_perform_icsi')
            p.can_perform_biopsy = get_bool('can_perform_biopsy')
            p.is_department_head = get_bool('is_department_head')
            p.save()

        elif updated_user.role == 'NUR' and hasattr(updated_user, 'nurse_profile'):
            p = updated_user.nurse_profile
            p.is_head_nurse      = get_bool('is_head_nurse')
            p.is_department_head = get_bool('is_department_head')
            p.save()

        elif updated_user.role == 'PHA' and hasattr(updated_user, 'pharmacist_profile'):
            p = updated_user.pharmacist_profile
            p.can_manage_inventory = get_bool('can_manage_inventory')
            p.is_department_head   = get_bool('is_department_head')
            p.save()

        elif updated_user.role == 'TEC' and hasattr(updated_user, 'technician_profile'):
            p = updated_user.technician_profile
            p.is_department_head = get_bool('is_department_head')
            p.save()

        elif updated_user.role == 'AND' and hasattr(updated_user, 'andrology_technician_profile'):
            p = updated_user.andrology_technician_profile
            p.can_perform_dna_frag = get_bool('can_perform_dna_frag')
            p.can_perform_cryo     = get_bool('can_perform_cryo')
            p.is_department_head   = get_bool('is_department_head')
            p.save()

        # ── Department head assignment 
        self.assign_department_head(updated_user, get_bool('is_department_head'))

        # ── Secondary department ──────────────────────────────────────
        secondary_dept_id = request.data.get('secondary_department_id')
        secondary_unit    = request.data.get('secondary_unit', '')
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
        return Response(serializer.data)
    
    @action(detail=True,methods=['post'],url_path='toggle-status')
    def toggle_status(self,request,pk=None):
        staff=self.get_object()
        if staff == request.user:
            return Response({'detail':'Cannot deactivate yourself.'},status=status.HTTP_400_BAD_REQUEST)
        staff.is_active = not staff.is_active
        staff.save()
        return Response({'is_active':staff.is_active})

    def assign_department_head(self,user,is_hod):
        if is_hod:
            primary = StaffDepartmentAssignment.objects.filter(
                user=user,
                role_in_dept='PRIMARY',
                is_active=True
            ).select_related('department').first()

            if primary:
                dept=primary.department
                from accounts.models import User as UserModel
                current_head=dept.head
                if current_head and current_head!=user:
                    for attr in ['receptionist_profile','hr_profile','clinical_counsellor_profile','financial_counsellor_profile','endocrinologist_profile','gynaec_profile','anesth_profile','embryologist_profile','nurse_profile','pharmacist_profile','technician_profile','andrology_technician_profile']:
                        if hasattr(current_head, attr):
                            profile=getattr(current_head,attr)
                            if hasattr(profile,'is_department_head'):
                                profile.is_department_head=False
                                profile.save()
                                break
                dept.head=user
                dept.save()
        else:
            Department.objects.filter(head=user).update(head=None)  
      
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
            profile.can_edit_anesthesia_records=is_checked('can_edit_anesthesia_records')
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
    
        is_hod = is_checked('is_department_head')
        self.assign_department_head(new_user, is_hod)

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
        return response



    @action(detail=False, methods=['get'], url_path='dashboard')
    def dashboard(self, request):
        from datetime import timedelta
        from django.utils import timezone
        from django.db.models import Count
        from departments.models import Department, StaffDepartmentAssignment
    
        # Staff counts
        staff_queryset = User.objects.exclude(role__in=['PAT', 'DON'])
    
        total_staff = staff_queryset.count()
        active_staff = staff_queryset.filter(is_active=True).count()
        inactive_staff = staff_queryset.filter(is_active=False).count()
    
        # Patient counts
        total_patients = User.objects.filter(role='PAT').count()
    
        patient_today_count = User.objects.filter(
            role='PAT',
            date_joined__date=timezone.now().date()
        ).count()
    
        # Department Heads
        departments_with_heads = Department.objects.filter(
            head__isnull=False
        ).select_related('head')
    
        hod_details = [
            {
                'department_id': dept.id,
                'department_name': dept.name,
                'department_code': dept.code,
                'head_id': dept.head.id,
                'head_name': dept.head.full_name,
                'head_email': dept.head.email,
                'head_role': dept.head.get_role_display(),
            }
            for dept in departments_with_heads
        ]
    
        # Online Staff
        cutoff = timezone.now() - timedelta(minutes=5)
    
        raw_logs = (
            LoginAuditLog.objects
            .filter(
                is_active_session=True,
                last_seen__gte=cutoff
            )
            .select_related('user')
            .order_by('user_id', '-login_time')
        )
    
        seen = {}
        for log in raw_logs:
            if log.user_id not in seen:
                seen[log.user_id] = log
    
        active_sessions = [{
            'user_id': log.user.id,
            'full_name': log.user.full_name,
            'email': log.user.email,
            'role': log.user.get_role_display(),
            'role_code': log.user.role,
            'login_time': log.login_time.isoformat() if log.login_time else None,
            'last_seen': log.last_seen.isoformat() if log.last_seen else None,
        } for log in seen.values()][:20]
    
        # Recent Patients
        new_patients = User.objects.filter(
            role='PAT',
            date_joined__date=timezone.now().date()
        ).order_by('-date_joined').values(
            'full_name',
            'email',
            'date_joined'
        )[:20]
    
        # Role Distribution
        role_distribution = []
    
        role_counts = (
            staff_queryset
            .values('role')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
    
        role_map = dict(ROLES)
    
        for item in role_counts:
            role_distribution.append({
                'role_code': item['role'],
                'role_display': role_map.get(item['role'], item['role']),
                'count': item['count'],
            })
    
        # Department-wise Staff Count
        department_staff_count = (
            StaffDepartmentAssignment.objects
            .filter(
                is_active=True,
                role_in_dept='PRIMARY'
            )
            .values('department__name')
            .annotate(count=Count('user'))
            .order_by('-count')
        )
    
        return Response({
            'summary': {
                'total_staff': total_staff,
                'active_staff': active_staff,
                'inactive_staff': inactive_staff,
                'online_staff': len(active_sessions),
                'total_patients': total_patients,
                'patient_today_count': patient_today_count,
                'total_hods': len(hod_details),
            },
    
            'department_heads': hod_details,
    
            'role_distribution': role_distribution,
    
            'active_sessions': active_sessions,
    
            'patients': list(new_patients),
    
            'top_departments': list(department_staff_count),
        })

    @action(detail=False,methods=['get','post'], url_path='my-profile')
    def my_profile(self,request):
        user=request.user
        is_editing = request.GET.get('edit') == 'true'
        change_password = request.GET.get('password') == 'true'
        if request.method == 'GET':
            context={
                'id': user.id,
                'email': user.email,
                'full_name': user.full_name,
                'role': user.role,
                }
            if user.role=='HRM' :
                profile,_=HRManagerProfile.objects.get_or_create(user=user)
                profile.refresh_from_db()
                context['managed_depts'] = getattr(profile, 'managed_depts', '')
            return Response(context)

        if request.method == 'POST':
            if 'new_password' in request.data:
                old_pass=request.data.get('old_password')
                new_pass=request.data.get('new_password')
                if user.check_password(old_pass):
                    user.set_password(new_pass)
                    user.save()
                    update_session_auth_hash(request,user)
                    return Response({'message': 'Password updated successfully'})
                else:
                    return Response({'error':'Incorrect Old Password'}, status=400)
            if user.role=='HRM':
                profile=user.hr_profile
                profile.managed_depts = request.data.get('managed_departments','')
                profile.contact_number = request.data.get('contact_number','')
                profile.save()
                profile.refresh_from_db()
            return Response({'message': 'Profile updated successfully'})

    @action(detail=False,methods=['post'],url_path='force-password-change',permission_classes=[IsAuthenticated])
    def force_password_change(self,request):
        new_password=request.data.get('new_password')
        confirm_password=request.data.get('confirm_password')
        if new_password==confirm_password:
            user=request.user
            user.set_password(new_password)
            user.has_changed_password=True
            user.save()

            update_session_auth_hash(request,user)
            return Response({'message': 'Password changed successfully'})
        else:
            return Response({'error':'Passwords do not match'}, status=400)
    
    @action(detail=True,methods=['get'],url_path='audit-log',url_name='audit-log')
    def audit_log(self,request,pk=None):
        staff=self.get_object()
        logs=staff.login_logs.all()
        log_data = [{'login_time': log.login_time, 'logout_time': log.logout_time, 'ip_address': log.ip_address} for log in logs]
        return Response({'staff_id': staff.id, 'logs': log_data})

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
        data = AdminUserCreateSerializer(new_patients,many=True).data
        return Response({'patients': data, 'stats': stats, 'report_date': today})

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