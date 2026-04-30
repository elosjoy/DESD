from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("marketplace", "0005_merge_product_and_order_branches"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="delivery_date",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
