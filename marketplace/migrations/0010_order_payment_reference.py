from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("marketplace", "0009_order_delivery_date"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="payment_reference",
            field=models.CharField(blank=True, max_length=100),
        ),
    ]
