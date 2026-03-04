from django.urls import path
from . import views

app_name = "marketplace"

urlpatterns = [
    path("", views.home, name="home"),
    path("register/customer/", views.register_customer, name="register_customer"),
    path("api/register/producer/", views.ProducerRegistrationView.as_view(), name="producer-register"),
    path("category/<slug:slug>/", views.category_products, name="category_products"),
    
    # Producer product management
    path("api/producer/products/", views.ProducerProductListCreateView.as_view(), name="producer-products"),
    path("api/producer/products/<int:pk>/", views.ProducerProductDetailView.as_view(), name="producer-product-detail"),
]
