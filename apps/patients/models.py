from django.db import models
from django.conf import settings
from django.utils.text import slugify
from datetime import date

TREATMENT_TYPES=[
    ('IVF','In Vitro Fertilization(IVF)'),
    ('IUI','IntraUterine Insemination(IUI)'),
    ('FET','Frozen Embryo Transfer(FET)'),
    ('ICSI','IntraCytoplasmic Sperm Injection(ICSI)'),
    ('OI','Ovulation Induction'),
    ('IVM','In Vitro Maturation'),
    ('EGG_FREEZE','Egg Freezing'),
    ('EMBRYO_FREEZE','Embryo Freezing'),
    ('SPERM_FREEZE','Sperm Freeze'),
    ('PGT','Preimplantation Genetic Testing(PGT)'),
    ('OTHER','Other'),
]

PATIENT_STATUS=[
    ('PEN','Pending'),
    ('ACT','Active Treatment'),
    ('HOL','On Hold'),
    ('COM','Completed'),
    ('CAN','Cancelled'),
]

GENDER_CHOICES=[
    ('M','Male'),
    ('F','Female'),
    ('O','Other'),
]

BLOOD_GROUP_CHOICES=[
    ('A+','A+'),('A-','A-'),
    ('B+','B+'),('B-','B-'),
    ('O+','O+'),('O-','O-'),
    ('AB+','AB+'),('AB-','AB-')
    ]


class PatientProfile(models.Model):
    user=models.OneToOneField(to=settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='patient_profile')
    patient_id=models.CharField(max_length=20,unique=True, blank=True,help_text='PT001')
    slug=models.SlugField(unique=True, blank=True)

    #Basic Info
    phone=models.CharField(max_length=15,blank=True)
    date_of_birth=models.DateField(blank=True,null=True)
    gender = models.CharField(max_length=1,choices=GENDER_CHOICES,default='O')
    blood_group=models.CharField(max_length=3,choices=BLOOD_GROUP_CHOICES, blank=True)
    address = models.TextField(blank=True)
    insurance_policy_number=models.CharField(max_length=50,blank=True)
    insurance_details=models.TextField(blank=True)
    emergency_contact_name= models.CharField(max_length=100,blank=True)
    emergency_contact_phone=models.CharField(max_length=15,blank=True)

    #Treatment
    treatment_type=models.CharField(max_length=20,choices=TREATMENT_TYPES,blank=True)
    status=models.CharField(max_length=3,choices=PATIENT_STATUS,default='PEN')
    assigned_doctor=models.ForeignKey(
        to=settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,blank=True, 
        related_name='assigned_patients', 
        limit_choices_to={'role__in':['GYN','END']},
        )
    
    #Couple Linkage
    partner=models.OneToOneField(to='self',on_delete=models.SET_NULL,blank=True,null=True,related_name='partner_of')

    years_of_infertility=models.PositiveIntegerField(default=0,blank=True)
    previous_ivf_attempts=models.PositiveIntegerField(default=0,blank=True)
    known_allergies=models.TextField(blank=True)
    
    #Timestamps
    registered_on=models.DateField(auto_now_add=True)
    updated_on=models.DateTimeField(auto_now=True)
    notes=models.TextField(blank=True)

    is_active=models.BooleanField(default=True)
    class Meta:
        ordering = ['-registered_on']

    def save(self,*args,**kwargs):
        if not self.patient_id:
            last_profile = PatientProfile.objects.order_by('-id').first()

            if not last_profile:
                self.patient_id = "PAT001"
            else:
                last_id = int(last_profile.patient_id.replace("PAT", ""))
                new_id = last_id + 1
                self.patient_id = f"PAT{new_id:03d}"
        if not self.slug:
            base = slugify(self.user.full_name)
            self.slug = f'{base}-{self.patient_id.lower()}'
        super().save(*args,**kwargs)
    
    def __str__(self):
        return f"Patient:{self.patient_id} — {self.user.full_name}"

    @property
    def age(self):
        if not self.date_of_birth:
            return None
        today=date.today()
        dob=self.date_of_birth
        return today.year - dob.year - ((today.month,today.day)<(dob.month,dob.day))

