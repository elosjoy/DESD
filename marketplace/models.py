from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone


class CustomerProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=30)
    delivery_address = models.TextField()
    postcode = models.CharField(max_length=20)
    terms_accepted = models.BooleanField(default=False)
    terms_accepted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.full_name

# ProducerProfile and Product models are defined.
class ProducerProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    producer_name = models.CharField(max_length=200)
    contact_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=30)
    address = models.TextField()
    postcode = models.CharField(max_length=20)

    def __str__(self):
        return self.producer_name

# Category and Product models are defined.
class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

# Product model is defined with availability status choices and related fields.
class Product(models.Model):
    AVAILABLE = "AVAILABLE"
    IN_SEASON = "IN_SEASON"
    UNAVAILABLE = "UNAVAILABLE"
    OUT_OF_SEASON = "OUT_OF_SEASON"

    SEASON_IN = "IN_SEASON"
    SEASON_OUT = "OUT_OF_SEASON"
    SEASON_YEAR_ROUND = "YEAR_ROUND"

    STATUS_CHOICES = [
        (AVAILABLE, "Available"),
        (IN_SEASON, "In Season"),
        (UNAVAILABLE, "Unavailable"),
        (OUT_OF_SEASON, "Out of Season"),
    ]

    SEASONAL_AVAILABILITY_CHOICES = [
        (SEASON_IN, "In Season"),
        (SEASON_OUT, "Out of Season"),
        (SEASON_YEAR_ROUND, "Year-Round"),
    ]

    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    producer = models.ForeignKey(ProducerProfile, on_delete=models.CASCADE, related_name='products')
    description = models.TextField(blank=True)
    allergen_info = models.CharField(max_length=200, blank=True)
    harvest_date = models.DateField(null=True, blank=True)
    stock_quantity = models.IntegerField(default=0)
    availability_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=AVAILABLE)
    seasonal_availability = models.CharField(
        max_length=20,
        choices=SEASONAL_AVAILABILITY_CHOICES,
        default=SEASON_YEAR_ROUND,
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def is_orderable(self):
        if self.stock_quantity <= 0:
            return False
        if self.availability_status not in [self.AVAILABLE, self.IN_SEASON]:
            return False
        if self.seasonal_availability == self.SEASON_OUT:
            return False
        return True


class Order(models.Model):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    READY = "READY"
    DELIVERED = "DELIVERED"
    COMPLETED = "COMPLETED"

    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (CONFIRMED, "Confirmed"),
        (READY, "Ready"),
        (DELIVERED, "Delivered"),
        # Keep legacy value for compatibility with any existing data.
        (COMPLETED, "Completed (legacy)"),
    ]

    ALLOWED_STATUS_TRANSITIONS = {
        PENDING: [CONFIRMED],
        CONFIRMED: [READY],
        READY: [DELIVERED],
        DELIVERED: [],
        COMPLETED: [],
    }

    STATUS_STAGE = {
        PENDING: 1,
        CONFIRMED: 2,
        READY: 3,
        DELIVERED: 4,
        COMPLETED: 4,
    }

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.id}"

    def get_allowed_next_statuses(self):
        return self.ALLOWED_STATUS_TRANSITIONS.get(self.status, [])

    def can_transition_to(self, new_status):
        return new_status in self.get_allowed_next_statuses()

    def update_status(self, new_status, producer_note="", updated_by=None):
        if not self.can_transition_to(new_status):
            raise ValidationError(
                f"Invalid status transition from {self.status} to {new_status}."
            )

        self.status = new_status
        if new_status == self.DELIVERED:
            self.delivered_at = timezone.now()
        self.save(update_fields=["status", "delivered_at"])

        OrderStatusUpdate.objects.create(
            order=self,
            status=new_status,
            producer_note=producer_note,
            updated_by=updated_by,
        )

    def refresh_status_from_items(self):
        item_statuses = list(self.items.values_list("status", flat=True))
        if not item_statuses:
            return

        lowest_stage = min(self.STATUS_STAGE.get(status, 1) for status in item_statuses)
        stage_to_status = {
            1: self.PENDING,
            2: self.CONFIRMED,
            3: self.READY,
            4: self.DELIVERED,
        }
        new_status = stage_to_status[lowest_stage]

        if self.status != new_status:
            self.status = new_status

        if new_status == self.DELIVERED and self.delivered_at is None:
            self.delivered_at = timezone.now()
        elif new_status != self.DELIVERED:
            self.delivered_at = None

        self.save(update_fields=["status", "delivered_at"])


class OrderItem(models.Model):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    READY = "READY"
    DELIVERED = "DELIVERED"

    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (CONFIRMED, "Confirmed"),
        (READY, "Ready"),
        (DELIVERED, "Delivered"),
    ]

    ALLOWED_STATUS_TRANSITIONS = {
        PENDING: [CONFIRMED],
        CONFIRMED: [READY],
        READY: [DELIVERED],
        DELIVERED: [],
    }

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    producer = models.ForeignKey(
        ProducerProfile,
        on_delete=models.PROTECT,
        related_name="order_items",
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"OrderItem #{self.id}"

    def get_allowed_next_statuses(self):
        return self.ALLOWED_STATUS_TRANSITIONS.get(self.status, [])

    def can_transition_to(self, new_status):
        return new_status in self.get_allowed_next_statuses()

    def update_status(self, new_status, producer_note="", updated_by=None):
        if not self.can_transition_to(new_status):
            raise ValidationError(
                f"Invalid status transition from {self.status} to {new_status}."
            )

        self.status = new_status
        self.save(update_fields=["status"])

        OrderStatusUpdate.objects.create(
            order=self.order,
            order_item=self,
            status=new_status,
            producer_note=producer_note,
            updated_by=updated_by,
        )

        self.order.refresh_status_from_items()


class Settlement(models.Model):
    producer = models.ForeignKey(
        ProducerProfile,
        on_delete=models.CASCADE,
        related_name="settlements",
    )
    week_start = models.DateField()
    week_end = models.DateField()
    total_order_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    commission_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    producer_payment_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-week_start", "-created_at"]
        unique_together = ("producer", "week_start", "week_end")

    def __str__(self):
        return f"Settlement {self.week_start} - {self.week_end} ({self.producer})"


class OrderStatusUpdate(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="status_updates")
    order_item = models.ForeignKey(
        OrderItem,
        on_delete=models.CASCADE,
        related_name="status_updates",
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=20, choices=Order.STATUS_CHOICES)
    producer_note = models.TextField(blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_status_updates",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.order_id} -> {self.status}"
