from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .forms import CustomerRegistrationForm
from .serializers import ProducerRegistrationSerializer, ProductSerializer
from .models import Category, Product, ProducerProfile
from django.contrib.auth import get_user_model

User = get_user_model()


def home(request):
    categories = Category.objects.all()
    return render(request, "marketplace/home.html", {"categories": categories})


def register_customer(request):
    if request.method == "POST":
        form = CustomerRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Account created. Please log in.")
            return redirect("login")
    else:
        form = CustomerRegistrationForm()

    return render(request, "marketplace/register.html", {"form": form})


def category_products(request, slug):
    category = get_object_or_404(Category, slug=slug)
    products = Product.objects.filter(
        category=category,
        availability_status__in=[Product.AVAILABLE, Product.IN_SEASON],
    )
    return render(request, "marketplace/category.html", {"category": category, "products": products})


class ProducerRegistrationView(generics.CreateAPIView):
    """API endpoint for producer registration"""
    queryset = User.objects.all()
    serializer_class = ProducerRegistrationSerializer
    permission_classes = []  # Allow unauthenticated access

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(
            {"detail": "Producer account created successfully. Please log in."},
            status=status.HTTP_201_CREATED
        )


class ProducerProductListCreateView(generics.ListCreateAPIView):
    """Producer can create and list their own products"""
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Only show this producer's products"""
        producer = get_object_or_404(ProducerProfile, user=self.request.user)
        return Product.objects.filter(producer=producer)

    def perform_create(self, serializer):
        """Automatically link product to the authenticated producer"""
        producer = get_object_or_404(ProducerProfile, user=self.request.user)
        serializer.save(producer=producer)


class ProducerProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Producer can update or delete their own products"""
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Only allow editing own products"""
        producer = get_object_or_404(ProducerProfile, user=self.request.user)
        return Product.objects.filter(producer=producer)
