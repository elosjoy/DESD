from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("marketplace", "0003_orderstatusupdate_and_order_status_choices"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="seasonal_availability",
            field=models.CharField(
                choices=[
                    ("IN_SEASON", "In Season"),
                    ("OUT_OF_SEASON", "Out of Season"),
                    ("YEAR_ROUND", "Year-Round"),
                ],
                default="YEAR_ROUND",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDING", "Pending"),
                    ("CONFIRMED", "Confirmed"),
                    ("READY", "Ready"),
                    ("DELIVERED", "Delivered"),
                ],
                default="PENDING",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="orderstatusupdate",
            name="order_item",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="status_updates",
                to="marketplace.orderitem",
            ),
        ),
    ]
