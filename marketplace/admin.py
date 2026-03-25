from django.contrib import admin
from .models import CustomerProfile, ProducerProfile, Category, Product, Order, OrderItem, Settlement, OrderStatusUpdate

admin.site.register(CustomerProfile)
admin.site.register(ProducerProfile)
admin.site.register(Category)
admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(Settlement)
admin.site.register(OrderStatusUpdate)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'producer', 'price', 'stock_quantity', 'availability_status')
    list_filter = ('category', 'availability_status', 'producer')
    search_fields = ('name', 'producer__producer_name')
    readonly_fields = ('producer',)