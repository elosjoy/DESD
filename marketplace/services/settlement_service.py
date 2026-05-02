# Handles calculating producer payouts and settlements at the end of each week.

from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings

from marketplace.models import Settlement, OrderItem, ProducerProfile


def get_commission_rate():
    # reads from settings, defaults to 5%
    rate = getattr(settings, 'MARKETPLACE_COMMISSION_RATE', 5.0)
    return Decimal(str(rate))


def get_week_boundaries(target_date=None):
    # returns (monday, sunday) for the given date, defaults to current week
    if target_date is None:
        target_date = datetime.now().date()
    
    # weekday(): Monday=0, Sunday=6
    days_since_monday = target_date.weekday()
    week_start = target_date - timedelta(days=days_since_monday)
    week_end = week_start + timedelta(days=6)
    
    return week_start, week_end


def calculate_settlement_for_producer(producer, week_start=None, week_end=None):
    # works out the total sales, commission and payout for a producer for a given week
    # creates a new Settlement record or updates it if one already exists
    if not isinstance(producer, ProducerProfile):
        raise TypeError("producer must be a ProducerProfile instance")
    
    # default to current week if not specified
    if week_start is None or week_end is None:
        week_start, week_end = get_week_boundaries()
    
    # Query: Get all OrderItems for this producer that were delivered in this week
    delivered_items = OrderItem.objects.filter(
        producer=producer,
        status=OrderItem.DELIVERED,
        order__delivered_at__date__gte=week_start,
        order__delivered_at__date__lte=week_end,
    )
    
    # multiply quantity by unit price for each item
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
    
    # create a new settlement or update the existing one for this week
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
    
    # already exists so just update the totals
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
    # runs calculate_settlement_for_producer for every producer with deliveries in the given week
    if week_start is None or week_end is None:
        week_start, week_end = get_week_boundaries()
    
    # if no producers passed in, find everyone who had deliveries this week
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
    # returns the producer's settlements ordered newest first
    settlements = Settlement.objects.filter(producer=producer).order_by('-week_start')
    
    if limit:
        settlements = settlements[:limit]
    
    return settlements
