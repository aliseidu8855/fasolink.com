# api/migrations/0002_seed_categories.py

from django.db import migrations

def seed_categories(apps, schema_editor):
    Category = apps.get_model('api', 'Category')
    categories = [
        {'name': 'Electronics', 'icon_name': 'electronics'},
        {'name': 'Cars', 'icon_name': 'cars'},
        {'name': 'Fashion', 'icon_name': 'fashion'},
        {'name': 'Real Estate', 'icon_name': 'real-estate'},
        {'name': 'Jobs', 'icon_name': 'jobs'},
        {'name': 'Services', 'icon_name': 'services'},
    ]
    for category_data in categories:
        Category.objects.create(**category_data)

class Migration(migrations.Migration):

    dependencies = [
        ('api', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_categories),
    ]