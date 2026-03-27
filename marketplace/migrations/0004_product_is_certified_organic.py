from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("marketplace", "0003_productupdatehistory"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="is_certified_organic",
            field=models.BooleanField(default=False),
        ),
    ]
