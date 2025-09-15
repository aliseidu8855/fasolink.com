from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0006_review"),
    ]

    operations = [
        migrations.AddField(
            model_name="listing",
            name="brand",
            field=models.CharField(blank=True, null=True, max_length=120),
        ),
        migrations.AddField(
            model_name="listing",
            name="condition",
            field=models.CharField(blank=True, null=True, max_length=60),
        ),
        migrations.AddField(
            model_name="listing",
            name="color",
            field=models.CharField(blank=True, null=True, max_length=80),
        ),
        migrations.AddField(
            model_name="listing",
            name="material",
            field=models.CharField(blank=True, null=True, max_length=120),
        ),
        migrations.AddField(
            model_name="listing",
            name="room",
            field=models.CharField(blank=True, null=True, max_length=120),
        ),
        migrations.AddField(
            model_name="listing",
            name="address_line",
            field=models.CharField(blank=True, null=True, max_length=255),
        ),
        migrations.AddField(
            model_name="listing",
            name="address_city",
            field=models.CharField(blank=True, null=True, max_length=120),
        ),
        migrations.AddField(
            model_name="listing",
            name="address_region",
            field=models.CharField(blank=True, null=True, max_length=120),
        ),
        migrations.AddField(
            model_name="listing",
            name="address_postal_code",
            field=models.CharField(blank=True, null=True, max_length=40),
        ),
        migrations.AddField(
            model_name="listing",
            name="opening_hours",
            field=models.CharField(blank=True, null=True, max_length=180),
        ),
        migrations.AddField(
            model_name="listing",
            name="is_open_now",
            field=models.BooleanField(default=False),
        ),
    ]
