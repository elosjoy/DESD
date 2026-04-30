from django.contrib import admin
from .models import CustomerProfile, ProducerProfile, Category, Product, Order, OrderItem, Settlement, OrderStatusUpdate

admin.site.register(CustomerProfile)
admin.site.register(ProducerProfile)
admin.site.register(Category)
admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(OrderStatusUpdate)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'producer', 'price', 'stock_quantity', 'availability_status')
    list_filter = ('category', 'availability_status', 'producer')
    search_fields = ('name', 'producer__producer_name')
    readonly_fields = ('producer',)


@admin.register(Settlement)
class SettlementAdmin(admin.ModelAdmin):
    """
    Admin interface for Settlement records.
    
    Displays:
    - Week date range
    - Producer name
    - Total sales and commission breakdown
    - Final net payout to producer
    """
    list_display = (
        'producer_name',
        'week_range',
        'total_order_value',
        'commission_display',
        'net_payout_display',
        'created_at',
    )
    list_filter = (
        'producer',
        'week_start',
        'created_at',
    )
    search_fields = (
        'producer__producer_name',
        'producer__user__username',
    )
    readonly_fields = (
        'total_order_value',
        'commission_rate',
        'commission_amount',
        'net_payout',
        'created_at',
    )
    fieldsets = (
        ('Settlement Period', {
            'fields': ('producer', 'week_start', 'week_end', 'created_at'),
        }),
        ('Financial Details', {
            'fields': (
                'total_order_value',
                'commission_rate',
                'commission_amount',
                'net_payout',
            ),
        }),
    )
    
    def producer_name(self, obj):
        """Display producer's business name."""
        return obj.producer.producer_name
    producer_name.short_description = 'Producer'
    
    def week_range(self, obj):
        """Display the settlement week as readable date range."""
        return f"{obj.week_start} to {obj.week_end}"
    week_range.short_description = 'Week'
    
    def commission_display(self, obj):
        """Display commission amount with rate."""
        return f"£{obj.commission_amount} ({obj.commission_rate}%)"
    commission_display.short_description = 'Commission'
    
    def net_payout_display(self, obj):
        """Display net payout (producer's payment)."""
        return f"£{obj.net_payout}"
    net_payout_display.short_description = 'Producer Payout'