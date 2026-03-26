from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Category, Order, OrderItem, ProducerProfile, Product


User = get_user_model()




class ProducerOrderStatusTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="customer2@example.com",
            email="customer2@example.com",
            password="TestPass123!",
        )
        producer_user_1 = User.objects.create_user(
            username="producer1@example.com",
            email="producer1@example.com",
            password="TestPass123!",
        )
        producer_user_2 = User.objects.create_user(
            username="producer2@example.com",
            email="producer2@example.com",
            password="TestPass123!",
        )

        self.producer_1 = ProducerProfile.objects.create(
            user=producer_user_1,
            producer_name="Farm One",
            contact_name="P1",
            phone="0123",
            address="A",
            postcode="AA1",
        )
        self.producer_2 = ProducerProfile.objects.create(
            user=producer_user_2,
            producer_name="Farm Two",
            contact_name="P2",
            phone="0456",
            address="B",
            postcode="BB1",
        )

        category = Category.objects.create(name="Veg", slug="veg")
        product_1 = Product.objects.create(
            name="Carrot",
            price=Decimal("1.00"),
            category=category,
            producer=self.producer_1,
            stock_quantity=10,
        )
        product_2 = Product.objects.create(
            name="Leek",
            price=Decimal("2.00"),
            category=category,
            producer=self.producer_2,
            stock_quantity=10,
        )

        self.order = Order.objects.create(customer=self.customer, status=Order.PENDING, total_amount=Decimal("5.00"))
        self.item_1 = OrderItem.objects.create(
            order=self.order,
            product=product_1,
            producer=self.producer_1,
            quantity=2,
            unit_price=Decimal("1.00"),
        )
        self.item_2 = OrderItem.objects.create(
            order=self.order,
            product=product_2,
            producer=self.producer_2,
            quantity=1,
            unit_price=Decimal("2.00"),
        )

    def test_producer_can_update_only_own_item_status(self):
        self.client.login(username="producer1@example.com", password="TestPass123!")

        response = self.client.post(
            reverse("marketplace:producer_update_order_status", args=[self.item_1.id]),
            {"new_status": OrderItem.CONFIRMED, "producer_note": "Preparing now"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.item_1.refresh_from_db()
        self.assertEqual(self.item_1.status, OrderItem.CONFIRMED)
        self.assertEqual(self.item_1.status_updates.count(), 1)

        forbidden_response = self.client.post(
            reverse("marketplace:producer_update_order_status", args=[self.item_2.id]),
            {"new_status": OrderItem.CONFIRMED},
        )
        self.assertEqual(forbidden_response.status_code, 404)

    def test_invalid_status_jump_is_blocked(self):
        self.client.login(username="producer1@example.com", password="TestPass123!")

        self.client.post(
            reverse("marketplace:producer_update_order_status", args=[self.item_1.id]),
            {"new_status": OrderItem.READY},
            follow=True,
        )

        self.item_1.refresh_from_db()
        self.assertEqual(self.item_1.status, OrderItem.PENDING)


class SeasonalAvailabilityTests(TestCase):
    def setUp(self):
        customer = User.objects.create_user(
            username="seasonal@example.com",
            email="seasonal@example.com",
            password="TestPass123!",
        )
        producer_user = User.objects.create_user(
            username="seasonal_producer@example.com",
            email="seasonal_producer@example.com",
            password="TestPass123!",
        )
        producer = ProducerProfile.objects.create(
            user=producer_user,
            producer_name="Season Farm",
            contact_name="Season Owner",
            phone="999",
            address="Season Street",
            postcode="SS1",
        )
        category = Category.objects.create(name="Herbs", slug="herbs")
        self.product = Product.objects.create(
            name="Basil",
            price=Decimal("1.20"),
            category=category,
            producer=producer,
            stock_quantity=4,
            availability_status=Product.AVAILABLE,
            seasonal_availability=Product.SEASON_OUT,
        )
        self.customer = customer

    def test_out_of_season_product_cannot_be_added_to_cart(self):
        self.client.login(username="seasonal@example.com", password="TestPass123!")
        response = self.client.post(
            reverse("marketplace:add_to_cart", args=[self.product.id]),
            {"quantity": 1},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        cart = self.client.session.get("cart", {})
        self.assertNotIn(str(self.product.id), cart)
