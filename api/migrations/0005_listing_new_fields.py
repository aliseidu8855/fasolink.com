from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ("api", "0004_messageread"),
    ]

    operations = [
        migrations.AddField(
            model_name='listing',
            name='is_featured',
            field=models.BooleanField(default=False, db_index=True),
        ),
        migrations.AddField(
            model_name='listing',
            name='negotiable',
            field=models.BooleanField(default=False, db_index=True),
        ),
        migrations.AddField(
            model_name='listing',
            name='rating',
            field=models.DecimalField(null=True, blank=True, max_digits=3, decimal_places=2),
        ),
    ]
