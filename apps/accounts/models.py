from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django.contrib.auth.models import BaseUserManager,AbstractBaseUser,PermissionsMixin
from django.core.validators import MinValueValidator
from django.utils import timezone

ROLES=[
    ('REC','Receptionist'),
    ('CCO','Clinical Counsellor'),
    ('FCO','Financial Counsellor'),
    ('END','Reproductive Endocrinologist'),
    ('GYN','Gynaecologist'),
    ('ANE','Anesthesiologist'),
    ('EMB','Embryologist'),
    ('NUR','Nurse'),
    ('PHA','Pharmacist'),
    ('TEC','Lab Technician'),
    ('AND','Andrology Lab Technician'),
    ('PAT','Patient'),
    ('HRM','HR Manager'),
    ('ADM','Admin')
]

class UserManager(BaseUserManager):
    def create_user(self,email,password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email=self.normalize_email(email)
        user=self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    def create_superuser(self,email,password=None, **extra_fields):
        extra_fields.setdefault('is_staff',True)
        extra_fields.setdefault('is_superuser',True)
        extra_fields.setdefault('role', 'ADM')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email,password, **extra_fields)

class User(AbstractBaseUser,PermissionsMixin):
    email=models.EmailField(unique=True)
    full_name=models.CharField(max_length=255)
    role=models.CharField(max_length=3,choices=ROLES,default='PAT')
    has_changed_password=models.BooleanField(default=False)
    is_active=models.BooleanField(default=True)
    is_staff=models.BooleanField(default=False)
    date_joined=models.DateTimeField(auto_now_add=True)

    objects= UserManager()

    USERNAME_FIELD='email'
    REQUIRED_FIELDS=['full_name','role']

    def save(self, *args, **kwargs):
        if self.role =='ADM':
            self.is_staff=True
        super().save(*args,**kwargs)

    def __str__(self):
        return f"{self.email} ({self.role})"

class ReceptionistProfile(models.Model):
    user=models.OneToOneField(to=settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='receptionist_profile')
    employee_id=models.CharField(max_length=20, unique=True, blank=True,help_text='RC001')
    slug=models.SlugField(unique=True, blank=True)

    desk_location=models.CharField(max_length=100, blank=True,help_text="Eg: Main Entrance")
    contact_number=models.CharField(max_length=15)
    
    can_register_patient=models.BooleanField(default=True)
    can_access_billing = models.BooleanField(default=True)
    can_modify_patient_records = models.BooleanField(default=False, help_text="Usually restricted to medical staff")
    can_schedule_appointment=models.BooleanField(default=True)
    is_department_head=models.BooleanField(default=False)



    is_active=models.BooleanField(default=True)
    date_assigned=models.DateField(auto_now_add=True)

    def save(self,*args,**kwargs):
        if not self.employee_id:
            last_profile = ReceptionistProfile.objects.order_by('-id').first()
            if not last_profile:
                self.employee_id = "RC001"
            else:
                last_id = int(last_profile.employee_id.replace("RC", ""))
                new_id = last_id + 1
                self.employee_id = f"RC{new_id:03d}"
        if not self.slug:
            base_slug = slugify(self.user.full_name)
            self.slug = f"{base_slug}-{self.employee_id.lower()}"
        super().save(*args,**kwargs)
    def __str__(self):
        return f"Receptionist: {self.user.full_name}"

class ClinicalCounsellorProfile(models.Model):
    user=models.OneToOneField(to=settings.AUTH_USER_MODEL,on_delete=models.CASCADE, related_name='clinical_counsellor_profile')
    employee_id=models.CharField(max_length=20,unique=True,blank=True,help_text='CO001')    
    slug=models.SlugField(unique=True,blank=True)

    medical_license_number=models.CharField(max_length=50,blank=True)
    specialization=models.CharField(max_length=100,default="Fertility & IVF Counseling")
    years_of_exp=models.PositiveIntegerField(validators=[MinValueValidator(0)],default=0)
    biography=models.TextField(blank=True,null=True)

    is_department_head=models.BooleanField(default=False)

    is_active=models.BooleanField(default=True)
    date_joined=models.DateField(auto_now_add=True)

    def save(self,request,*args,**kwargs):
        if not self.employee_id:
            last_profile=ClinicalCounsellorProfile.objects.order_by('-id').first()
            if not last_profile:
                self.employee_id='CO001'
            else:
                last_id=int(last_profile.employee_id.replace("CO",""))
                new_id=last_id+1
                self.employee_id=f"CO{new_id:03d}"
        if not self.slug:
            base_slug=slugify(self.user.full_name)
            self.slug=f"{base_slug}-{self.employee_id.lower()}"
        super().save(*args,**kwargs)
    def __str__(self):
        return f"Clinical Counsellor: {self.user.full_name}"

class FinancialCounsellorProfile(models.Model):
    user=models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='financial_counsellor_profile')
    employee_id=models.CharField(max_length=50,unique=True,blank=True,help_text="FO001")
    slug=models.SlugField(unique=True,blank=True)

    specialization=models.CharField(max_length=100,blank=True)

    can_approve_discounts=models.BooleanField(default=False)
    can_override_insurance=models.BooleanField(default=False)
    is_department_head=models.BooleanField(default=False)

    is_active=models.BooleanField(default=True)
    # last_audit_performed=models.DateField(null=True,blank=True)
    def save(self,request,*args,**kwargs):
        if not self.employee_id:
            last_profile=FinancialCounsellorProfile.objects.order_by('-id').first()
            if not last_profile:
                self.employee_id="FO001"
            else:
                last_id=int(last_profile.employee_id.replace("FO",""))
                new_id=last_id+1
                self.employee_id=f"FO{new_id:03d}"
        if not self.slug:
            base_slug=slugify(self.user.full_name)
            self.slug=f"{base_slug}-{self.employee_id.lower()}"
        super().save(*args,**kwargs)
    def __str__(self):
        return f"Financial Counsellor: {self.user.full_name}"


class AnesthesiologistProfile(models.Model):
    user=models.OneToOneField(to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='anesth_profile')
    employee_id=models.CharField(max_length=20, unique=True, blank=True,help_text='AN001')
    slug=models.SlugField(unique=True, blank=True)

    specialization=models.CharField(max_length=100, blank=True)
    medical_license_no=models.CharField(max_length=50, blank=True)
    emergency_contact_info=models.TextField(blank=True,null=True)

    #capability
    edit_anesthesia_records=models.BooleanField(default=False)
    is_department_head=models.BooleanField(default=False)

    is_active=models.BooleanField(default=True)
    date_assigned=models.DateField(auto_now_add=True)
    def save(self,*args,**kwargs):
        if not self.employee_id:
            last_profile = AnesthesiologistProfile.objects.order_by('-id').first()
            if not last_profile:
                self.employee_id = "AN001"
            else:
                last_id = int(last_profile.employee_id.replace("AN", ""))
                new_id = last_id + 1
                self.employee_id = f"AN{new_id:03d}"
        if not self.slug:
            base_slug = slugify(self.user.full_name)
            self.slug = f"{base_slug}-{self.employee_id.lower()}"
        super().save(*args,**kwargs)

    def __str__(self):
        return f"Dr. {self.user.full_name} (Anasthesiologist)"

class EmbryologistProfile(models.Model):
    user=models.OneToOneField(to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE,related_name='embryologist_profile')
    employee_id=models.CharField(max_length=20, unique=True, blank=True,help_text='EM001')
    slug=models.SlugField(unique=True, blank=True)

    certification_body=models.CharField(max_length=100, blank=True)
    license_number=models.CharField(max_length=50, blank=True)

    can_perform_icsi=models.BooleanField(default=False, blank=True)
    can_perform_biopsy=models.BooleanField(default=False, blank=True)
    is_department_head=models.BooleanField(default=False)

    
    is_active=models.BooleanField(default=True)
    date_assigned=models.DateField(auto_now_add=True)
    def save(self,*args,**kwargs):
        if not self.employee_id:
            last_profile = EmbryologistProfile.objects.order_by('-id').first()
            if not last_profile:
                self.employee_id = "EM001"
            else:
                last_id = int(last_profile.employee_id.replace("EM", ""))
                new_id = last_id + 1
                self.employee_id = f"EM{new_id:03d}"
        if not self.slug:
            base_slug = slugify(self.user.full_name)
            self.slug = f"{base_slug}-{self.employee_id.lower()}"
        super().save(*args,**kwargs)
    def __str__(self):
        return f"Embryologist: {self.user.full_name}"

class NurseProfile(models.Model):
    user=models.OneToOneField(to=settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="nurse_profile")
    employee_id=models.CharField(max_length=20, unique=True, blank=True,help_text='NR001')
    slug=models.SlugField(unique=True, blank=True)

    nursing_license_no=models.CharField(max_length=50, blank=True)
    department=models.CharField(max_length=100, blank=True)

    is_head_nurse=models.BooleanField(default=False, blank=True)
    is_department_head=models.BooleanField(default=False)


    is_active=models.BooleanField(default=True)
    date_assigned=models.DateField(auto_now_add=True)

    def save(self,*args,**kwargs):
        if not self.employee_id:
            last_profile = NurseProfile.objects.order_by('-id').first()
            if not last_profile:
                self.employee_id = "NR001"
            else:
                last_id = int(last_profile.employee_id.replace("NR", ""))
                new_id = last_id + 1
                self.employee_id = f"NR{new_id:03d}"
        if not self.slug:
            base_slug = slugify(self.user.full_name)
            self.slug = f"{base_slug}-{self.employee_id.lower()}"
        super().save(*args,**kwargs)
    
    def __str__(self):
        return f"Nurse {self.user.full_name} ({self.department})"

class AdminProfile(models.Model):
    user=models.OneToOneField(to=settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='admin_profile')

    employee_id=models.CharField(max_length=20,unique=True, blank=True)
    department=models.CharField(max_length=50, blank=True,default='Administration')

    #1=View only , 2=Add/edit , 3=Delete/system
    ACCESS_CHOICES=[(1,'viewer'),(2,'Manager'),(3,'Super Admin')]
    access_level = models.PositiveSmallIntegerField(choices=ACCESS_CHOICES,default=1)
    # Audit trail for system changes
    is_notified_on_new_user = models.BooleanField(default=True)   #signals
    last_system_audit_date = models.DateTimeField(null=True, blank=True) #

    def __str__(self):
        return f"Admin: {self.user.full_name} ({self.employee_id})"

class LoginAuditLog(models.Model):
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='login_logs')

    login_time=models.DateTimeField(auto_now_add=True)
    logout_time=models.DateTimeField(null=True,blank=True)
    ip_address=models.GenericIPAddressField(null=True,blank=True)
    user_agent=models.TextField(null=True,blank=True)
    last_seen=models.DateTimeField(default=timezone.now)
    
    is_active_session=models.BooleanField(default=True)
    class Meta:
        ordering= ['-login_time']