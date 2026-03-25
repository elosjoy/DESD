from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("marketplace", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Order",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "status",
                    models.CharField(
                        choices=[("PENDING", "Pending"), ("COMPLETED", "Completed"), ("DELIVERED", "Delivered")],
                        default="PENDING",
                        max_length=20,
                    ),
                ),
                ("total_amount", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("delivered_at", models.DateTimeField(blank=True, null=True)),
                (
                    "customer",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="orders",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="Settlement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("week_start", models.DateField()),
                ("week_end", models.DateField()),
                ("total_order_value", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("commission_total", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("producer_payment_total", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "producer",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="settlements", to="marketplace.producerprofile"),
                ),
            ],
            options={"ordering": ["-week_start", "-created_at"], "unique_together": {("producer", "week_start", "week_end")}},
        ),
        migrations.CreateModel(
            name="OrderItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.PositiveIntegerField(default=1)),
                ("unit_price", models.DecimalField(decimal_places=2, max_digits=10)),
                (
                    "order",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="marketplace.order"),
                ),
                (
                    "producer",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="order_items", to="marketplace.producerprofile"),
                ),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="marketplace.product")),
            ],
            options={"ordering": ["id"]},
        ),
    ]
