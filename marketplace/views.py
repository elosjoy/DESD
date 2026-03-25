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
    ProducerOrderStatusUpdateForm,
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
@require_POST
def producer_update_order_status(request, order_item_id):
    # Security check: producer can only update status for their own order items.
    try:
        producer = ProducerProfile.objects.get(user=request.user)
    except ProducerProfile.DoesNotExist:
        messages.error(request, "Only producer accounts can update order statuses.")
        return redirect("marketplace:home")

    order_item = get_object_or_404(OrderItem, id=order_item_id, producer=producer)
    allowed_statuses = order_item.get_allowed_next_statuses()
    form = ProducerOrderStatusUpdateForm(request.POST, allowed_statuses=allowed_statuses)

    if not allowed_statuses:
        messages.warning(request, "This order has no further allowed status transitions.")
        return redirect("marketplace:producer_orders")

    if not form.is_valid():
        messages.error(request, "Invalid status update request.")
        return redirect("marketplace:producer_orders")

    new_status = form.cleaned_data["new_status"]
    producer_note = form.cleaned_data.get("producer_note", "").strip()

    try:
        # Enforces allowed transitions: Pending -> Confirmed -> Ready -> Delivered.
        order_item.update_status(new_status, producer_note=producer_note, updated_by=request.user)
    except Exception:
        messages.error(request, "Status update was rejected due to an invalid transition.")
        return redirect("marketplace:producer_orders")

    messages.success(
        request,
        f"Updated {order_item.product.name} on Order #{order_item.order.id} to {order_item.get_status_display()}.",
    )
    return redirect("marketplace:producer_orders")


@login_required
def customer_orders(request):
    # Security check: customer only sees their own orders.
    orders = (
        Order.objects.filter(customer=request.user)
        .prefetch_related("status_updates")
        .order_by("-created_at")
        .distinct()
    )
    return render(request, "marketplace/customer_orders.html", {"orders": orders})


@login_required
def customer_order_detail(request, order_id):
    # Security check: customer can only view their own order details.
    order = get_object_or_404(
        Order.objects.prefetch_related("items__product", "status_updates__order_item__product"),
        id=order_id,
        customer=request.user,
    )
    return render(request, "marketplace/customer_order_detail.html", {"order": order})


@login_required
@require_POST
def reorder_from_order(request, order_id):
    # Security check: customer can only reorder from their own past orders.
    order = get_object_or_404(Order.objects.prefetch_related("items__product"), id=order_id, customer=request.user)
    cart = Cart(request)

    added_items = 0
    unavailable_products = []
    limited_stock_products = []

    for item in order.items.all():
        product = item.product
        if not product.is_orderable():
            unavailable_products.append(product.name)
            continue

        quantity_to_add = min(item.quantity, product.stock_quantity)
        if quantity_to_add < item.quantity:
            limited_stock_products.append(product.name)

        cart.add(product=product, quantity=quantity_to_add)
        added_items += 1

    if added_items:
        messages.success(request, f"Added {added_items} item(s) from this order back into your cart.")
    if unavailable_products:
        messages.warning(request, f"Skipped unavailable products: {', '.join(unavailable_products)}")
    if limited_stock_products:
        messages.warning(request, f"Some products were added with reduced quantity due to stock: {', '.join(limited_stock_products)}")
    if not added_items and not unavailable_products and not limited_stock_products:
        messages.info(request, "No items were added from this order.")

    return redirect("marketplace:cart_detail")


def category_products(request, slug):
    cart = Cart(request)
    category = get_object_or_404(Category, slug=slug)
    products = Product.objects.filter(
        category=category,
        availability_status__in=[Product.AVAILABLE, Product.IN_SEASON],
    )
    return render(
        request,
        "marketplace/category.html",
        {
            "category": category,
            "products": products,
            "cart_total_items": cart.get_total_items(),
        },
    )


def product_detail(request, pk):
    cart = Cart(request)
    product = get_object_or_404(
        Product,
        pk=pk,
        availability_status__in=[Product.AVAILABLE, Product.IN_SEASON],
    )
    return render(
        request,
        "marketplace/product_detail.html",
        {"product": product, "cart_total_items": cart.get_total_items()},
    )


def cart_detail(request):
    cart = Cart(request)
    return render(
        request,
        "marketplace/cart.html",
        {"cart": cart, "cart_total_items": cart.get_total_items()},
    )


@require_POST
def add_to_cart(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, pk=product_id)

    quantity_raw = request.POST.get("quantity", "1")
    try:
        quantity = int(quantity_raw)
    except (TypeError, ValueError):
        quantity = 1

    if quantity < 1:
        messages.error(request, "Quantity must be at least 1.")
        return redirect("marketplace:product_detail", pk=product.id)

    if product.availability_status not in [Product.AVAILABLE, Product.IN_SEASON]:
        messages.error(request, "This product is currently unavailable.")
        return redirect("marketplace:product_detail", pk=product.id)

    if product.seasonal_availability == Product.SEASON_OUT:
        messages.error(request, "This product is currently out of season.")
        return redirect("marketplace:product_detail", pk=product.id)

    if product.stock_quantity <= 0:
        messages.error(request, "This product is out of stock.")
        return redirect("marketplace:product_detail", pk=product.id)

    if quantity > product.stock_quantity:
        quantity = product.stock_quantity
        messages.warning(
            request,
            f"Only {product.stock_quantity} in stock. Added available quantity.",
        )

    cart.add(product=product, quantity=quantity)
    messages.success(request, f"Added {quantity} × {product.name} to cart.")

    next_url = request.POST.get("next", "").strip()
    if next_url:
        return redirect(next_url)

    return redirect("marketplace:cart_detail")


@require_POST
def update_cart_item(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, pk=product_id)

    quantity_raw = request.POST.get("quantity", "1")
    try:
        quantity = int(quantity_raw)
    except (TypeError, ValueError):
        quantity = 1

    if quantity <= 0:
        cart.remove(product)
        messages.success(request, f"Removed {product.name} from cart.")
    else:
        if quantity > product.stock_quantity:
            quantity = product.stock_quantity
            messages.warning(
                request,
                f"Only {product.stock_quantity} in stock. Quantity adjusted.",
            )
        cart.add(product=product, quantity=quantity, override_quantity=True)
        messages.success(request, f"Updated {product.name} quantity to {quantity}.")

    return redirect("marketplace:cart_detail")


@require_POST
def remove_from_cart(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, pk=product_id)
    cart.remove(product)
    messages.success(request, f"Removed {product.name} from cart.")
    return redirect("marketplace:cart_detail")


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
    # Security check: user must be logged in and must be a producer.
    permission_classes = [IsAuthenticated, IsProducerUser]

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
    # Security check: user must be logged in and must be a producer.
    permission_classes = [IsAuthenticated, IsProducerUser]

    def get_queryset(self):
        """Only allow editing own products"""
        producer = get_object_or_404(ProducerProfile, user=self.request.user)
        return Product.objects.filter(producer=producer)


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
