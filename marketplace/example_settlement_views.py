"""
Example DRF views for settlement management.

These views demonstrate how to use the settlement service in your API endpoints.
Add these to your urls.py as needed.
"""

from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from decimal import Decimal

from marketplace.models import Settlement, ProducerProfile
from marketplace.serializers import SettlementSerializer
from marketplace.services.settlement_service import (
    calculate_settlement_for_producer,
    calculate_settlements_for_week,
    get_producer_settlements,
    get_week_boundaries,
)


# ============================================================================
# Example 1: Producer views their recent settlements (for dashboard/profile)
# ============================================================================

class ProducerSettlementsListView(generics.ListAPIView):
    """
    GET /api/producer/settlements/
    
    Returns the producer's recent settlements.
    Only producers can view their own settlements.
    """
    serializer_class = SettlementSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Get the producer profile for the logged-in user
        try:
            producer = self.request.user.producerprofile
        except ProducerProfile.DoesNotExist:
            return Settlement.objects.none()
        
        # Return their settlements, newest first
        return Settlement.objects.filter(
            producer=producer
        ).order_by('-week_start')


# ============================================================================
# Example 2: Calculate settlement on demand (e.g., for current week)
# ============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def calculate_current_settlement(request):
    """
    POST /api/producer/settlements/calculate/
    
    Calculates the settlement for the current week.
    Only works if the producer profile exists.
    
    Request body: {} (empty)
    
    Response:
    {
        "id": 123,
        "producer": 5,
        "week_start": "2026-04-27",
        "week_end": "2026-05-03",
        "total_order_value": "1000.00",
        "commission_rate": "5.00",
        "commission_amount": "50.00",
        "net_payout": "950.00"
    }
    """
    try:
        producer = request.user.producerprofile
    except ProducerProfile.DoesNotExist:
        return Response(
            {'error': 'User is not a producer'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        settlement = calculate_settlement_for_producer(producer)
        serializer = SettlementSerializer(settlement)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response(
            {'error': f'Failed to calculate settlement: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============================================================================
# Example 3: Admin endpoint to calculate settlements for all producers
# ============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def calculate_all_settlements(request):
    """
    POST /api/admin/settlements/calculate-week/
    
    Calculates settlements for ALL producers for a given week.
    Only admin users should have access to this endpoint.
    
    Request body:
    {
        "week_offset": 0  # 0=current, -1=last week, etc. (optional, default=0)
    }
    
    Response:
    {
        "success": true,
        "count": 5,
        "total_sales": "5000.00",
        "total_commission": "250.00",
        "total_payouts": "4750.00",
        "settlements": [...]
    }
    """
    week_offset = request.data.get('week_offset', 0)
    
    from django.utils import timezone
    from datetime import timedelta
    
    today = timezone.now().date()
    target_date = today + timedelta(weeks=week_offset)
    week_start, week_end = get_week_boundaries(target_date)
    
    try:
        settlements = calculate_settlements_for_week(
            week_start=week_start,
            week_end=week_end,
        )
        
        total_sales = sum(s.total_order_value for s in settlements)
        total_commission = sum(s.commission_amount for s in settlements)
        total_payouts = sum(s.net_payout for s in settlements)
        
        return Response(
            {
                'success': True,
                'count': len(settlements),
                'week_start': str(week_start),
                'week_end': str(week_end),
                'total_sales': str(total_sales),
                'total_commission': str(total_commission),
                'total_payouts': str(total_payouts),
                'settlements': SettlementSerializer(settlements, many=True).data,
            },
            status=status.HTTP_200_OK
        )
    
    except Exception as e:
        return Response(
            {'error': f'Failed to calculate settlements: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============================================================================
# Example 4: Get settlement details for a specific week
# ============================================================================

class SettlementDetailView(generics.RetrieveAPIView):
    """
    GET /api/settlements/{id}/
    
    Returns details of a specific settlement.
    """
    queryset = Settlement.objects.all()
    serializer_class = SettlementSerializer
    permission_classes = [IsAuthenticated]
