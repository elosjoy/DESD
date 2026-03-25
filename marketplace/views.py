from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q, Sum, F, DecimalField, ExpressionWrapper
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .forms import (
    CustomerRegistrationForm,
    ProducerRegistrationForm,
    ProducerProductForm,
)
from .serializers import ProducerRegistrationSerializer, ProductSerializer, ProducerOrderItemSerializer
from .models import Category, Product, ProducerProfile, Order, OrderItem, Settlement
from .permissions import IsProducerUser
from .cart import Cart
from django.contrib.auth import get_user_model

User = get_user_model()


def home(request):
    cart = Cart(request)
    categories = Category.objects.all()
    query = request.GET.get("q", "").strip()
    products = Product.objects.none()

    if query:
        products = (
            Product.objects.select_related("producer", "category")
            .filter(
                availability_status__in=[Product.AVAILABLE, Product.IN_SEASON],
            )
            .filter(
                Q(name__icontains=query)
                | Q(description__icontains=query)
                | Q(producer__producer_name__icontains=query)
            )
            .distinct()
        )

    context = {
        "categories": categories,
        "search_query": query,
        "search_results": products,
        "search_performed": bool(query),
        "cart_total_items": cart.get_total_items(),
    }
    return render(request, "marketplace/home.html", context)


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


def register_producer(request):
    if request.method == "POST":
        form = ProducerRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Producer account created. Please log in.")
            return redirect("login")
    else:
        form = ProducerRegistrationForm()

    return render(request, "marketplace/register_producer.html", {"form": form})


@login_required
def producer_products(request):
    try:
        producer = ProducerProfile.objects.get(user=request.user)
    except ProducerProfile.DoesNotExist:
        messages.error(request, "You do not have a producer profile yet.")
        return redirect("marketplace:register_producer")

    products = Product.objects.filter(producer=producer).select_related("category")
    return render(
        request,
        "marketplace/producer_products.html",
        {"producer": producer, "products": products},
    )


@login_required
def producer_product_create(request):
    try:
        producer = ProducerProfile.objects.get(user=request.user)
    except ProducerProfile.DoesNotExist:
        messages.error(request, "You do not have a producer profile yet.")
        return redirect("marketplace:register_producer")

    if not Category.objects.exists():
        messages.error(request, "No categories exist yet. Ask an admin to add categories first.")
        return redirect("marketplace:producer_products")

    if request.method == "POST":
        form = ProducerProductForm(request.POST)
        if form.is_valid():
            product = form.save(commit=False)
            product.producer = producer
            product.save()
            messages.success(request, "Product listed successfully.")
            return redirect("marketplace:producer_products")
    else:
        form = ProducerProductForm()

    return render(request, "marketplace/producer_product_form.html", {"form": form})


@login_required
def producer_orders(request):
    # Security check for web dashboard: only producers can access incoming orders.
    try:
        producer = ProducerProfile.objects.get(user=request.user)
    except ProducerProfile.DoesNotExist:
        messages.error(request, "Only producer accounts can view incoming orders.")
        return redirect("marketplace:home")

    order_items = (
        OrderItem.objects.filter(producer=producer)
        .select_related("order", "product")
        .order_by("-order__created_at", "id")
    )

    return render(
        request,
        "marketplace/producer_orders.html",
        {"order_items": order_items},
    )


@login_required
def producer_weekly_settlement(request):
    # Security check for web dashboard: only producers can access settlement data.
    try:
        producer = ProducerProfile.objects.get(user=request.user)
    except ProducerProfile.DoesNotExist:
        messages.error(request, "Only producer accounts can view settlements.")
        return redirect("marketplace:home")

    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    # Settlement is based on completed/delivered orders for this producer in the selected week.
    weekly_items = OrderItem.objects.filter(
        producer=producer,
        order__status__in=[Order.COMPLETED, Order.DELIVERED],
        order__delivered_at__date__range=(week_start, week_end),
    )

    line_total_expression = ExpressionWrapper(
        F("quantity") * F("unit_price"),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )

    totals = weekly_items.aggregate(total_order_value=Sum(line_total_expression))
    total_order_value = totals["total_order_value"] or Decimal("0.00")

    commission_total = (total_order_value * Decimal("0.05")).quantize(Decimal("0.01"))
    producer_payment_total = (total_order_value - commission_total).quantize(Decimal("0.01"))

    settlement, created = Settlement.objects.get_or_create(
        producer=producer,
        week_start=week_start,
        week_end=week_end,
        defaults={
            "total_order_value": total_order_value,
            "commission_total": commission_total,
            "producer_payment_total": producer_payment_total,
        },
    )

    if not created:
        settlement.total_order_value = total_order_value
        settlement.commission_total = commission_total
        settlement.producer_payment_total = producer_payment_total
        settlement.save(update_fields=["total_order_value", "commission_total", "producer_payment_total"])

    return render(
        request,
        "marketplace/producer_settlement.html",
        {
            "settlement": settlement,
            "week_order_count": weekly_items.count(),
        },
    )


class ProducerOrderListView(generics.ListAPIView):
    """Producer can view only their own completed/delivered order line items."""

    serializer_class = ProducerOrderItemSerializer
    # Security check: enforce authenticated producer-only access.
    permission_classes = [IsAuthenticated, IsProducerUser]

    def get_queryset(self):
        producer = get_object_or_404(ProducerProfile, user=self.request.user)
        return OrderItem.objects.select_related("order", "product").filter(
            producer=producer,
            order__status__in=[Order.COMPLETED, Order.DELIVERED],
        )
