from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.db.models import Q, Sum, F, DecimalField, ExpressionWrapper
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login
from django.views.decorators.http import require_POST
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import permission_classes
from rest_framework.authentication import SessionAuthentication
from .forms import (
    CustomerRegistrationForm,
    ProducerRegistrationForm,
    ProducerProductForm,
    ProducerOrderStatusUpdateForm,
    ProductAvailabilityUpdateForm,
)
from .serializers import ProducerRegistrationSerializer, ProductSerializer, ProducerOrderItemSerializer
from .models import Category, Product, ProducerProfile, Order, OrderItem, Settlement, ProductUpdateHistory
from .permissions import IsProducerUser
from .cart import Cart
from django.contrib.auth import get_user_model

User = get_user_model()


def home(request):
    cart = Cart(request)
    categories = Category.objects.all()
    query = request.GET.get("q", "").strip()
    organic_filter = request.GET.get("organic", "").strip()
    allergen_presence = request.GET.get("allergen_presence", "").strip()
    allergen_query = request.GET.get("allergen", "").strip()
    min_price = request.GET.get("min_price", "").strip()
    max_price = request.GET.get("max_price", "").strip()

    # Show all products regardless of availability (template will mark unavailable items)
    products = Product.objects.select_related("producer", "category").all()

    if organic_filter == "certified":
        products = products.filter(is_certified_organic=True)
    elif organic_filter == "not_certified":
        products = products.filter(is_certified_organic=False)

    if allergen_presence == "contains":
        products = products.exclude(allergen_info__exact="")
        # Only apply allergen_query if looking for products that contain allergens
        if allergen_query:
            products = products.filter(allergen_info__icontains=allergen_query)
    elif allergen_presence == "none":
        products = products.filter(Q(allergen_info__exact="") | Q(allergen_info__iexact="No common allergens"))
        # Don't apply allergen_query when filtering for allergen-free items
    else:
        # If allergen_presence is not set, apply allergen_query as a general search
        if allergen_query:
            products = products.filter(allergen_info__icontains=allergen_query)

    if min_price:
        try:
            products = products.filter(price__gte=Decimal(min_price))
        except InvalidOperation:
            messages.error(request, "Min price must be a valid number.")

    if max_price:
        try:
            products = products.filter(price__lte=Decimal(max_price))
        except InvalidOperation:
            messages.error(request, "Max price must be a valid number.")

    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(producer__producer_name__icontains=query)
            | Q(allergen_info__icontains=query)
        )

    products = products.distinct()

    is_producer = request.user.is_authenticated and ProducerProfile.objects.filter(user=request.user).exists()

    context = {
        "categories": categories,
        "search_query": query,
        "search_results": products,
        "search_performed": bool(query or organic_filter or allergen_presence or allergen_query or min_price or max_price),
        "organic_filter": organic_filter,
        "allergen_presence": allergen_presence,
        "allergen_query": allergen_query,
        "min_price": min_price,
        "max_price": max_price,
        "cart_total_items": cart.get_total_items(),
        "is_producer": is_producer,
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
    recent_updates = ProductUpdateHistory.objects.filter(product__producer=producer).select_related("product")[:10]
    return render(
        request,
        "marketplace/producer_products.html",
        {"producer": producer, "products": products, "recent_updates": recent_updates},
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
            ProductUpdateHistory.objects.create(
                product=product,
                changed_by=request.user,
                action=ProductUpdateHistory.ACTION_CREATE,
                new_stock_quantity=product.stock_quantity,
                new_availability_status=product.availability_status,
            )
            messages.success(request, "Product listed successfully.")
            if product.stock_quantity <= 5:
                messages.warning(request, f"Low stock alert: {product.name} has only {product.stock_quantity} left.")
            return redirect("marketplace:producer_products")
    else:
        form = ProducerProductForm()

    return render(request, "marketplace/producer_product_form.html", {"form": form})


@login_required
@require_POST
def producer_update_product_availability(request, product_id):
    # Security check: producer can only update their own products.
    try:
        producer = ProducerProfile.objects.get(user=request.user)
    except ProducerProfile.DoesNotExist:
        messages.error(request, "Only producer accounts can update product availability.")
        return redirect("marketplace:home")

    product = get_object_or_404(Product, id=product_id, producer=producer)
    form = ProductAvailabilityUpdateForm(request.POST, instance=product)

    if form.is_valid():
        previous_stock = product.stock_quantity
        previous_status = product.availability_status

        if 'availability_status' in request.POST and request.POST.get('availability_status'):
            product.availability_status = form.cleaned_data['availability_status']
        if 'stock_quantity' in request.POST:
            try:
                product.stock_quantity = int(request.POST.get('stock_quantity', product.stock_quantity))
            except (ValueError, TypeError):
                pass

        product.save(update_fields=["availability_status", "stock_quantity"])
        ProductUpdateHistory.objects.create(
            product=product,
            changed_by=request.user,
            action=ProductUpdateHistory.ACTION_STOCK_UPDATE,
            previous_stock_quantity=previous_stock,
            new_stock_quantity=product.stock_quantity,
            previous_availability_status=previous_status,
            new_availability_status=product.availability_status,
        )
        messages.success(
            request,
            f"Updated {product.name}: {product.get_availability_status_display()}, Stock: {product.stock_quantity}",
        )
    else:
        error_msg = "; ".join([f"{field}: {error}" for field, errors in form.errors.items() for error in errors])
        messages.error(request, f"Failed to update: {error_msg}")

    return redirect("marketplace:producer_products")


@login_required
def producer_product_edit(request, pk):
    producer = get_object_or_404(ProducerProfile, user=request.user)
    product = get_object_or_404(Product, pk=pk, producer=producer)

    if request.method == "POST":
        previous_stock = product.stock_quantity
        previous_status = product.availability_status
        form = ProducerProductForm(request.POST, instance=product)
        if form.is_valid():
            updated = form.save(commit=False)
            updated.producer = producer
            updated.save()
            ProductUpdateHistory.objects.create(
                product=updated,
                changed_by=request.user,
                action=ProductUpdateHistory.ACTION_UPDATE,
                previous_stock_quantity=previous_stock,
                new_stock_quantity=updated.stock_quantity,
                previous_availability_status=previous_status,
                new_availability_status=updated.availability_status,
            )
            messages.success(request, "Product updated successfully.")
            if updated.stock_quantity <= 5:
                messages.warning(request, f"Low stock alert: {updated.name} has only {updated.stock_quantity} left.")
            return redirect("marketplace:producer_products")
    else:
        form = ProducerProductForm(instance=product)

    return render(
        request,
        "marketplace/producer_product_form.html",
        {"form": form, "product": product},
    )


@login_required
@require_POST
def producer_product_delete(request, pk):
    producer = get_object_or_404(ProducerProfile, user=request.user)
    product = get_object_or_404(Product, pk=pk, producer=producer)
    product_name = product.name
    product.delete()
    messages.success(request, f"Removed product: {product_name}.")
    return redirect("marketplace:producer_products")


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


@login_required
@require_POST
def producer_product_update_stock(request, pk):
    producer = get_object_or_404(ProducerProfile, user=request.user)
    product = get_object_or_404(Product, pk=pk, producer=producer)
    previous_stock = product.stock_quantity
    previous_status = product.availability_status

    quantity_raw = request.POST.get("stock_quantity", "")
    try:
        quantity = int(quantity_raw)
    except (TypeError, ValueError):
        messages.error(request, "Stock quantity must be a valid number.")
        return redirect("marketplace:producer_products")

    if quantity < 0:
        messages.error(request, "Stock quantity cannot be negative.")
        return redirect("marketplace:producer_products")

    product.stock_quantity = quantity
    product.save(update_fields=["stock_quantity"])
    ProductUpdateHistory.objects.create(
        product=product,
        changed_by=request.user,
        action=ProductUpdateHistory.ACTION_STOCK_UPDATE,
        previous_stock_quantity=previous_stock,
        new_stock_quantity=quantity,
        previous_availability_status=previous_status,
        new_availability_status=product.availability_status,
    )
    messages.success(request, f"Updated stock for {product.name} to {quantity}.")
    if quantity <= 5:
        messages.warning(request, f"Low stock alert: {product.name} has only {quantity} left.")
    return redirect("marketplace:producer_products")


def category_products(request, slug):
    cart = Cart(request)
    category = get_object_or_404(Category, slug=slug)
    organic_filter = request.GET.get("organic", "").strip()
    allergen_presence = request.GET.get("allergen_presence", "").strip()
    allergen_query = request.GET.get("allergen", "").strip()
    min_price = request.GET.get("min_price", "").strip()
    max_price = request.GET.get("max_price", "").strip()

    products = Product.objects.filter(
        category=category,
        availability_status__in=[Product.AVAILABLE, Product.IN_SEASON],
    )

    if organic_filter == "certified":
        products = products.filter(is_certified_organic=True)
    elif organic_filter == "not_certified":
        products = products.filter(is_certified_organic=False)

    if allergen_presence == "contains":
        products = products.exclude(allergen_info__exact="")
    elif allergen_presence == "none":
        products = products.filter(Q(allergen_info__exact="") | Q(allergen_info__iexact="No common allergens"))

    if allergen_query:
        products = products.filter(allergen_info__icontains=allergen_query)

    if min_price:
        try:
            products = products.filter(price__gte=Decimal(min_price))
        except InvalidOperation:
            messages.error(request, "Min price must be a valid number.")

    if max_price:
        try:
            products = products.filter(price__lte=Decimal(max_price))
        except InvalidOperation:
            messages.error(request, "Max price must be a valid number.")

    return render(
        request,
        "marketplace/category.html",
        {
            "category": category,
            "products": products,
            "organic_filter": organic_filter,
            "allergen_presence": allergen_presence,
            "allergen_query": allergen_query,
            "min_price": min_price,
            "max_price": max_price,
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


@login_required
@require_POST
def submit_cart(request):
    cart = Cart(request)
    cart_items = list(cart)

    if not cart_items:
        messages.error(request, "Your cart is empty.")
        return redirect("marketplace:cart_detail")

    unavailable = []
    insufficient_stock = []
    total_amount = Decimal("0.00")

    for item in cart_items:
        product = item["product"]
        quantity = item["quantity"]

        if not product.is_orderable():
            unavailable.append(product.name)
            continue

        if quantity > product.stock_quantity:
            insufficient_stock.append(f"{product.name} (available: {product.stock_quantity})")
            continue

        total_amount += product.price * quantity

    if unavailable or insufficient_stock:
        if unavailable:
            messages.error(request, f"These products are no longer orderable: {', '.join(unavailable)}")
        if insufficient_stock:
            messages.error(request, f"Insufficient stock for: {', '.join(insufficient_stock)}")
        messages.info(request, "Please update your cart and try again.")
        return redirect("marketplace:cart_detail")

    with transaction.atomic():
        order = Order.objects.create(
            customer=request.user,
            status=Order.PENDING,
            total_amount=total_amount,
        )

        for item in cart_items:
            product = item["product"]
            quantity = item["quantity"]

            OrderItem.objects.create(
                order=order,
                product=product,
                producer=product.producer,
                quantity=quantity,
                unit_price=product.price,
                status=OrderItem.PENDING,
            )

            product.stock_quantity -= quantity
            if product.stock_quantity == 0:
                product.availability_status = Product.UNAVAILABLE
                product.save(update_fields=["stock_quantity", "availability_status"])
            else:
                product.save(update_fields=["stock_quantity"])

    cart.clear()
    messages.success(request, f"Order #{order.id} submitted successfully.")
    return redirect("marketplace:customer_order_detail", order_id=order.id)


@require_POST
def add_to_cart(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, pk=product_id)

    allergen_ack = request.POST.get("allergen_ack") == "on"
    if not allergen_ack:
        messages.error(request, "Please review and acknowledge allergen information before adding this item to cart.")
        return redirect("marketplace:product_detail", pk=product.id)

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


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """Session auth that does not enforce CSRF checks."""
    def enforce_csrf(self, request):
        return  # skip CSRF check


@api_view(['POST'])
@permission_classes([AllowAny])
def producer_login(request):
    """Login endpoint for producers"""
    email = request.data.get('email')
    password = request.data.get('password')
    
    user = authenticate(username=email, password=password)
    if user and hasattr(user, 'producerprofile'):
        login(request, user)
        return Response({"detail": "Logged in successfully"})
    return Response({"detail": "Invalid credentials"}, status=400)

class ProducerProductListCreateView(generics.ListCreateAPIView):
    """Producer can create and list their own products"""
    authentication_classes = [CsrfExemptSessionAuthentication]
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
    authentication_classes = [CsrfExemptSessionAuthentication]
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
