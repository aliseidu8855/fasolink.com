from django.db import migrations


def upsert_jiji_categories(apps, _schema_editor):
    Category = apps.get_model('api', 'Category')
    # Jiji-style top categories with stable icon_name slugs
    categories = [
        {"name": "Vehicles", "icon_name": "cars"},
        {"name": "Property", "icon_name": "real-estate"},
        {"name": "Mobile Phones & Tablets", "icon_name": "mobile"},
        {"name": "Electronics", "icon_name": "electronics"},
        {"name": "Home, Furniture & Appliances", "icon_name": "home"},
        {"name": "Beauty & Personal Care", "icon_name": "beauty"},
        {"name": "Fashion", "icon_name": "fashion"},
        {"name": "Jobs", "icon_name": "jobs"},
        {"name": "Services", "icon_name": "services"},
        {"name": "Sports & Outdoors", "icon_name": "sports"},
        {"name": "Babies & Kids", "icon_name": "babies"},
        {"name": "Animals & Pets", "icon_name": "animals"},
    ]

    for item in categories:
        icon = item["icon_name"]
        name = item["name"]
        # Prefer matching by icon_name (acts as a slug)
        obj = Category.objects.filter(icon_name=icon).first()
        if obj:
            if obj.name != name:
                obj.name = name
                obj.save(update_fields=["name"])
            continue
        # Fallback: try matching by name
        obj = Category.objects.filter(name=name).first()
        if obj:
            if obj.icon_name != icon:
                obj.icon_name = icon
                obj.save(update_fields=["icon_name"])
            continue
        # Create new if not found
        Category.objects.create(name=name, icon_name=icon)


def noop(_apps, _schema_editor):
    # Non-destructive migration; no-op on reverse
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0009_listing_contact_phone'),
    ]

    operations = [
        migrations.RunPython(upsert_jiji_categories, noop),
    ]
