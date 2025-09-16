from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('api', '0008_listingattribute'),
    ]

    operations = [
        migrations.AddField(
            model_name='listing',
            name='contact_phone',
            field=models.CharField(blank=True, help_text='Primary contact phone for this listing', max_length=40, null=True),
        ),
    ]
