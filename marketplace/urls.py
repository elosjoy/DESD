from django.urls import path
from . import views

app_name = "marketplace"

urlpatterns = [
    path("", views.home, name="home"),
    path("register/customer/", views.register_customer, name="register_customer"),
    path("register/producer/", views.register_producer, name="register_producer"),
    path("producer/products/", views.producer_products, name="producer_products"),
    path("producer/products/new/", views.producer_product_create, name="producer_product_create"),
    path("producer/orders/", views.producer_orders, name="producer_orders"),
    path("producer/order-items/<int:order_item_id>/status/", views.producer_update_order_status, name="producer_update_order_status"),
    path("producer/settlement/", views.producer_weekly_settlement, name="producer_weekly_settlement"),
    path("orders/", views.customer_orders, name="customer_orders"),
    path("orders/<int:order_id>/", views.customer_order_detail, name="customer_order_detail"),
    path("orders/<int:order_id>/reorder/", views.reorder_from_order, name="reorder_from_order"),
    path("api/register/producer/", views.ProducerRegistrationView.as_view(), name="producer-register"),
    path("category/<slug:slug>/", views.category_products, name="category_products"),
    path("product/<int:pk>/", views.product_detail, name="product_detail"),
    path("cart/", views.cart_detail, name="cart_detail"),
    path("cart/add/<int:product_id>/", views.add_to_cart, name="add_to_cart"),
    path("cart/update/<int:product_id>/", views.update_cart_item, name="update_cart_item"),
    path("cart/remove/<int:product_id>/", views.remove_from_cart, name="remove_from_cart"),
    
    # Producer product management
    path("api/producer/products/", views.ProducerProductListCreateView.as_view(), name="producer-products"),
    path("api/producer/products/<int:pk>/", views.ProducerProductDetailView.as_view(), name="producer-product-detail"),
    path("api/producer/orders/", views.ProducerOrderListView.as_view(), name="producer-orders"),
]
