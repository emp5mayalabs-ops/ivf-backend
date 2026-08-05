# cryo/views.py

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count, Sum
from django.utils import timezone
from django.shortcuts import get_object_or_404

from .models import (
    CryoTank,
    CryoCanister,
    CryoCane,
    CryoGoblet,
    CryoStoredSample
)
from .serializers import (
    CryoTankSerializer,
    CryoTankListSerializer,
    CryoCanisterSerializer,
    CryoCaneSerializer,
    CryoGobletSerializer,
    CryoStoredSampleSerializer,
    CryoStoredSampleListSerializer
)
from .permissions import IsCryoStaff


# ============================================================
# 1. TANK VIEWS
# ============================================================

class CryoTankListView(generics.ListCreateAPIView):
    """
    List all tanks / Create new tank
    GET /api/cryo/tanks/
    POST /api/cryo/tanks/
    """
    permission_classes = [IsAuthenticated, IsCryoStaff]
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return CryoTankListSerializer
        return CryoTankSerializer
    
    def get_queryset(self):
        queryset = CryoTank.objects.all()
        
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(name__icontains=search)
        
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class CryoTankDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Get, update, delete tank
    GET /api/cryo/tanks/{id}/
    PUT /api/cryo/tanks/{id}/
    DELETE /api/cryo/tanks/{id}/
    """
    permission_classes = [IsAuthenticated, IsCryoStaff]
    serializer_class = CryoTankSerializer
    queryset = CryoTank.objects.all()


# ============================================================
# 2. CANISTER VIEWS
# ============================================================

class CryoCanisterListView(generics.ListCreateAPIView):
    """
    List canisters / Create new canister
    GET /api/cryo/canisters/
    POST /api/cryo/canisters/
    """
    permission_classes = [IsAuthenticated, IsCryoStaff]
    serializer_class = CryoCanisterSerializer
    
    def get_queryset(self):
        queryset = CryoCanister.objects.all()
        
        tank_id = self.request.query_params.get('tank')
        if tank_id:
            queryset = queryset.filter(tank_id=tank_id)
        
        return queryset


class CryoCanisterDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update, delete canister"""
    permission_classes = [IsAuthenticated, IsCryoStaff]
    serializer_class = CryoCanisterSerializer
    queryset = CryoCanister.objects.all()


# ============================================================
# 3. CANE VIEWS
# ============================================================

class CryoCaneListView(generics.ListCreateAPIView):
    """
    List canes / Create new cane
    GET /api/cryo/canes/
    POST /api/cryo/canes/
    """
    permission_classes = [IsAuthenticated, IsCryoStaff]
    serializer_class = CryoCaneSerializer
    
    def get_queryset(self):
        queryset = CryoCane.objects.all()
        
        canister_id = self.request.query_params.get('canister')
        if canister_id:
            queryset = queryset.filter(canister_id=canister_id)
        
        return queryset


class CryoCaneDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update, delete cane"""
    permission_classes = [IsAuthenticated, IsCryoStaff]
    serializer_class = CryoCaneSerializer
    queryset = CryoCane.objects.all()


# ============================================================
# 4. GOBLET VIEWS
# ============================================================

class CryoGobletListView(generics.ListCreateAPIView):
    """
    List goblets / Create new goblet
    GET /api/cryo/goblets/
    POST /api/cryo/goblets/
    """
    permission_classes = [IsAuthenticated, IsCryoStaff]
    serializer_class = CryoGobletSerializer
    
    def get_queryset(self):
        queryset = CryoGoblet.objects.all()
        
        cane_id = self.request.query_params.get('cane')
        if cane_id:
            queryset = queryset.filter(cane_id=cane_id)
        
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset


class CryoGobletDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update, delete goblet"""
    permission_classes = [IsAuthenticated, IsCryoStaff]
    serializer_class = CryoGobletSerializer
    queryset = CryoGoblet.objects.all()


# ============================================================
# 5. STORED SAMPLE VIEWS
# ============================================================

class CryoStoredSampleListView(generics.ListAPIView):
    """
    List all stored samples
    GET /api/cryo/samples/
    """
    permission_classes = [IsAuthenticated, IsCryoStaff]
    serializer_class = CryoStoredSampleListSerializer
    
    def get_queryset(self):
        queryset = CryoStoredSample.objects.select_related(
            'patient__user',
            'tank',
            'canister',
            'cane',
            'goblet'
        )
        
        # Filter by patient
        patient_id = self.request.query_params.get('patient')
        if patient_id:
            queryset = queryset.filter(patient_id=patient_id)
        
        # Filter by status
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by sample type
        sample_type = self.request.query_params.get('sample_type')
        if sample_type:
            queryset = queryset.filter(sample_type=sample_type)
        
        # Search
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(patient__user__full_name__icontains=search) |
                Q(sample_id__icontains=search) |
                Q(rfid_tag__icontains=search)
            )
        
        # Filter by location
        tank_id = self.request.query_params.get('tank')
        if tank_id:
            queryset = queryset.filter(tank_id=tank_id)
        
        return queryset.order_by('-storage_date')


class CryoStoredSampleCreateView(generics.CreateAPIView):
    """
    Store a new sample
    POST /api/cryo/samples/create/
    """
    permission_classes = [IsAuthenticated, IsCryoStaff]
    serializer_class = CryoStoredSampleSerializer


class CryoStoredSampleDetailView(generics.RetrieveAPIView):
    """
    Get sample details
    GET /api/cryo/samples/{id}/
    """
    permission_classes = [IsAuthenticated, IsCryoStaff]
    serializer_class = CryoStoredSampleSerializer
    queryset = CryoStoredSample.objects.all()


class CryoStoredSampleUpdateView(generics.UpdateAPIView):
    """
    Update sample
    PUT /api/cryo/samples/{id}/update/
    """
    permission_classes = [IsAuthenticated, IsCryoStaff]
    serializer_class = CryoStoredSampleSerializer
    queryset = CryoStoredSample.objects.all()


class CryoStoredSampleDeleteView(generics.DestroyAPIView):
    """
    Delete sample
    DELETE /api/cryo/samples/{id}/delete/
    """
    permission_classes = [IsAuthenticated, IsCryoStaff]
    queryset = CryoStoredSample.objects.all()


# ============================================================
# 6. THAW SAMPLE
# ============================================================

class CryoThawSampleView(APIView):
    """
    Thaw a sample
    POST /api/cryo/samples/{id}/thaw/
    """
    permission_classes = [IsAuthenticated, IsCryoStaff]
    
    def post(self, request, pk):
        sample = get_object_or_404(CryoStoredSample, pk=pk)
        
        sample.status = 'THAWED'
        sample.thawed_date = timezone.now()
        sample.thawed_by = request.user
        sample.post_thaw_survival = request.data.get('post_thaw_survival')
        sample.thaw_notes = request.data.get('thaw_notes', '')
        sample.save()
        
        # Free the goblet
        if sample.goblet:
            sample.goblet.status = 'EMPTY'
            sample.goblet.save()
        
        return Response({
            'success': True,
            'message': 'Sample thawed successfully',
            'data': CryoStoredSampleSerializer(sample).data
        }, status=status.HTTP_200_OK)


# ============================================================
# 7. DASHBOARD / INVENTORY
# ============================================================

class CryoDashboardView(APIView):
    """
    Get storage dashboard summary
    GET /api/cryo/dashboard/
    """
    permission_classes = [IsAuthenticated, IsCryoStaff]
    
    def get(self, request):
        tanks = CryoTank.objects.all()
        tank_data = []
        
        for tank in tanks:
            tank_data.append({
                'id': tank.id,
                'name': tank.name,
                'total_capacity': tank.capacity,
                'used': tank.current_usage,
                'available': tank.available_space,
                'usage_percentage': tank.usage_percentage,
                'is_full': tank.is_full,
                'status': tank.status,
                'samples_stored': tank.samples.filter(status='STORED').count()
            })
        
        total_samples = CryoStoredSample.objects.count()
        stored_samples = CryoStoredSample.objects.filter(status='STORED').count()
        thawed_samples = CryoStoredSample.objects.filter(status='THAWED').count()
        expired_samples = CryoStoredSample.objects.filter(status='EXPIRED').count()
        
        by_type = CryoStoredSample.objects.values('sample_type').annotate(
            count=Count('id')
        )
        
        recent_samples = CryoStoredSample.objects.select_related(
            'patient__user'
        ).order_by('-storage_date')[:10]
        
        recent_data = CryoStoredSampleListSerializer(recent_samples, many=True).data
        
        return Response({
            'success': True,
            'summary': {
                'total_samples': total_samples,
                'stored_samples': stored_samples,
                'thawed_samples': thawed_samples,
                'expired_samples': expired_samples,
                'total_tanks': tanks.count(),
                'total_capacity': sum(t.capacity for t in tanks),
                'used_capacity': sum(t.current_usage for t in tanks),
            },
            'tanks': tank_data,
            'by_type': by_type,
            'recent_storages': recent_data
        })


# ============================================================
# 8. AVAILABLE POSITIONS
# ============================================================

class CryoAvailablePositionsView(APIView):
    """
    Get available positions for storage
    GET /api/cryo/available-positions/
    """
    permission_classes = [IsAuthenticated, IsCryoStaff]
    
    def get(self, request):
        empty_goblets = CryoGoblet.objects.filter(
            status='EMPTY'
        ).select_related(
            'cane__canister__tank'
        )
        
        result = []
        tanks = CryoTank.objects.filter(status='ACTIVE')
        
        for tank in tanks:
            tank_data = {
                'id': tank.id,
                'name': tank.name,
                'canisters': []
            }
            
            canisters = tank.canisters.all()
            for canister in canisters:
                canister_data = {
                    'id': canister.id,
                    'canister_number': canister.canister_number,
                    'canes': []
                }
                
                canes = canister.canes.all()
                for cane in canes:
                    goblets = cane.goblets.filter(status='EMPTY')
                    if goblets.exists():
                        canister_data['canes'].append({
                            'id': cane.id,
                            'cane_number': cane.cane_number,
                            'goblets': CryoGobletSerializer(goblets, many=True).data
                        })
                
                if canister_data['canes']:
                    tank_data['canisters'].append(canister_data)
            
            if tank_data['canisters']:
                result.append(tank_data)
        
        return Response({
            'success': True,
            'available_positions': result
        })