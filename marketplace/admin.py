from django.contrib import admin
from .models import CustomerProfile, ProducerProfile, Category, Product

admin.site.register(CustomerProfile)
admin.site.register(ProducerProfile)
admin.site.register(Category)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'producer', 'price', 'stock_quantity', 'availability_status')
    list_filter = ('category', 'availability_status', 'producer')
    search_fields = ('name', 'producer__producer_name')
    readonly_fields = ('producer',)