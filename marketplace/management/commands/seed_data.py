from decimal import Decimal
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from marketplace.models import Category, CustomerProfile, Order, OrderItem, ProducerProfile, Product


class Command(BaseCommand):
    help = "Seed the database with demo data for users, profiles, products, and orders"
    DEFAULT_SCALE = 3
    DEFAULT_ORDERS_PER_CUSTOMER = 4

    CUSTOMER_USERS = [
        {
            "username": "alice_customer",
            "email": "alice@example.com",
            "password": "Pass1234!",
            "first_name": "Alice",
            "last_name": "Green",
            "profile": {
                "full_name": "Alice Green",
                "phone": "07111 111111",
                "delivery_address": "12 Rose Lane, Leeds",
                "postcode": "LS1 4AB",
            },
        },
        {
            "username": "bob_customer",
            "email": "bob@example.com",
            "password": "Pass1234!",
            "first_name": "Bob",
            "last_name": "Taylor",
            "profile": {
                "full_name": "Bob Taylor",
                "phone": "07222 222222",
                "delivery_address": "44 Market Street, Manchester",
                "postcode": "M1 2CD",
            },
        },
    ]

    PRODUCER_USERS = [
        {
            "username": "fresh_farm_producer",
            "email": "freshfarm@example.com",
            "password": "Pass1234!",
            "first_name": "Sarah",
            "last_name": "Farmer",
            "profile": {
                "producer_name": "Fresh Farm Co",
                "contact_name": "Sarah Farmer",
                "phone": "07333 333333",
                "address": "1 Country Road, York",
                "postcode": "YO1 7EF",
            },
        },
        {
            "username": "sunny_dairy_producer",
            "email": "sunnydairy@example.com",
            "password": "Pass1234!",
            "first_name": "Tom",
            "last_name": "Milner",
            "profile": {
                "producer_name": "Sunny Dairy",
                "contact_name": "Tom Milner",
                "phone": "07444 444444",
                "address": "9 Meadow Lane, Bristol",
                "postcode": "BS1 5GH",
            },
        },
    ]

    CATEGORY_NAMES = [
        "Vegetables",
        "Dairy",
        "Fruit",
        "Bakery",
        "Pantry",
        "Meat",
        "Herbs",
        "Drinks",
        "Seafood",
    ]

    PRODUCT_DATA = [
        {
            "name": "Carrots",
            "price": Decimal("1.20"),
            "category": "Vegetables",
            "producer": "Fresh Farm Co",
            "stock_quantity": 60,
            "availability_status": Product.AVAILABLE,
            "description": "Fresh local carrots.",
        },
        {
            "name": "Broccoli",
            "price": Decimal("1.80"),
            "category": "Vegetables",
            "producer": "Fresh Farm Co",
            "stock_quantity": 30,
            "availability_status": Product.IN_SEASON,
            "description": "Green broccoli heads.",
        },
        {
            "name": "Potatoes",
            "price": Decimal("2.50"),
            "category": "Vegetables",
            "producer": "Fresh Farm Co",
            "stock_quantity": 80,
            "availability_status": Product.AVAILABLE,
            "description": "Washed white potatoes.",
        },
        {
            "name": "Whole Milk",
            "price": Decimal("1.10"),
            "category": "Dairy",
            "producer": "Sunny Dairy",
            "stock_quantity": 40,
            "availability_status": Product.AVAILABLE,
            "description": "Creamy whole milk.",
        },
        {
            "name": "Cheddar Cheese",
            "price": Decimal("3.90"),
            "category": "Dairy",
            "producer": "Sunny Dairy",
            "stock_quantity": 25,
            "availability_status": Product.IN_SEASON,
            "description": "Mature cheddar block.",
        },
        {
            "name": "Yoghurt",
            "price": Decimal("0.95"),
            "category": "Dairy",
            "producer": "Sunny Dairy",
            "stock_quantity": 50,
            "availability_status": Product.AVAILABLE,
            "description": "Natural live yoghurt.",
        },
        {
            "name": "Apples",
            "price": Decimal("2.20"),
            "category": "Fruit",
            "producer": "Fresh Farm Co",
            "stock_quantity": 70,
            "availability_status": Product.IN_SEASON,
            "description": "Crisp red apples.",
        },
        {
            "name": "Strawberries",
            "price": Decimal("2.80"),
            "category": "Fruit",
            "producer": "Fresh Farm Co",
            "stock_quantity": 35,
            "availability_status": Product.AVAILABLE,
            "description": "Sweet fresh strawberries.",
        },
        {
            "name": "Spinach",
            "price": Decimal("1.60"),
            "category": "Vegetables",
            "producer": "Fresh Farm Co",
            "stock_quantity": 45,
            "availability_status": Product.IN_SEASON,
            "description": "Tender baby spinach leaves.",
        },
        {
            "name": "Bananas",
            "price": Decimal("1.95"),
            "category": "Fruit",
            "producer": "Fresh Farm Co",
            "stock_quantity": 55,
            "availability_status": Product.AVAILABLE,
            "description": "Ripe bananas sold in bunches.",
        },
        {
            "name": "Blueberries",
            "price": Decimal("3.40"),
            "category": "Fruit",
            "producer": "Fresh Farm Co",
            "stock_quantity": 28,
            "availability_status": Product.IN_SEASON,
            "description": "Fresh blueberries packed in punnets.",
        },
        {
            "name": "Farmhouse Bread",
            "price": Decimal("2.70"),
            "category": "Bakery",
            "producer": "Fresh Farm Co",
            "stock_quantity": 22,
            "availability_status": Product.AVAILABLE,
            "description": "Crusty farmhouse loaf.",
        },
        {
            "name": "Free Range Eggs",
            "price": Decimal("2.95"),
            "category": "Dairy",
            "producer": "Sunny Dairy",
            "stock_quantity": 48,
            "availability_status": Product.AVAILABLE,
            "description": "Box of 6 free-range eggs.",
        },
        {
            "name": "Butter",
            "price": Decimal("2.30"),
            "category": "Dairy",
            "producer": "Sunny Dairy",
            "stock_quantity": 38,
            "availability_status": Product.AVAILABLE,
            "description": "Salted block butter.",
        },
        {
            "name": "Honey",
            "price": Decimal("4.50"),
            "category": "Pantry",
            "producer": "Fresh Farm Co",
            "stock_quantity": 20,
            "availability_status": Product.AVAILABLE,
            "description": "Local wildflower honey.",
        },
        {
            "name": "Chicken Breast",
            "price": Decimal("5.90"),
            "category": "Meat",
            "producer": "Fresh Farm Co",
            "stock_quantity": 24,
            "availability_status": Product.IN_SEASON,
            "description": "Skinless chicken breast fillets.",
        },
    ]

    ORDER_BLUEPRINTS = [
        {
            "customer": "alice_customer",
            "status": Order.PENDING,
            "items": [
                {"product": "Carrots", "quantity": 2},
                {"product": "Whole Milk", "quantity": 1},
                {"product": "Apples", "quantity": 3},
            ],
        },
        {
            "customer": "bob_customer",
            "status": Order.CONFIRMED,
            "items": [
                {"product": "Broccoli", "quantity": 1},
                {"product": "Cheddar Cheese", "quantity": 2},
                {"product": "Yoghurt", "quantity": 4},
            ],
        },
        {
            "customer": "alice_customer",
            "status": Order.READY,
            "items": [
                {"product": "Potatoes", "quantity": 2},
                {"product": "Strawberries", "quantity": 1},
            ],
        },
        {
            "customer": "bob_customer",
            "status": Order.PENDING,
            "items": [
                {"product": "Farmhouse Bread", "quantity": 1},
                {"product": "Butter", "quantity": 1},
                {"product": "Honey", "quantity": 1},
            ],
        },
        {
            "customer": "alice_customer",
            "status": Order.CONFIRMED,
            "items": [
                {"product": "Chicken Breast", "quantity": 2},
                {"product": "Spinach", "quantity": 1},
                {"product": "Free Range Eggs", "quantity": 1},
            ],
        },
        {
            "customer": "bob_customer",
            "status": Order.READY,
            "items": [
                {"product": "Bananas", "quantity": 2},
                {"product": "Blueberries", "quantity": 1},
                {"product": "Yoghurt", "quantity": 2},
            ],
        },
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            "--scale",
            type=int,
            default=self.DEFAULT_SCALE,
            help="Volume multiplier for bulk demo data (default: 3)",
        )
        parser.add_argument(
            "--orders-per-customer",
            type=int,
            default=self.DEFAULT_ORDERS_PER_CUSTOMER,
            help="Base number of bulk orders per customer before scaling (default: 4)",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        scale = max(1, options["scale"])
        orders_per_customer = max(1, options["orders_per_customer"])

        self.stdout.write(self.style.NOTICE("Seeding marketplace demo data..."))
        self.stdout.write(
            self.style.NOTICE(
                f"Bulk settings: scale={scale}, orders_per_customer={orders_per_customer}"
            )
        )

        users_by_username, base_customers, base_producers = self._create_users_and_profiles()
        bulk_customers, bulk_producers = self._create_bulk_users_and_profiles(scale, users_by_username)

        all_customers = base_customers + bulk_customers
        all_producers = base_producers + bulk_producers

        categories_by_name = self._create_categories()
        products_by_name = self._create_products(categories_by_name)
        all_products = self._create_bulk_products(categories_by_name, all_producers, scale, products_by_name)

        if Order is not None:
            self._create_orders(users_by_username, products_by_name)
            self._create_bulk_orders(all_customers, all_products, scale, orders_per_customer)
            self._create_tc012_settlement_data(users_by_username, products_by_name)

        self.stdout.write(self.style.SUCCESS("Seed data completed."))

    def _create_users_and_profiles(self):
        User = get_user_model()
        users_by_username = {}
        customer_users = []
        producer_profiles = []

        customer_created = 0
        for customer_data in self.CUSTOMER_USERS:
            user, was_created = User.objects.get_or_create(
                username=customer_data["username"],
                defaults={
                    "email": customer_data["email"],
                    "first_name": customer_data["first_name"],
                    "last_name": customer_data["last_name"],
                },
            )

            # Ensure repeat runs keep credentials and basic details consistent.
            user.email = customer_data["email"]
            user.first_name = customer_data["first_name"]
            user.last_name = customer_data["last_name"]
            user.set_password(customer_data["password"])
            user.save()

            CustomerProfile.objects.update_or_create(
                user=user,
                defaults=customer_data["profile"],
            )

            users_by_username[user.username] = user
            customer_users.append(user)
            if was_created:
                customer_created += 1

        producer_created = 0
        for producer_data in self.PRODUCER_USERS:
            user, was_created = User.objects.get_or_create(
                username=producer_data["username"],
                defaults={
                    "email": producer_data["email"],
                    "first_name": producer_data["first_name"],
                    "last_name": producer_data["last_name"],
                },
            )

            user.email = producer_data["email"]
            user.first_name = producer_data["first_name"]
            user.last_name = producer_data["last_name"]
            user.set_password(producer_data["password"])
            user.save()

            ProducerProfile.objects.update_or_create(
                user=user,
                defaults=producer_data["profile"],
            )
            producer_profile = ProducerProfile.objects.get(user=user)

            users_by_username[user.username] = user
            producer_profiles.append(producer_profile)
            if was_created:
                producer_created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Customers created: {customer_created}, producers created: {producer_created}"
            )
        )
        self.stdout.write(self.style.SUCCESS("Customer and producer profiles are ready."))
        return users_by_username, customer_users, producer_profiles

    def _create_bulk_users_and_profiles(self, scale, users_by_username):
        User = get_user_model()

        customer_target = scale * 10
        producer_target = scale * 5

        created_customers = 0
        created_producers = 0
        customer_users = []
        producer_profiles = []

        for index in range(1, customer_target + 1):
            username = f"demo_customer_{index:03d}"
            user, was_created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": f"{username}@example.com",
                    "first_name": f"DemoCustomer{index}",
                    "last_name": "User",
                },
            )
            user.email = f"{username}@example.com"
            user.first_name = f"DemoCustomer{index}"
            user.last_name = "User"
            user.set_password("DemoPass123!")
            user.save()

            CustomerProfile.objects.update_or_create(
                user=user,
                defaults={
                    "full_name": f"Demo Customer {index}",
                    "phone": f"07000{index:06d}",
                    "delivery_address": f"{index} Demo Street, Demo City",
                    "postcode": f"D{index % 10} {index % 9}{(index + 3) % 10}AA",
                },
            )

            users_by_username[user.username] = user
            customer_users.append(user)
            if was_created:
                created_customers += 1

        for index in range(1, producer_target + 1):
            username = f"demo_producer_{index:03d}"
            user, was_created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": f"{username}@example.com",
                    "first_name": f"Producer{index}",
                    "last_name": "Demo",
                },
            )
            user.email = f"{username}@example.com"
            user.first_name = f"Producer{index}"
            user.last_name = "Demo"
            user.set_password("DemoPass123!")
            user.save()

            producer_profile, _ = ProducerProfile.objects.update_or_create(
                user=user,
                defaults={
                    "producer_name": f"Demo Producer Farm {index:03d}",
                    "contact_name": f"Producer Contact {index}",
                    "phone": f"07500{index:06d}",
                    "address": f"Unit {index}, Producer Park",
                    "postcode": f"P{index % 10} {index % 8}{(index + 5) % 10}BB",
                },
            )

            users_by_username[user.username] = user
            producer_profiles.append(producer_profile)
            if was_created:
                created_producers += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Bulk customers created: {created_customers}, bulk producers created: {created_producers}"
            )
        )
        return customer_users, producer_profiles

    def _create_categories(self):
        categories_by_name = {}
        created_count = 0

        for category_name in self.CATEGORY_NAMES:
            category, was_created = Category.objects.get_or_create(
                slug=slugify(category_name),
                defaults={"name": category_name},
            )
            if category.name != category_name:
                category.name = category_name
                category.save(update_fields=["name"])

            categories_by_name[category_name] = category
            if was_created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(f"Categories created: {created_count}"))
        return categories_by_name

    def _create_products(self, categories_by_name):
        products_by_name = {}
        created_count = 0

        producers_by_name = {producer.producer_name: producer for producer in ProducerProfile.objects.all()}

        for data in self.PRODUCT_DATA:
            product, was_created = Product.objects.get_or_create(
                name=data["name"],
                producer=producers_by_name[data["producer"]],
                defaults={
                    "price": data["price"],
                    "category": categories_by_name[data["category"]],
                    "description": data["description"],
                    "stock_quantity": data["stock_quantity"],
                    "availability_status": data["availability_status"],
                    "seasonal_availability": Product.SEASON_YEAR_ROUND,
                },
            )

            # Keep product details aligned with seed data on repeat runs.
            product.price = data["price"]
            product.category = categories_by_name[data["category"]]
            product.description = data["description"]
            product.stock_quantity = data["stock_quantity"]
            product.availability_status = data["availability_status"]
            product.seasonal_availability = Product.SEASON_YEAR_ROUND
            product.save()

            products_by_name[product.name] = product
            if was_created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(f"Products created: {created_count}"))
        return products_by_name

    def _create_bulk_products(self, categories_by_name, producer_profiles, scale, products_by_name):
        created_count = 0
        status_cycle = [
            Product.AVAILABLE,
            Product.IN_SEASON,
            Product.UNAVAILABLE,
            Product.OUT_OF_SEASON,
        ]
        seasonal_cycle = [
            Product.SEASON_YEAR_ROUND,
            Product.SEASON_IN,
            Product.SEASON_OUT,
        ]

        if not producer_profiles:
            producer_profiles = list(ProducerProfile.objects.all())

        category_names = list(categories_by_name.keys())
        product_target = scale * 40

        for index in range(1, product_target + 1):
            category_name = category_names[index % len(category_names)]
            category = categories_by_name[category_name]
            producer = producer_profiles[index % len(producer_profiles)]

            availability_status = status_cycle[index % len(status_cycle)]
            seasonal_availability = seasonal_cycle[index % len(seasonal_cycle)]

            if (
                availability_status in [Product.UNAVAILABLE, Product.OUT_OF_SEASON]
                or seasonal_availability == Product.SEASON_OUT
            ):
                stock_quantity = 0
            else:
                stock_quantity = 12 + (index % 40)

            product_name = f"{category_name} Demo Item {index:03d}"
            price = Decimal(f"{2 + (index % 14)}.{(index * 7) % 100:02d}")

            product, was_created = Product.objects.get_or_create(
                name=product_name,
                producer=producer,
                defaults={
                    "price": price,
                    "category": category,
                    "description": f"Bulk demo {category_name.lower()} product {index}.",
                    "stock_quantity": stock_quantity,
                    "availability_status": availability_status,
                    "seasonal_availability": seasonal_availability,
                },
            )

            product.price = price
            product.category = category
            product.description = f"Bulk demo {category_name.lower()} product {index}."
            product.stock_quantity = stock_quantity
            product.availability_status = availability_status
            product.seasonal_availability = seasonal_availability
            product.save()

            products_by_name[product.name] = product
            if was_created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(f"Bulk products created: {created_count}"))
        return list(products_by_name.values())

    def _create_orders(self, users_by_username, products_by_name):
        created_orders = 0
        created_items = 0

        for blueprint in self.ORDER_BLUEPRINTS:
            customer = users_by_username[blueprint["customer"]]

            order_total = Decimal("0.00")
            for item_data in blueprint["items"]:
                product = products_by_name[item_data["product"]]
                order_total += product.price * item_data["quantity"]

            order, order_created = Order.objects.get_or_create(
                customer=customer,
                status=blueprint["status"],
                total_amount=order_total,
            )
            self._set_order_delivery_fields(order, blueprint["status"], days_ago=1)
            if order_created:
                created_orders += 1

            item_total = Decimal("0.00")
            for item_data in blueprint["items"]:
                product = products_by_name[item_data["product"]]
                order_item, item_created = OrderItem.objects.get_or_create(
                    order=order,
                    product=product,
                    producer=product.producer,
                    defaults={
                        "quantity": item_data["quantity"],
                        "unit_price": product.price,
                        "status": blueprint["status"],
                    },
                )

                if (
                    order_item.quantity != item_data["quantity"]
                    or order_item.unit_price != product.price
                    or order_item.status != blueprint["status"]
                ):
                    order_item.quantity = item_data["quantity"]
                    order_item.unit_price = product.price
                    order_item.status = blueprint["status"]
                    order_item.save(update_fields=["quantity", "unit_price", "status"])

                item_total += order_item.unit_price * order_item.quantity
                if item_created:
                    created_items += 1

            if order.total_amount != item_total:
                order.total_amount = item_total
                order.save(update_fields=["total_amount"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Orders created: {created_orders}, order items created: {created_items}"
            )
        )

    def _create_bulk_orders(self, customers, all_products, scale, orders_per_customer):
        created_orders = 0
        created_items = 0

        if not all_products:
            self.stdout.write(self.style.WARNING("No products available to create bulk orders."))
            return

        orderable_products = [
            product
            for product in all_products
            if product.stock_quantity > 0
            and product.availability_status in [Product.AVAILABLE, Product.IN_SEASON]
            and product.seasonal_availability != Product.SEASON_OUT
        ]
        if not orderable_products:
            orderable_products = all_products

        status_cycle = [Order.PENDING, Order.CONFIRMED, Order.READY, Order.DELIVERED]

        for customer_index, customer in enumerate(customers):
            total_customer_orders = orders_per_customer * scale

            for order_index in range(total_customer_orders):
                status = status_cycle[(customer_index + order_index) % len(status_cycle)]
                first = (customer_index * 11 + order_index * 3) % len(orderable_products)
                second = (first + 1) % len(orderable_products)
                third = (first + 2) % len(orderable_products)
                selected_products = [
                    orderable_products[first],
                    orderable_products[second],
                    orderable_products[third],
                ]

                q1 = 1 + (order_index % 3)
                q2 = 1 + ((order_index + 1) % 3)
                q3 = 1 + ((order_index + 2) % 3)
                quantities = [q1, q2, q3]

                order_total = Decimal("0.00")
                for product, quantity in zip(selected_products, quantities):
                    order_total += product.price * quantity

                order, order_created = Order.objects.get_or_create(
                    customer=customer,
                    status=status,
                    total_amount=order_total,
                )
                self._set_order_delivery_fields(order, status, days_ago=order_index % 12)
                if order_created:
                    created_orders += 1

                item_total = Decimal("0.00")
                for product, quantity in zip(selected_products, quantities):
                    order_item, item_created = OrderItem.objects.get_or_create(
                        order=order,
                        product=product,
                        producer=product.producer,
                        defaults={
                            "quantity": quantity,
                            "unit_price": product.price,
                            "status": status,
                        },
                    )

                    if (
                        order_item.quantity != quantity
                        or order_item.unit_price != product.price
                        or order_item.status != status
                    ):
                        order_item.quantity = quantity
                        order_item.unit_price = product.price
                        order_item.status = status
                        order_item.save(update_fields=["quantity", "unit_price", "status"])

                    item_total += order_item.unit_price * order_item.quantity
                    if item_created:
                        created_items += 1

                if order.total_amount != item_total:
                    order.total_amount = item_total
                    order.save(update_fields=["total_amount"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Bulk orders created: {created_orders}, bulk order items created: {created_items}"
            )
        )

    def _set_order_delivery_fields(self, order, status, days_ago=0):
        if status in [Order.DELIVERED, Order.COMPLETED]:
            delivered_at = timezone.now() - timedelta(days=max(0, days_ago))
            if order.delivered_at is None or order.delivered_at.date() != delivered_at.date() or order.status != status:
                order.status = status
                order.delivered_at = delivered_at
                order.save(update_fields=["status", "delivered_at"])
        elif order.delivered_at is not None:
            order.delivered_at = None
            if order.status != status:
                order.status = status
                order.save(update_fields=["status", "delivered_at"])
            else:
                order.save(update_fields=["delivered_at"])

    def _create_tc012_settlement_data(self, users_by_username, products_by_name):
        created_orders = 0
        created_items = 0

        tc_orders = [
            {
                "customer": "alice_customer",
                "status": Order.DELIVERED,
                "days_ago": 1,
                "items": [
                    {"product": "Carrots", "quantity": 5},
                    {"product": "Apples", "quantity": 3},
                    {"product": "Farmhouse Bread", "quantity": 2},
                ],
            },
            {
                "customer": "bob_customer",
                "status": Order.DELIVERED,
                "days_ago": 2,
                "items": [
                    {"product": "Whole Milk", "quantity": 4},
                    {"product": "Cheddar Cheese", "quantity": 2},
                    {"product": "Free Range Eggs", "quantity": 2},
                ],
            },
            {
                "customer": "alice_customer",
                "status": Order.DELIVERED,
                "days_ago": 9,
                "items": [
                    {"product": "Yoghurt", "quantity": 3},
                    {"product": "Butter", "quantity": 2},
                ],
            },
        ]

        for tc_order in tc_orders:
            customer = users_by_username[tc_order["customer"]]

            order_total = Decimal("0.00")
            for item_data in tc_order["items"]:
                product = products_by_name[item_data["product"]]
                order_total += product.price * item_data["quantity"]

            order, order_created = Order.objects.get_or_create(
                customer=customer,
                status=tc_order["status"],
                total_amount=order_total,
            )
            self._set_order_delivery_fields(order, tc_order["status"], days_ago=tc_order["days_ago"])
            if order_created:
                created_orders += 1

            item_total = Decimal("0.00")
            for item_data in tc_order["items"]:
                product = products_by_name[item_data["product"]]
                order_item, item_created = OrderItem.objects.get_or_create(
                    order=order,
                    product=product,
                    producer=product.producer,
                    defaults={
                        "quantity": item_data["quantity"],
                        "unit_price": product.price,
                        "status": tc_order["status"],
                    },
                )

                if (
                    order_item.quantity != item_data["quantity"]
                    or order_item.unit_price != product.price
                    or order_item.status != tc_order["status"]
                ):
                    order_item.quantity = item_data["quantity"]
                    order_item.unit_price = product.price
                    order_item.status = tc_order["status"]
                    order_item.save(update_fields=["quantity", "unit_price", "status"])

                item_total += order_item.unit_price * order_item.quantity
                if item_created:
                    created_items += 1

            if order.total_amount != item_total:
                order.total_amount = item_total
                order.save(update_fields=["total_amount"])

        self.stdout.write(
            self.style.SUCCESS(
                f"TC-012 delivered orders created: {created_orders}, TC-012 items created: {created_items}"
            )
        )
