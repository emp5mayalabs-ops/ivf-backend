# apps/nurse/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import viewsets
from rest_framework.decorators import action
from django.contrib.auth import login, logout
from django.utils import timezone
from django.db.models import Q, Count, Avg
from datetime import timedelta, datetime
import logging

from accounts.models import NurseProfile, LoginAuditLog
from patients.models import PatientProfile
from .models import PatientVital, PatientVitalHistory
from .serializers import (
    NurseLoginSerializer, 
    NurseProfileSerializer,
    NurseProfileUpdateSerializer,
    NurseProfileListSerializer,
    PatientVitalSerializer,
    PatientVitalListSerializer,
    PatientVitalCreateUpdateSerializer
)
from .permissions import IsNurse, IsHeadNurse, IsNurseOrAdmin

logger = logging.getLogger(__name__)


# ========== HELPER FUNCTIONS ==========

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


# ========== AUTH VIEWS ==========

class NurseLoginView(APIView):
    """
    POST /api/nurse/login/
    Nurse Login API
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = NurseLoginSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                {
                    'success': False,
                    'message': 'Invalid input',
                    'errors': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = serializer.validated_data['user']
        login(request, user)
        
        # Update login audit log
        try:
            LoginAuditLog.objects.filter(
                user=user,
                is_active_session=True
            ).update(is_active_session=False, logout_time=timezone.now())
            
            LoginAuditLog.objects.create(
                user=user,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                is_active_session=True
            )
        except Exception as e:
            logger.error(f"Login audit log error: {str(e)}")
        
        nurse_profile = user.nurse_profile
        
        return Response({
            'success': True,
            'message': 'Login successful',
            'user': {
                'id': user.id,
                'name': user.full_name,
                'email': user.email,
                'role': user.role,
                'role_display': 'Nurse',
                'nurse_id': getattr(nurse_profile, 'employee_id', f"NURSE-{user.id:04d}"),
                'is_head_nurse': getattr(nurse_profile, 'is_head_nurse', False),
                'is_department_head': getattr(nurse_profile, 'is_department_head', False),
                'is_active': getattr(nurse_profile, 'is_active', True),
            }
        }, status=status.HTTP_200_OK)


class NurseLogoutView(APIView):
    """
    POST /api/nurse/logout/
    Nurse Logout API
    """
    permission_classes = [IsAuthenticated, IsNurse]
    
    def post(self, request):
        # Update login audit log
        try:
            LoginAuditLog.objects.filter(
                user=request.user,
                is_active_session=True
            ).update(
                is_active_session=False,
                logout_time=timezone.now()
            )
        except Exception as e:
            logger.error(f"Logout audit log error: {str(e)}")
        
        logout(request)
        
        return Response({
            'success': True,
            'message': 'Logged out successfully'
        }, status=status.HTTP_200_OK)


class NurseProfileView(APIView):
    """
    GET /api/nurse/profile/
    Get current nurse's profile
    
    PUT /api/nurse/profile/
    Update current nurse's profile
    """
    permission_classes = [IsAuthenticated, IsNurse]
    
    def get(self, request):
        user = request.user
        nurse_profile = user.nurse_profile
        
        return Response({
            'success': True,
            'profile': NurseProfileSerializer(nurse_profile).data
        }, status=status.HTTP_200_OK)
    
    def put(self, request):
        user = request.user
        nurse_profile = user.nurse_profile
        
        serializer = NurseProfileUpdateSerializer(
            nurse_profile, 
            data=request.data,
            partial=True
        )
        
        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        nurse_profile = serializer.save()
        
        return Response({
            'success': True,
            'message': 'Profile updated successfully',
            'profile': NurseProfileSerializer(nurse_profile).data
        }, status=status.HTTP_200_OK)


class NurseProfileDetailView(APIView):
    """
    GET /api/nurse/profile/{id}/
    Get nurse profile by ID (for admin/head nurse)
    """
    permission_classes = [IsAuthenticated, IsNurseOrAdmin]
    
    def get(self, request, nurse_id):
        try:
            nurse_profile = NurseProfile.objects.get(id=nurse_id)
        except NurseProfile.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Nurse not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        return Response({
            'success': True,
            'profile': NurseProfileSerializer(nurse_profile).data
        }, status=status.HTTP_200_OK)


# ========== NURSE VIEWSET ==========

class NurseViewSet(viewsets.ModelViewSet):
    """
    GET    /api/nurse/list/           - List all nurses
    GET    /api/nurse/list/{id}/      - Get specific nurse
    PUT    /api/nurse/list/{id}/      - Update nurse
    DELETE /api/nurse/list/{id}/      - Delete nurse
    """
    queryset = NurseProfile.objects.select_related('user').all()
    permission_classes = [IsAuthenticated, IsNurseOrAdmin]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return NurseProfileListSerializer
        return NurseProfileSerializer
    
    def get_queryset(self):
        queryset = self.queryset
        
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(user__full_name__icontains=search) |
                Q(user__email__icontains=search) |
                Q(employee_id__icontains=search)
            )
        
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        is_head = self.request.query_params.get('is_head_nurse')
        if is_head is not None:
            queryset = queryset.filter(is_head_nurse=is_head.lower() == 'true')
        
        return queryset.order_by('-id')
    
    @action(detail=True, methods=['post'], url_path='toggle-status')
    def toggle_status(self, request, pk=None):
        nurse = self.get_object()
        
        if nurse.user == request.user:
            return Response({
                'error': 'Cannot deactivate yourself'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        nurse.is_active = not nurse.is_active
        nurse.save()
        nurse.user.is_active = nurse.is_active
        nurse.user.save()
        
        return Response({
            'success': True,
            'is_active': nurse.is_active,
            'message': f"Nurse {'activated' if nurse.is_active else 'deactivated'} successfully"
        })
    
    @action(detail=False, methods=['get'], url_path='stats')
    def get_stats(self, request):
        total = NurseProfile.objects.count()
        active = NurseProfile.objects.filter(is_active=True).count()
        inactive = NurseProfile.objects.filter(is_active=False).count()
        head_nurses = NurseProfile.objects.filter(is_head_nurse=True).count()
        
        return Response({
            'success': True,
            'stats': {
                'total_nurses': total,
                'active_nurses': active,
                'inactive_nurses': inactive,
                'head_nurses': head_nurses,
            }
        })


# ========== PATIENT VITAL VIEWS ==========

class PatientVitalViewSet(viewsets.ModelViewSet):
    """
    GET    /api/nurse/vitals/              - List all vitals
    POST   /api/nurse/vitals/              - Create new vital record
    GET    /api/nurse/vitals/{id}/         - Get vital detail
    PUT    /api/nurse/vitals/{id}/         - Update vital
    PATCH  /api/nurse/vitals/{id}/         - Partial update vital
    DELETE /api/nurse/vitals/{id}/         - Delete vital
    GET    /api/nurse/vitals/patients/     - List all patients
    GET    /api/nurse/vitals/patient/{id}/ - Get patient's vitals
    GET    /api/nurse/vitals/stats/        - Get vital statistics
    GET    /api/nurse/vitals/my-patients/  - Get my patients
    GET    /api/nurse/vitals/{id}/emr/     - Get EMR record for vital
    DELETE /api/nurse/vitals/delete-all/   - Delete all vitals (head nurse only)
    """
    queryset = PatientVital.objects.select_related(
        'patient', 'patient__user', 'nurse', 'nurse__user'
    ).all()
    permission_classes = [IsAuthenticated, IsNurse]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return PatientVitalListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return PatientVitalCreateUpdateSerializer
        return PatientVitalSerializer
    
    def get_queryset(self):
        queryset = self.queryset
        nurse_profile = self.request.user.nurse_profile
        
        # Filter by nurse (only see their own records unless head nurse)
        if not nurse_profile.is_head_nurse and not nurse_profile.is_department_head:
            queryset = queryset.filter(nurse=nurse_profile)
        
        # Filter by patient
        patient_id = self.request.query_params.get('patient')
        if patient_id:
            queryset = queryset.filter(patient_id=patient_id)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            try:
                start = datetime.strptime(start_date, '%Y-%m-%d')
                queryset = queryset.filter(recorded_at__date__gte=start)
            except ValueError:
                pass
        
        if end_date:
            try:
                end = datetime.strptime(end_date, '%Y-%m-%d')
                queryset = queryset.filter(recorded_at__date__lte=end)
            except ValueError:
                pass
        
        # Filter by emergency
        is_emergency = self.request.query_params.get('is_emergency')
        if is_emergency is not None:
            queryset = queryset.filter(is_emergency=is_emergency.lower() == 'true')
        
        # Search by patient name
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(patient__user__full_name__icontains=search) |
                Q(patient__user__email__icontains=search)
            )
        
        return queryset.order_by('-recorded_at')
    
    def perform_create(self, serializer):
        """Create vital record and auto-create EMR Nursing Note"""
        vital = serializer.save(nurse=self.request.user.nurse_profile)
        
        # Auto-create EMR Nursing Note if EMR app exists
        try:
            self.create_emr_nursing_note(vital)
        except Exception as e:
            logger.error(f"Failed to create EMR nursing note: {str(e)}")
        
        return vital
    
    def perform_update(self, serializer):
        """Update vital record and update EMR Nursing Note"""
        vital = self.get_object()
        updated_vital = serializer.save()
        
        # Update EMR Nursing Note if EMR app exists
        try:
            self.update_emr_nursing_note(updated_vital)
        except Exception as e:
            logger.error(f"Failed to update EMR nursing note: {str(e)}")
        
        return updated_vital
    
    def create_emr_nursing_note(self, vital):
        """
        Create EMR Nursing Note from vitals - Matches your EMR NursingNote model
        Your NursingNote model uses: vital_bp, vital_pulse, vital_temp, vital_spo2, vital_weight
        """
        try:
            from emr.models import EMRRecord, NursingNote
            
            # Format vitals as a note
            note_content = self.format_vitals_note(vital)
            
            # Format vitals for your NursingNote model (CharFields)
            vital_bp = ""
            if vital.blood_pressure_systolic and vital.blood_pressure_diastolic:
                vital_bp = f"{vital.blood_pressure_systolic}/{vital.blood_pressure_diastolic} mmHg"
            
            vital_pulse = f"{vital.heart_rate} bpm" if vital.heart_rate else ""
            vital_temp = f"{vital.temperature} °F" if vital.temperature else ""
            vital_spo2 = f"{vital.oxygen_saturation}%" if vital.oxygen_saturation else ""
            vital_weight = f"{vital.weight} kg" if vital.weight else ""
            
            # Combine observations
            observations = vital.notes or ""
            if vital.respiratory_rate:
                observations += f"\nRespiratory Rate: {vital.respiratory_rate} breaths/min"
            if vital.blood_sugar:
                observations += f"\nBlood Sugar: {vital.blood_sugar} mg/dL"
            if vital.bmi:
                observations += f"\nBMI: {vital.bmi}"
            if vital.pain_score is not None:
                observations += f"\nPain Score: {vital.pain_score}/10"
            
            # Create EMR Record
            emr_record = EMRRecord.objects.create(
                patient=vital.patient,
                record_type='NURSING_NOTE',
                title=f"Nursing Vitals - {vital.recorded_at.strftime('%Y-%m-%d %H:%M')}",
                date=vital.recorded_at.date(),
                notes=note_content,
                created_by=vital.nurse.user,
            )
            
            logger.info(f"EMR Record created: {emr_record.id}")
            
            # Create Nursing Note using your model fields
            NursingNote.objects.create(
                record=emr_record,
                vital_bp=vital_bp,
                vital_pulse=vital_pulse,
                vital_temp=vital_temp,
                vital_spo2=vital_spo2,
                vital_weight=vital_weight,
                observations=observations,
                medications_given=vital.medications_given or "",
                instructions_given=""
            )
            
            logger.info(f"Nursing Note created for patient {vital.patient.id}")
            
        except ImportError:
            logger.warning("EMR app not installed, skipping nursing note creation")
        except Exception as e:
            logger.error(f"Error creating EMR nursing note: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
    
    def update_emr_nursing_note(self, vital):
        """
        Update EMR Nursing Note from vitals - Matches your EMR NursingNote model
        """
        try:
            from emr.models import EMRRecord, NursingNote
            
            # Find the EMR record for this vital
            emr_record = EMRRecord.objects.filter(
                patient=vital.patient,
                record_type='NURSING_NOTE',
                created_by=vital.nurse.user,
                date=vital.recorded_at.date()
            ).order_by('-created_at').first()
            
            if emr_record:
                logger.info(f"Found EMR record: {emr_record.id}")
                
                # Update the nursing note
                nursing_note = NursingNote.objects.filter(record=emr_record).first()
                if nursing_note:
                    logger.info(f"Found Nursing Note: {nursing_note.id}")
                    
                    # Format vitals for your NursingNote model
                    vital_bp = ""
                    if vital.blood_pressure_systolic and vital.blood_pressure_diastolic:
                        vital_bp = f"{vital.blood_pressure_systolic}/{vital.blood_pressure_diastolic} mmHg"
                    
                    vital_pulse = f"{vital.heart_rate} bpm" if vital.heart_rate else ""
                    vital_temp = f"{vital.temperature} °F" if vital.temperature else ""
                    vital_spo2 = f"{vital.oxygen_saturation}%" if vital.oxygen_saturation else ""
                    vital_weight = f"{vital.weight} kg" if vital.weight else ""
                    
                    # Combine observations
                    observations = vital.notes or ""
                    if vital.respiratory_rate:
                        observations += f"\nRespiratory Rate: {vital.respiratory_rate} breaths/min"
                    if vital.blood_sugar:
                        observations += f"\nBlood Sugar: {vital.blood_sugar} mg/dL"
                    if vital.bmi:
                        observations += f"\nBMI: {vital.bmi}"
                    if vital.pain_score is not None:
                        observations += f"\nPain Score: {vital.pain_score}/10"
                    
                    nursing_note.vital_bp = vital_bp
                    nursing_note.vital_pulse = vital_pulse
                    nursing_note.vital_temp = vital_temp
                    nursing_note.vital_spo2 = vital_spo2
                    nursing_note.vital_weight = vital_weight
                    nursing_note.observations = observations
                    nursing_note.medications_given = vital.medications_given or ""
                    nursing_note.save()
                    
                    # Update EMR record notes
                    emr_record.notes = self.format_vitals_note(vital)
                    emr_record.save()
                    
                    logger.info(f"EMR Nursing Note updated for patient {vital.patient.id}")
                else:
                    logger.warning(f"No Nursing Note found for EMR record: {emr_record.id}")
            else:
                logger.warning(f"No EMR record found for patient {vital.patient.id} on date {vital.recorded_at.date()}")
                    
        except ImportError:
            logger.warning("EMR app not installed, skipping nursing note update")
        except Exception as e:
            logger.error(f"Error updating EMR nursing note: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
    
    def format_vitals_note(self, vital):
        """Format vitals as a readable note"""
        note_parts = []
        
        if vital.blood_pressure_systolic and vital.blood_pressure_diastolic:
            note_parts.append(f"🩸 BP: {vital.blood_pressure_systolic}/{vital.blood_pressure_diastolic} mmHg")
        if vital.heart_rate:
            note_parts.append(f"💓 Heart Rate: {vital.heart_rate} bpm")
        if vital.respiratory_rate:
            note_parts.append(f"🫁 Respiratory Rate: {vital.respiratory_rate} breaths/min")
        if vital.temperature:
            note_parts.append(f"🌡️ Temperature: {vital.temperature}°F")
        if vital.blood_sugar:
            note_parts.append(f"🩸 Blood Sugar: {vital.blood_sugar} mg/dL")
        if vital.weight:
            note_parts.append(f"⚖️ Weight: {vital.weight} kg")
        if vital.bmi:
            note_parts.append(f"📊 BMI: {vital.bmi}")
        if vital.oxygen_saturation:
            note_parts.append(f"💨 SpO2: {vital.oxygen_saturation}%")
        if vital.pain_score is not None:
            note_parts.append(f"😖 Pain Score: {vital.pain_score}/10")
        
        note = "**Vital Signs Recorded**\n\n" + "\n".join(note_parts)
        
        if vital.notes:
            note += f"\n\n📝 Notes: {vital.notes}"
        
        if vital.medications_given:
            note += f"\n\n💊 Medications Given: {vital.medications_given}"
        
        if vital.is_emergency:
            note += "\n\n⚠️ **EMERGENCY ALERT!**"
        
        return note
    
    @action(detail=True, methods=['post'], url_path='mark-emergency')
    def mark_emergency(self, request, pk=None):
        """Mark a vital record as emergency"""
        vital = self.get_object()
        vital.is_emergency = True
        vital.save()
        
        # Update EMR if exists
        try:
            self.update_emr_nursing_note(vital)
        except Exception as e:
            logger.error(f"Failed to update EMR for emergency: {str(e)}")
        
        return Response({
            'success': True,
            'message': 'Marked as emergency',
            'data': PatientVitalSerializer(vital).data
        })
    
    @action(detail=False, methods=['get'], url_path='patient/(?P<patient_id>[^/.]+)')
    def patient_vitals(self, request, patient_id=None):
        """Get all vitals for a specific patient"""
        try:
            patient = PatientProfile.objects.get(id=patient_id)
        except PatientProfile.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Patient not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        vitals = PatientVital.objects.filter(patient=patient).order_by('-recorded_at')
        
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        total = vitals.count()
        start = (page - 1) * page_size
        end = start + page_size
        
        paginated = vitals[start:end]
        serializer = PatientVitalListSerializer(paginated, many=True)
        
        return Response({
            'success': True,
            'patient': {
                'id': patient.id,
                'name': patient.user.full_name,
                'email': patient.user.email,
            },
            'data': serializer.data,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total': total,
                'total_pages': (total + page_size - 1) // page_size if page_size > 0 else 1
            }
        })
    
    @action(detail=False, methods=['get'], url_path='stats')
    def vital_stats(self, request):
        """Get vital statistics for dashboard"""
        nurse_profile = request.user.nurse_profile
        
        queryset = PatientVital.objects.all()
        if not nurse_profile.is_head_nurse and not nurse_profile.is_department_head:
            queryset = queryset.filter(nurse=nurse_profile)
        
        today = timezone.now().date()
        today_records = queryset.filter(recorded_at__date=today).count()
        
        week_start = today - timedelta(days=7)
        week_records = queryset.filter(recorded_at__date__gte=week_start).count()
        
        total_records = queryset.count()
        emergency_records = queryset.filter(is_emergency=True).count()
        
        # Average vitals
        avg_vitals = queryset.aggregate(
            avg_systolic=Avg('blood_pressure_systolic'),
            avg_diastolic=Avg('blood_pressure_diastolic'),
            avg_heart_rate=Avg('heart_rate'),
            avg_temperature=Avg('temperature'),
            avg_blood_sugar=Avg('blood_sugar'),
            avg_bmi=Avg('bmi')
        )
        
        recent = queryset.order_by('-recorded_at')[:10]
        recent_data = PatientVitalListSerializer(recent, many=True).data
        
        return Response({
            'success': True,
            'stats': {
                'today_records': today_records,
                'week_records': week_records,
                'total_records': total_records,
                'emergency_records': emergency_records,
                'average_vitals': {
                    'blood_pressure_systolic': avg_vitals['avg_systolic'],
                    'blood_pressure_diastolic': avg_vitals['avg_diastolic'],
                    'heart_rate': avg_vitals['avg_heart_rate'],
                    'temperature': avg_vitals['avg_temperature'],
                    'blood_sugar': avg_vitals['avg_blood_sugar'],
                    'bmi': avg_vitals['avg_bmi']
                }
            },
            'recent_records': recent_data
        })
    
    @action(detail=False, methods=['get'], url_path='my-patients')
    def my_patients(self, request):
        """Get list of patients assigned to this nurse"""
        nurse_profile = request.user.nurse_profile
        
        patient_ids = PatientVital.objects.filter(
            nurse=nurse_profile
        ).values_list('patient_id', flat=True).distinct()
        
        patients = PatientProfile.objects.filter(
            id__in=patient_ids
        ).select_related('user')
        
        data = []
        for patient in patients:
            latest_vital = PatientVital.objects.filter(
                patient=patient,
                nurse=nurse_profile
            ).order_by('-recorded_at').first()
            
            data.append({
                'id': patient.id,
                'name': patient.user.full_name,
                'email': patient.user.email,
                'latest_vital': PatientVitalListSerializer(latest_vital).data if latest_vital else None,
                'total_records': PatientVital.objects.filter(patient=patient, nurse=nurse_profile).count()
            })
        
        return Response({
            'success': True,
            'patients': data,
            'total': len(data)
        })
    
    @action(detail=False, methods=['get'], url_path='patients')
    def get_patients(self, request):
        """
        GET /api/nurse/vitals/patients/
        Get list of all patients with their latest vitals
        
        Query Parameters:
        - search: Search by patient name or email
        - has_vitals: Filter patients with/without vitals (true/false)
        - page: Page number
        - page_size: Items per page
        """
        nurse_profile = request.user.nurse_profile
        
        # Get all patients with vitals recorded by this nurse
        patient_ids_with_vitals = PatientVital.objects.filter(
            nurse=nurse_profile
        ).values_list('patient_id', flat=True).distinct()
        
        # Base queryset
        queryset = PatientProfile.objects.select_related('user')
        
        # Filter: Only show patients with vitals if requested
        has_vitals = request.query_params.get('has_vitals')
        if has_vitals is not None:
            if has_vitals.lower() == 'true':
                queryset = queryset.filter(id__in=patient_ids_with_vitals)
            else:
                queryset = queryset.exclude(id__in=patient_ids_with_vitals)
        else:
            # By default, show all patients with vitals
            queryset = queryset.filter(id__in=patient_ids_with_vitals)
        
        # Search filter
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(user__full_name__icontains=search) |
                Q(user__email__icontains=search)
            )
        
        # Pagination
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        total = queryset.count()
        start = (page - 1) * page_size
        end = start + page_size
        
        paginated = queryset[start:end]
        
        # Build response with latest vitals
        data = []
        for patient in paginated:
            # Get latest vital for this patient
            latest_vital = PatientVital.objects.filter(
                patient=patient,
                nurse=nurse_profile
            ).order_by('-recorded_at').first()
            
            # Get all vitals count for this patient
            total_vitals = PatientVital.objects.filter(
                patient=patient,
                nurse=nurse_profile
            ).count()
            
            # Get emergency count
            emergency_count = PatientVital.objects.filter(
                patient=patient,
                nurse=nurse_profile,
                is_emergency=True
            ).count()
            
            data.append({
                'id': patient.id,
                'name': patient.user.full_name,
                'email': patient.user.email,
                'phone': getattr(patient, 'phone_number', ''),
                'latest_vital': PatientVitalListSerializer(latest_vital).data if latest_vital else None,
                'total_vitals': total_vitals,
                'emergency_count': emergency_count,
                'last_recorded': latest_vital.recorded_at if latest_vital else None
            })
        
        return Response({
            'success': True,
            'patients': data,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total': total,
                'total_pages': (total + page_size - 1) // page_size if page_size > 0 else 1
            }
        })
    
    @action(detail=True, methods=['get'], url_path='emr')
    def get_emr_record(self, request, pk=None):
        """Get the EMR record associated with this vital"""
        vital = self.get_object()
        
        try:
            from emr.models import EMRRecord
            from emr.serializer import EMRRecordDetailSerializer
            
            # Find the EMR record for this vital
            emr_record = EMRRecord.objects.filter(
                patient=vital.patient,
                record_type='NURSING_NOTE',
                created_by=vital.nurse.user,
                date=vital.recorded_at.date()
            ).order_by('-created_at').first()
            
            if emr_record:
                serializer = EMRRecordDetailSerializer(emr_record, context={'request': request})
                return Response({
                    'success': True,
                    'emr_record': serializer.data
                })
            else:
                return Response({
                    'success': False,
                    'message': 'No EMR record found for this vital'
                }, status=status.HTTP_404_NOT_FOUND)
                
        except ImportError:
            return Response({
                'success': False,
                'message': 'EMR app not installed'
            }, status=status.HTTP_501_NOT_IMPLEMENTED)
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['delete'], url_path='delete-all')
    def delete_all_vitals(self, request):
        """
        DELETE /api/nurse/vitals/delete-all/
        Delete all vitals for the current nurse (admin only)
        """
        nurse_profile = request.user.nurse_profile
        
        if not nurse_profile.is_head_nurse and not nurse_profile.is_department_head:
            return Response({
                'success': False,
                'message': 'Permission denied. Only head nurses can delete all vitals.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        count = PatientVital.objects.filter(nurse=nurse_profile).count()
        PatientVital.objects.filter(nurse=nurse_profile).delete()
        
        return Response({
            'success': True,
            'message': f'Deleted {count} vital records'
        })