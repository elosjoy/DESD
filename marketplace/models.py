from django.conf import settings
from django.db import models


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

    STATUS_CHOICES = [
        (AVAILABLE, "Available"),
        (IN_SEASON, "In Season"),
        (UNAVAILABLE, "Unavailable"),
        (OUT_OF_SEASON, "Out of Season"),
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

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
