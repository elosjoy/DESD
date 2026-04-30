from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Category, Order, OrderItem, ProducerProfile, Product


User = get_user_model()


class CustomerOrderHistoryTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="customer@example.com",
            email="customer@example.com",
            password="TestPass123!",
        )
        self.other_customer = User.objects.create_user(
            username="other@example.com",
            email="other@example.com",
            password="TestPass123!",
        )

        producer_user = User.objects.create_user(
            username="producer@example.com",
            email="producer@example.com",
            password="TestPass123!",
        )
        self.producer = ProducerProfile.objects.create(
            user=producer_user,
            producer_name="Farm One",
            contact_name="Farmer One",
            phone="0123",
            address="Farm Lane",
            postcode="AB1 2CD",
        )

        self.category = Category.objects.create(name="Fruit", slug="fruit")
        self.available_product = Product.objects.create(
            name="Apples",
            price=Decimal("2.00"),
            category=self.category,
            producer=self.producer,
            stock_quantity=5,
            availability_status=Product.AVAILABLE,
        )
        self.unavailable_product = Product.objects.create(
            name="Pears",
            price=Decimal("3.00"),
            category=self.category,
            producer=self.producer,
            stock_quantity=0,
            availability_status=Product.UNAVAILABLE,
        )

    def test_customer_order_history_shows_only_own_orders_most_recent_first(self):
        older_order = Order.objects.create(customer=self.customer, status=Order.PENDING, total_amount=Decimal("10.00"))
        newer_order = Order.objects.create(customer=self.customer, status=Order.CONFIRMED, total_amount=Decimal("20.00"))
        other_order = Order.objects.create(customer=self.other_customer, status=Order.PENDING, total_amount=Decimal("30.00"))

        self.client.login(username="customer@example.com", password="TestPass123!")
        response = self.client.get(reverse("marketplace:customer_orders"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, f"#{other_order.id}")

        body = response.content.decode("utf-8")
        self.assertLess(
            body.find(f"<td>#{newer_order.id}</td>"),
            body.find(f"<td>#{older_order.id}</td>"),
        )

    def test_customer_order_detail_is_customer_scoped(self):
        own_order = Order.objects.create(customer=self.customer, status=Order.PENDING, total_amount=Decimal("10.00"))
        other_order = Order.objects.create(customer=self.other_customer, status=Order.PENDING, total_amount=Decimal("8.00"))

        self.client.login(username="customer@example.com", password="TestPass123!")

        own_response = self.client.get(reverse("marketplace:customer_order_detail", args=[own_order.id]))
        other_response = self.client.get(reverse("marketplace:customer_order_detail", args=[other_order.id]))

        self.assertEqual(own_response.status_code, 200)
        self.assertEqual(other_response.status_code, 404)

    def test_reorder_adds_available_items_and_skips_unavailable(self):
        order = Order.objects.create(customer=self.customer, status=Order.DELIVERED, total_amount=Decimal("17.00"))
        OrderItem.objects.create(
            order=order,
            product=self.available_product,
            producer=self.producer,
            quantity=3,
            unit_price=Decimal("2.00"),
        )
        OrderItem.objects.create(
            order=order,
            product=self.unavailable_product,
            producer=self.producer,
            quantity=2,
            unit_price=Decimal("3.00"),
        )

        self.client.login(username="customer@example.com", password="TestPass123!")
        response = self.client.post(reverse("marketplace:reorder_from_order", args=[order.id]), follow=True)

        self.assertEqual(response.status_code, 200)

        cart = self.client.session.get("cart", {})
        self.assertIn(str(self.available_product.id), cart)
        self.assertEqual(cart[str(self.available_product.id)]["quantity"], 3)
        self.assertNotIn(str(self.unavailable_product.id), cart)

        messages = [m.message for m in response.context["messages"]]
        self.assertTrue(any("Skipped unavailable products" in message for message in messages))


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


# ---------------------------------------------------------------------------
# TC-001: Producer registration
# ---------------------------------------------------------------------------

class ProducerRegistrationTests(TestCase):
    def test_html_form_creates_user_and_producer_profile(self):
        response = self.client.post(
            reverse("marketplace:register_producer"),
            {
                "producer_name": "Green Fields Farm",
                "contact_name": "Alice Farmer",
                "email": "alice@farm.com",
                "phone": "07700900000",
                "address": "1 Farm Lane",
                "postcode": "AB1 2CD",
                "password1": "StrongPass99!",
                "password2": "StrongPass99!",
            },
        )
        self.assertRedirects(response, reverse("login"))
        self.assertTrue(User.objects.filter(username="alice@farm.com").exists())
        user = User.objects.get(username="alice@farm.com")
        self.assertTrue(
            ProducerProfile.objects.filter(user=user, producer_name="Green Fields Farm").exists()
        )

    def test_mismatched_passwords_rejected(self):
        response = self.client.post(
            reverse("marketplace:register_producer"),
            {
                "producer_name": "Farm",
                "contact_name": "Bob",
                "email": "bob@farm.com",
                "phone": "0",
                "address": "1 Lane",
                "postcode": "X1",
                "password1": "StrongPass99!",
                "password2": "WrongPass99!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="bob@farm.com").exists())

    def test_duplicate_email_rejected(self):
        User.objects.create_user(username="dup@farm.com", email="dup@farm.com", password="pass")
        response = self.client.post(
            reverse("marketplace:register_producer"),
            {
                "producer_name": "Farm",
                "contact_name": "Dup",
                "email": "dup@farm.com",
                "phone": "0",
                "address": "1 Lane",
                "postcode": "X1",
                "password1": "StrongPass99!",
                "password2": "StrongPass99!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.filter(username="dup@farm.com").count(), 1)

    def test_api_endpoint_creates_producer(self):
        response = self.client.post(
            reverse("marketplace:producer-register"),
            {
                "producer_name": "API Farm",
                "contact_name": "API Owner",
                "email": "api@farm.com",
                "phone": "07700900001",
                "address": "2 API Lane",
                "postcode": "AP1 2CD",
                "password": "StrongPass99!",
                "password_confirm": "StrongPass99!",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(User.objects.filter(username="api@farm.com").exists())


# ---------------------------------------------------------------------------
# TC-002: Customer registration
# ---------------------------------------------------------------------------

class CustomerRegistrationTests(TestCase):
    def test_registration_creates_user_and_customer_profile(self):
        from .models import CustomerProfile
        response = self.client.post(
            reverse("marketplace:register_customer"),
            {
                "full_name": "Jane Doe",
                "email": "jane@example.com",
                "phone": "07700900002",
                "delivery_address": "10 High Street",
                "postcode": "EC1A 1BB",
                "password1": "StrongPass99!",
                "password2": "StrongPass99!",
                "accept_terms": "on",
            },
        )
        self.assertRedirects(response, reverse("login"))
        self.assertTrue(User.objects.filter(username="jane@example.com").exists())
        user = User.objects.get(username="jane@example.com")
        self.assertTrue(CustomerProfile.objects.filter(user=user, postcode="EC1A 1BB").exists())

    def test_missing_terms_checkbox_rejected(self):
        response = self.client.post(
            reverse("marketplace:register_customer"),
            {
                "full_name": "No Terms",
                "email": "noterms@example.com",
                "phone": "0",
                "delivery_address": "1 Street",
                "postcode": "X1",
                "password1": "StrongPass99!",
                "password2": "StrongPass99!",
                # accept_terms omitted
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="noterms@example.com").exists())

    def test_duplicate_email_rejected(self):
        User.objects.create_user(username="taken@example.com", email="taken@example.com", password="pass")
        response = self.client.post(
            reverse("marketplace:register_customer"),
            {
                "full_name": "Dup",
                "email": "taken@example.com",
                "phone": "0",
                "delivery_address": "1 St",
                "postcode": "X1",
                "password1": "StrongPass99!",
                "password2": "StrongPass99!",
                "accept_terms": "on",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.filter(username="taken@example.com").count(), 1)


# ---------------------------------------------------------------------------
# TC-022: Authentication & Authorisation
# ---------------------------------------------------------------------------

class AuthorisationTests(TestCase):
    def setUp(self):
        self.customer_user = User.objects.create_user(
            username="cust@example.com", email="cust@example.com", password="TestPass123!"
        )
        producer_user = User.objects.create_user(
            username="prod@example.com", email="prod@example.com", password="TestPass123!"
        )
        self.producer_profile = ProducerProfile.objects.create(
            user=producer_user,
            producer_name="Auth Farm",
            contact_name="Auth Owner",
            phone="0",
            address="X",
            postcode="X1",
        )

    def test_unauthenticated_redirected_from_producer_pages(self):
        protected_urls = [
            reverse("marketplace:producer_products"),
            reverse("marketplace:producer_product_create"),
            reverse("marketplace:producer_orders"),
            reverse("marketplace:producer_weekly_settlement"),
        ]
        for url in protected_urls:
            response = self.client.get(url)
            self.assertIn(response.status_code, [302, 301], msg=f"Expected redirect for {url}")
            self.assertIn("/login", response["Location"], msg=f"Expected login redirect for {url}")

    def test_unauthenticated_redirected_from_customer_pages(self):
        response = self.client.get(reverse("marketplace:customer_orders"))
        self.assertIn(response.status_code, [302, 301])
        self.assertIn("/login", response["Location"])

    def test_customer_cannot_access_producer_dashboard(self):
        self.client.login(username="cust@example.com", password="TestPass123!")
        response = self.client.get(reverse("marketplace:producer_products"), follow=True)
        self.assertEqual(response.status_code, 200)
        # Should be redirected to register_producer (no producer profile)
        self.assertRedirects(response, reverse("marketplace:register_producer"))

    def test_producer_can_access_own_dashboard(self):
        self.client.login(username="prod@example.com", password="TestPass123!")
        response = self.client.get(reverse("marketplace:producer_products"))
        self.assertEqual(response.status_code, 200)

    def test_password_is_hashed_not_plaintext(self):
        user = User.objects.get(username="cust@example.com")
        self.assertNotEqual(user.password, "TestPass123!")
        self.assertTrue(user.password.startswith("pbkdf2_") or user.password.startswith("bcrypt") or "$" in user.password)

    def test_api_producer_products_requires_auth(self):
        response = self.client.get(reverse("marketplace:producer-products"))
        self.assertEqual(response.status_code, 403)

    def test_api_producer_products_rejects_customer(self):
        self.client.login(username="cust@example.com", password="TestPass123!")
        response = self.client.get(reverse("marketplace:producer-products"))
        self.assertEqual(response.status_code, 403)


# ---------------------------------------------------------------------------
# TC-003: Create product
# ---------------------------------------------------------------------------

class ProductCreateTests(TestCase):
    def setUp(self):
        producer_user = User.objects.create_user(
            username="creator@farm.com", email="creator@farm.com", password="TestPass123!"
        )
        self.producer = ProducerProfile.objects.create(
            user=producer_user,
            producer_name="Creator Farm",
            contact_name="Creator",
            phone="0",
            address="X",
            postcode="X1",
        )
        self.category = Category.objects.create(name="Dairy", slug="dairy")
        self.client.login(username="creator@farm.com", password="TestPass123!")

    def test_producer_can_create_product(self):
        response = self.client.post(
            reverse("marketplace:producer_product_create"),
            {
                "name": "Fresh Milk",
                "price": "1.50",
                "unit": "litre",
                "stock_quantity": "20",
                "category": self.category.id,
                "description": "Full-fat milk",
                "allergen_info": "Contains milk",
                "availability_status": Product.AVAILABLE,
                "seasonal_availability": Product.SEASON_YEAR_ROUND,
                "is_certified_organic": False,
            },
        )
        self.assertRedirects(response, reverse("marketplace:producer_products"))
        self.assertTrue(Product.objects.filter(name="Fresh Milk", producer=self.producer).exists())

    def test_product_linked_to_logged_in_producer(self):
        response = self.client.post(
            reverse("marketplace:producer_product_create"),
            {
                "name": "Goat Cheese",
                "price": "3.00",
                "unit": "block",
                "stock_quantity": "10",
                "category": self.category.id,
                "description": "",
                "allergen_info": "None",
                "availability_status": Product.AVAILABLE,
                "seasonal_availability": Product.SEASON_YEAR_ROUND,
                "is_certified_organic": False,
            },
        )
        self.assertRedirects(response, reverse("marketplace:producer_products"))
        product = Product.objects.get(name="Goat Cheese")
        self.assertEqual(product.producer, self.producer)

    def test_customer_cannot_create_product(self):
        self.client.logout()
        customer_user = User.objects.create_user(
            username="shopper@example.com", email="shopper@example.com", password="TestPass123!"
        )
        self.client.login(username="shopper@example.com", password="TestPass123!")
        response = self.client.get(reverse("marketplace:producer_product_create"), follow=True)
        self.assertRedirects(response, reverse("marketplace:register_producer"))


# ---------------------------------------------------------------------------
# TC-004: Browse by category
# ---------------------------------------------------------------------------

class CategoryBrowseTests(TestCase):
    def setUp(self):
        producer_user = User.objects.create_user(
            username="cat_producer@farm.com", email="cat_producer@farm.com", password="TestPass123!"
        )
        self.producer = ProducerProfile.objects.create(
            user=producer_user, producer_name="Cat Farm", contact_name="C",
            phone="0", address="X", postcode="X1",
        )
        self.fruit = Category.objects.create(name="Fruit", slug="fruit-cat")
        self.veg = Category.objects.create(name="Veg", slug="veg-cat")

        self.apple = Product.objects.create(
            name="Apple", price=Decimal("1.00"), category=self.fruit,
            producer=self.producer, stock_quantity=10, availability_status=Product.AVAILABLE,
        )
        self.carrot = Product.objects.create(
            name="Carrot", price=Decimal("0.50"), category=self.veg,
            producer=self.producer, stock_quantity=10, availability_status=Product.AVAILABLE,
        )
        self.unavailable = Product.objects.create(
            name="OldFruit", price=Decimal("0.10"), category=self.fruit,
            producer=self.producer, stock_quantity=0, availability_status=Product.UNAVAILABLE,
        )

    def test_category_page_shows_only_that_categorys_available_products(self):
        response = self.client.get(reverse("marketplace:category_products", args=["fruit-cat"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Apple")
        self.assertNotContains(response, "Carrot")
        self.assertNotContains(response, "OldFruit")

    def test_unknown_category_returns_404(self):
        response = self.client.get(reverse("marketplace:category_products", args=["nonexistent"]))
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# TC-015: Allergen display
# ---------------------------------------------------------------------------

class AllergenTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="allergen_cust@example.com", email="allergen_cust@example.com", password="TestPass123!"
        )
        producer_user = User.objects.create_user(
            username="allergen_prod@farm.com", email="allergen_prod@farm.com", password="TestPass123!"
        )
        producer = ProducerProfile.objects.create(
            user=producer_user, producer_name="Allergen Farm", contact_name="A",
            phone="0", address="X", postcode="X1",
        )
        category = Category.objects.create(name="Baked", slug="baked")
        self.product_with_allergen = Product.objects.create(
            name="Bread", price=Decimal("2.00"), category=category,
            producer=producer, stock_quantity=10,
            availability_status=Product.AVAILABLE,
            allergen_info="Contains gluten, wheat",
        )
        self.product_no_allergen = Product.objects.create(
            name="Rice", price=Decimal("1.00"), category=category,
            producer=producer, stock_quantity=10,
            availability_status=Product.AVAILABLE,
            allergen_info="",
        )

    def test_allergen_info_displayed_on_product_detail(self):
        response = self.client.get(
            reverse("marketplace:product_detail", args=[self.product_with_allergen.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "gluten")

    def test_add_to_cart_blocked_without_allergen_acknowledgement(self):
        self.client.login(username="allergen_cust@example.com", password="TestPass123!")
        response = self.client.post(
            reverse("marketplace:add_to_cart", args=[self.product_with_allergen.id]),
            {"quantity": "1"},  # allergen_ack missing
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        cart = self.client.session.get("cart", {})
        self.assertNotIn(str(self.product_with_allergen.id), cart)

    def test_add_to_cart_succeeds_with_allergen_acknowledgement(self):
        self.client.login(username="allergen_cust@example.com", password="TestPass123!")
        response = self.client.post(
            reverse("marketplace:add_to_cart", args=[self.product_with_allergen.id]),
            {"quantity": "1", "allergen_ack": "on"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        cart = self.client.session.get("cart", {})
        self.assertIn(str(self.product_with_allergen.id), cart)

    def test_allergen_filter_contains(self):
        response = self.client.get(reverse("marketplace:home") + "?allergen_presence=contains")
        self.assertContains(response, "Bread")
        self.assertNotContains(response, "Rice")

    def test_allergen_filter_none(self):
        response = self.client.get(reverse("marketplace:home") + "?allergen_presence=none")
        self.assertNotContains(response, "Bread")
        self.assertContains(response, "Rice")


# ---------------------------------------------------------------------------
# TC-006: Add to cart
# ---------------------------------------------------------------------------

class CartTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="cart_cust@example.com", email="cart_cust@example.com", password="TestPass123!"
        )
        producer_user = User.objects.create_user(
            username="cart_prod@farm.com", email="cart_prod@farm.com", password="TestPass123!"
        )
        producer = ProducerProfile.objects.create(
            user=producer_user, producer_name="Cart Farm", contact_name="C",
            phone="0", address="X", postcode="X1",
        )
        category = Category.objects.create(name="Cart Category", slug="cart-cat")
        self.product = Product.objects.create(
            name="Cart Apple", price=Decimal("1.00"), category=category,
            producer=producer, stock_quantity=10, availability_status=Product.AVAILABLE,
        )
        self.out_of_stock = Product.objects.create(
            name="Gone Product", price=Decimal("1.00"), category=category,
            producer=producer, stock_quantity=0, availability_status=Product.UNAVAILABLE,
        )
        self.client.login(username="cart_cust@example.com", password="TestPass123!")

    def test_add_item_to_cart(self):
        self.client.post(
            reverse("marketplace:add_to_cart", args=[self.product.id]),
            {"quantity": "2", "allergen_ack": "on"},
        )
        cart = self.client.session.get("cart", {})
        self.assertIn(str(self.product.id), cart)
        self.assertEqual(cart[str(self.product.id)]["quantity"], 2)

    def test_update_cart_quantity(self):
        self.client.post(
            reverse("marketplace:add_to_cart", args=[self.product.id]),
            {"quantity": "2", "allergen_ack": "on"},
        )
        self.client.post(
            reverse("marketplace:update_cart_item", args=[self.product.id]),
            {"quantity": "5"},
        )
        cart = self.client.session.get("cart", {})
        self.assertEqual(cart[str(self.product.id)]["quantity"], 5)

    def test_remove_item_from_cart(self):
        self.client.post(
            reverse("marketplace:add_to_cart", args=[self.product.id]),
            {"quantity": "1", "allergen_ack": "on"},
        )
        self.client.post(reverse("marketplace:remove_from_cart", args=[self.product.id]))
        cart = self.client.session.get("cart", {})
        self.assertNotIn(str(self.product.id), cart)

    def test_quantity_capped_at_stock_level(self):
        self.client.post(
            reverse("marketplace:add_to_cart", args=[self.product.id]),
            {"quantity": "999", "allergen_ack": "on"},
        )
        cart = self.client.session.get("cart", {})
        self.assertEqual(cart[str(self.product.id)]["quantity"], self.product.stock_quantity)

    def test_out_of_stock_product_blocked(self):
        self.client.post(
            reverse("marketplace:add_to_cart", args=[self.out_of_stock.id]),
            {"quantity": "1", "allergen_ack": "on"},
        )
        cart = self.client.session.get("cart", {})
        self.assertNotIn(str(self.out_of_stock.id), cart)

    def test_cart_detail_page_loads(self):
        response = self.client.get(reverse("marketplace:cart_detail"))
        self.assertEqual(response.status_code, 200)


# ---------------------------------------------------------------------------
# TC-007: Single producer checkout & TC-008: Multi-producer checkout
# ---------------------------------------------------------------------------

class CheckoutTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="checkout_cust@example.com", email="checkout_cust@example.com", password="TestPass123!"
        )
        producer_user_1 = User.objects.create_user(
            username="checkout_prod1@farm.com", email="checkout_prod1@farm.com", password="TestPass123!"
        )
        producer_user_2 = User.objects.create_user(
            username="checkout_prod2@farm.com", email="checkout_prod2@farm.com", password="TestPass123!"
        )
        self.producer_1 = ProducerProfile.objects.create(
            user=producer_user_1, producer_name="Checkout Farm 1", contact_name="P1",
            phone="0", address="X", postcode="X1",
        )
        self.producer_2 = ProducerProfile.objects.create(
            user=producer_user_2, producer_name="Checkout Farm 2", contact_name="P2",
            phone="0", address="Y", postcode="Y1",
        )
        category = Category.objects.create(name="Checkout Cat", slug="checkout-cat")
        self.product_1 = Product.objects.create(
            name="Checkout Apple", price=Decimal("2.00"), category=category,
            producer=self.producer_1, stock_quantity=10, availability_status=Product.AVAILABLE,
        )
        self.product_2 = Product.objects.create(
            name="Checkout Leek", price=Decimal("3.00"), category=category,
            producer=self.producer_2, stock_quantity=10, availability_status=Product.AVAILABLE,
        )
        self.client.login(username="checkout_cust@example.com", password="TestPass123!")

    def _add_to_cart(self, product, quantity=2):
        self.client.post(
            reverse("marketplace:add_to_cart", args=[product.id]),
            {"quantity": str(quantity), "allergen_ack": "on"},
        )

    def test_single_producer_checkout_creates_order_and_items(self):
        self._add_to_cart(self.product_1, 2)
        response = self.client.post(reverse("marketplace:submit_cart"), follow=True)
        self.assertEqual(response.status_code, 200)

        order = Order.objects.filter(customer=self.customer).first()
        self.assertIsNotNone(order)
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.first().product, self.product_1)
        self.assertEqual(order.items.first().quantity, 2)
        self.assertEqual(order.total_amount, Decimal("4.00"))

        # Stock should be decremented
        self.product_1.refresh_from_db()
        self.assertEqual(self.product_1.stock_quantity, 8)

    def test_checkout_clears_cart(self):
        self._add_to_cart(self.product_1, 1)
        self.client.post(reverse("marketplace:submit_cart"), follow=True)
        cart = self.client.session.get("cart", {})
        self.assertEqual(cart, {})

    def test_multi_producer_checkout_creates_correct_order_items(self):
        self._add_to_cart(self.product_1, 1)
        self._add_to_cart(self.product_2, 2)
        self.client.post(reverse("marketplace:submit_cart"), follow=True)

        order = Order.objects.filter(customer=self.customer).first()
        self.assertIsNotNone(order)
        self.assertEqual(order.items.count(), 2)

        producers_in_order = set(order.items.values_list("producer_id", flat=True))
        self.assertIn(self.producer_1.id, producers_in_order)
        self.assertIn(self.producer_2.id, producers_in_order)

    def test_multi_producer_order_total_is_correct(self):
        self._add_to_cart(self.product_1, 1)  # -ú2.00
        self._add_to_cart(self.product_2, 2)  # -ú6.00
        self.client.post(reverse("marketplace:submit_cart"), follow=True)

        order = Order.objects.filter(customer=self.customer).first()
        self.assertEqual(order.total_amount, Decimal("8.00"))

    def test_empty_cart_checkout_rejected(self):
        response = self.client.post(reverse("marketplace:submit_cart"), follow=True)
        self.assertFalse(Order.objects.filter(customer=self.customer).exists())

    def test_checkout_blocked_when_insufficient_stock(self):
        self.product_1.stock_quantity = 1
        self.product_1.save()
        self._add_to_cart(self.product_1, 1)
        # Manually inject a higher quantity into the session cart
        session = self.client.session
        session["cart"] = {str(self.product_1.id): {"quantity": 99, "price": "2.00"}}
        session.save()

        self.client.post(reverse("marketplace:submit_cart"), follow=True)
        self.assertFalse(Order.objects.filter(customer=self.customer).exists())


# ---------------------------------------------------------------------------
# TC-009: Producer view orders
# ---------------------------------------------------------------------------

class ProducerViewOrdersTests(TestCase):
    def setUp(self):
        customer = User.objects.create_user(
            username="orders_cust@example.com", email="orders_cust@example.com", password="TestPass123!"
        )
        prod_user_1 = User.objects.create_user(
            username="orders_prod1@farm.com", email="orders_prod1@farm.com", password="TestPass123!"
        )
        prod_user_2 = User.objects.create_user(
            username="orders_prod2@farm.com", email="orders_prod2@farm.com", password="TestPass123!"
        )
        self.producer_1 = ProducerProfile.objects.create(
            user=prod_user_1, producer_name="Orders Farm 1", contact_name="P1",
            phone="0", address="X", postcode="X1",
        )
        self.producer_2 = ProducerProfile.objects.create(
            user=prod_user_2, producer_name="Orders Farm 2", contact_name="P2",
            phone="0", address="Y", postcode="Y1",
        )
        category = Category.objects.create(name="Orders Cat", slug="orders-cat")
        product_1 = Product.objects.create(
            name="Farm 1 Apple", price=Decimal("1.00"), category=category,
            producer=self.producer_1, stock_quantity=10,
        )
        product_2 = Product.objects.create(
            name="Farm 2 Leek", price=Decimal("2.00"), category=category,
            producer=self.producer_2, stock_quantity=10,
        )
        order = Order.objects.create(customer=customer, status=Order.PENDING, total_amount=Decimal("3.00"))
        self.item_1 = OrderItem.objects.create(
            order=order, product=product_1, producer=self.producer_1,
            quantity=1, unit_price=Decimal("1.00"),
        )
        self.item_2 = OrderItem.objects.create(
            order=order, product=product_2, producer=self.producer_2,
            quantity=1, unit_price=Decimal("2.00"),
        )

    def test_producer_sees_only_own_order_items(self):
        self.client.login(username="orders_prod1@farm.com", password="TestPass123!")
        response = self.client.get(reverse("marketplace:producer_orders"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Farm 1 Apple")
        self.assertNotContains(response, "Farm 2 Leek")

    def test_customer_cannot_access_producer_orders_page(self):
        customer_user = User.objects.create_user(
            username="noprod@example.com", email="noprod@example.com", password="TestPass123!"
        )
        self.client.login(username="noprod@example.com", password="TestPass123!")
        response = self.client.get(reverse("marketplace:producer_orders"), follow=True)
        self.assertEqual(response.status_code, 200)
        # Should be redirected away, not shown orders
        self.assertNotContains(response, "Farm 1 Apple")

    def test_unauthenticated_redirected_from_producer_orders(self):
        response = self.client.get(reverse("marketplace:producer_orders"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response["Location"])


# ---------------------------------------------------------------------------
# TC-012: Weekly settlements (5% commission)
# ---------------------------------------------------------------------------


class WeeklySettlementTests(TestCase):
    def setUp(self):
        from django.utils import timezone
        from datetime import timedelta

        customer = User.objects.create_user(
            username="settle_cust@example.com", email="settle_cust@example.com", password="TestPass123!"
        )
        prod_user = User.objects.create_user(
            username="settle_prod@farm.com", email="settle_prod@farm.com", password="TestPass123!"
        )
        self.producer = ProducerProfile.objects.create(
            user=prod_user, producer_name="Settle Farm", contact_name="S",
            phone="0", address="X", postcode="X1",
        )
        category = Category.objects.create(name="Settle Cat", slug="settle-cat")
        product = Product.objects.create(
            name="Settle Apple", price=Decimal("10.00"), category=category,
            producer=self.producer, stock_quantity=100,
        )
        self.order = Order.objects.create(
            customer=customer,
            status=Order.DELIVERED,
            total_amount=Decimal("100.00"),
            delivered_at=timezone.now(),
        )
        OrderItem.objects.create(
            order=self.order, product=product, producer=self.producer,
            quantity=10, unit_price=Decimal("10.00"),
        )
        self.client.login(username="settle_prod@farm.com", password="TestPass123!")

    def test_settlement_page_loads_for_producer(self):
        response = self.client.get(reverse("marketplace:producer_weekly_settlement"))
        self.assertEqual(response.status_code, 200)

    def test_five_percent_commission_deducted(self):
        from .models import Settlement
        self.client.get(reverse("marketplace:producer_weekly_settlement"))
        settlement = Settlement.objects.filter(producer=self.producer).first()
        self.assertIsNotNone(settlement)
        expected_commission = (settlement.total_order_value * Decimal("0.05")).quantize(Decimal("0.01"))
        self.assertEqual(settlement.commission_total, expected_commission)

    def test_producer_payment_is_ninety_five_percent(self):
        from .models import Settlement
        self.client.get(reverse("marketplace:producer_weekly_settlement"))
        settlement = Settlement.objects.filter(producer=self.producer).first()
        self.assertIsNotNone(settlement)
        expected_payment = settlement.total_order_value - settlement.commission_total
        self.assertEqual(settlement.producer_payment_total, expected_payment)

    def test_customer_cannot_access_settlement_page(self):
        self.client.logout()
        customer_user = User.objects.create_user(
            username="settle_cust2@example.com", email="settle_cust2@example.com", password="TestPass123!"
        )
        self.client.login(username="settle_cust2@example.com", password="TestPass123!")
        response = self.client.get(reverse("marketplace:producer_weekly_settlement"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Settle Farm")
