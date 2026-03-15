from django.urls import path
from . import views

app_name = "marketplace"

urlpatterns = [
    path("", views.home, name="home"),
    path("register/customer/", views.register_customer, name="register_customer"),
    path("register/producer/", views.register_producer, name="register_producer"),
    path("producer/products/", views.producer_products, name="producer_products"),
    path("producer/products/new/", views.producer_product_create, name="producer_product_create"),
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
]
