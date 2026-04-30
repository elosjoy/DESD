"""
Settlement Service for calculating and managing producer payouts.

This module handles:
- Aggregating order values per producer for a date range
- Calculating commissions and net payouts
- Creating/updating settlements
- Ensuring no duplicate settlements
"""

from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db.models import Q, Sum
from django.db import IntegrityError

from marketplace.models import Settlement, OrderItem, ProducerProfile


def get_commission_rate():
    """
    Get the marketplace commission rate from settings.
    
    Returns:
        Decimal: Commission rate as percentage (e.g., Decimal('5.00') for 5%)
    """
    rate = getattr(settings, 'MARKETPLACE_COMMISSION_RATE', 5.0)
    return Decimal(str(rate))


def get_week_boundaries(target_date=None):
    """
    Get Monday (week_start) and Sunday (week_end) for a given date.
    
    Args:
        target_date: datetime.date object. If None, uses today.
    
    Returns:
        Tuple of (week_start, week_end) as date objects
    """
    if target_date is None:
        target_date = datetime.now().date()
    
    # weekday(): Monday=0, Sunday=6
    days_since_monday = target_date.weekday()
    week_start = target_date - timedelta(days=days_since_monday)
    week_end = week_start + timedelta(days=6)
    
    return week_start, week_end


def calculate_settlement_for_producer(producer, week_start=None, week_end=None):
    """
    Calculate settlement for a single producer for a date range.
    
    This function:
    1. Aggregates all delivered/completed OrderItems for the producer
    2. Calculates commission based on marketplace rate
    3. Creates or updates the Settlement record
    4. Prevents duplicates via unique_together constraint
    
    Args:
        producer: ProducerProfile instance
        week_start: datetime.date (if None, uses current week Monday)
        week_end: datetime.date (if None, uses current week Sunday)
    
    Returns:
        Settlement: The created or updated Settlement object
    
    Raises:
        ValidationError: If producer not found or data is invalid
    
    Example:
        from marketplace.models import ProducerProfile
        from marketplace.services.settlement_service import calculate_settlement_for_producer
        
        producer = ProducerProfile.objects.get(id=1)
        settlement = calculate_settlement_for_producer(producer)
        print(f"Producer payout: £{settlement.net_payout}")
    """
    if not isinstance(producer, ProducerProfile):
        raise TypeError("producer must be a ProducerProfile instance")
    
    # Get week boundaries
    if week_start is None or week_end is None:
        week_start, week_end = get_week_boundaries()
    
    # Query: Get all OrderItems for this producer that are delivered/completed
    # Only items with status DELIVERED or COMPLETED count toward settlement
    delivered_items = OrderItem.objects.filter(
        producer=producer,
        status__in=[OrderItem.DELIVERED],
        order__delivered_at__date__gte=week_start,
        order__delivered_at__date__lte=week_end,
    )
    
    # Calculate total sales value (quantity * unit_price)
    totals = delivered_items.aggregate(
        total=Sum(
            'quantity',  # This won't work as intended; we need quantity * unit_price
            output_field=None
        )
    )
    
    # Better approach: calculate in Python for clarity
    total_sales = Decimal('0.00')
    for item in delivered_items:
        item_total = Decimal(str(item.quantity)) * item.unit_price
        total_sales += item_total
    
    total_sales = total_sales.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    # Get commission rate
    commission_rate = get_commission_rate()
    
    # Calculate commission and payout
    rate_decimal = commission_rate / Decimal('100')
    commission_amount = (total_sales * rate_decimal).quantize(
        Decimal('0.01'),
        rounding=ROUND_HALF_UP
    )
    net_payout = (total_sales - commission_amount).quantize(
        Decimal('0.01'),
        rounding=ROUND_HALF_UP
    )
    
    # Create or update settlement
    # Use get_or_create to handle the unique_together constraint gracefully
    settlement, created = Settlement.objects.get_or_create(
        producer=producer,
        week_start=week_start,
        week_end=week_end,
        defaults={
            'total_order_value': total_sales,
            'commission_rate': commission_rate,
            'commission_amount': commission_amount,
            'net_payout': net_payout,
        }
    )
    
    # If settlement already existed, update the values
    if not created:
        settlement.total_order_value = total_sales
        settlement.commission_rate = commission_rate
        settlement.commission_amount = commission_amount
        settlement.net_payout = net_payout
        settlement.save(update_fields=[
            'total_order_value',
            'commission_rate',
            'commission_amount',
            'net_payout',
        ])
    
    return settlement


def calculate_settlements_for_week(week_start=None, week_end=None, producers=None):
    """
    Calculate settlements for all producers (or specific producers) for a week.
    
    This is a bulk operation useful for periodic settlement calculations
    (e.g., weekly batch job).
    
    Args:
        week_start: datetime.date (if None, uses current week Monday)
        week_end: datetime.date (if None, uses current week Sunday)
        producers: QuerySet or list of ProducerProfile instances.
                  If None, calculates for all producers with delivered items.
    
    Returns:
        List of Settlement objects created/updated
    
    Example:
        from marketplace.services.settlement_service import calculate_settlements_for_week
        from datetime import datetime, timedelta
        
        # Calculate for last week
        today = datetime.now().date()
        last_week_start = today - timedelta(days=7)
        last_week_end = last_week_start + timedelta(days=6)
        
        settlements = calculate_settlements_for_week(last_week_start, last_week_end)
        print(f"Calculated {len(settlements)} settlements")
        for settlement in settlements:
            print(f"{settlement.producer.producer_name}: £{settlement.net_payout}")
    """
    if week_start is None or week_end is None:
        week_start, week_end = get_week_boundaries()
    
    # If no producers specified, find all with delivered items in this week
    if producers is None:
        producer_ids = OrderItem.objects.filter(
            status=OrderItem.DELIVERED,
            order__delivered_at__date__gte=week_start,
            order__delivered_at__date__lte=week_end,
        ).values_list('producer_id', flat=True).distinct()
        
        producers = ProducerProfile.objects.filter(id__in=producer_ids)
    
    settlements = []
    for producer in producers:
        settlement = calculate_settlement_for_producer(
            producer,
            week_start=week_start,
            week_end=week_end,
        )
        settlements.append(settlement)
    
    return settlements


def get_producer_settlements(producer, limit=None):
    """
    Get recent settlements for a producer.
    
    Args:
        producer: ProducerProfile instance
        limit: Number of recent settlements to return (default: all)
    
    Returns:
        QuerySet of Settlement objects, ordered newest first
    
    Example:
        from marketplace.models import ProducerProfile
        from marketplace.services.settlement_service import get_producer_settlements
        
        producer = ProducerProfile.objects.get(id=1)
        recent_settlements = get_producer_settlements(producer, limit=10)
        
        total_earned = sum(s.net_payout for s in recent_settlements)
        print(f"Total earned (last 10 weeks): £{total_earned}")
    """
    settlements = Settlement.objects.filter(producer=producer).order_by('-week_start')
    
    if limit:
        settlements = settlements[:limit]
    
    return settlements
