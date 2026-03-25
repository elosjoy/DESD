from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("marketplace", "0002_product_unit"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductUpdateHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(choices=[("CREATE", "Create"), ("UPDATE", "Update"), ("STOCK_UPDATE", "Stock Update")], max_length=20)),
                ("previous_stock_quantity", models.IntegerField(blank=True, null=True)),
                ("new_stock_quantity", models.IntegerField(blank=True, null=True)),
                ("previous_availability_status", models.CharField(blank=True, max_length=20)),
                ("new_availability_status", models.CharField(blank=True, max_length=20)),
                ("changed_at", models.DateTimeField(auto_now_add=True)),
                ("changed_by", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="update_history", to="marketplace.product")),
            ],
            options={
                "ordering": ["-changed_at"],
            },
        ),
    ]
