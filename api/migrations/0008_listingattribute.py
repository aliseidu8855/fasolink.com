from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0007_listing_extended_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="ListingAttribute",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80, db_index=True)),
                ("value", models.CharField(max_length=255)),
                ("listing", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attributes", to="api.listing")),
            ],
            options={
                "unique_together": {("listing", "name")},
            },
        ),
        migrations.AddIndex(
            model_name="listingattribute",
            index=models.Index(fields=["listing", "name"], name="api_listinga_listing_3f71fc_idx"),
        ),
    ]
