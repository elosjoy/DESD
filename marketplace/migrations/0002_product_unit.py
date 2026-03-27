from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("marketplace", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="unit",
            field=models.CharField(blank=True, max_length=50),
        ),
    ]
