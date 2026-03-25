from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .forms import CustomerRegistrationForm, ProducerRegistrationForm, ProducerProductForm
from rest_framework.decorators import api_view
from django.contrib.auth import authenticate, login
from .serializers import ProducerRegistrationSerializer, ProductSerializer
from .models import Category, Product, ProducerProfile
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

    is_producer = request.user.is_authenticated and ProducerProfile.objects.filter(user=request.user).exists()

    context = {
        "categories": categories,
        "search_query": query,
        "search_results": products,
        "search_performed": bool(query),
        "cart_total_items": cart.get_total_items(),
        "is_producer": is_producer,
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


from rest_framework.permissions import AllowAny
from rest_framework.decorators import permission_classes
from rest_framework.authentication import SessionAuthentication


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


from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt


class ProducerProductListCreateView(generics.ListCreateAPIView):
    """Producer can create and list their own products"""
    authentication_classes = [CsrfExemptSessionAuthentication]
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
    authentication_classes = [CsrfExemptSessionAuthentication]
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Only allow editing own products"""
        producer = get_object_or_404(ProducerProfile, user=self.request.user)
        return Product.objects.filter(producer=producer)
