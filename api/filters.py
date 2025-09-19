from django_filters import rest_framework as filters
from .models import Listing


class ListingFilter(filters.FilterSet):
    # Add a filter for a minimum price (e.g., ?min_price=10000)
    min_price = filters.NumberFilter(field_name="price", lookup_expr="gte")
    # Add a filter for a maximum price (e.g., ?max_price=50000)
    max_price = filters.NumberFilter(field_name="price", lookup_expr="lte")
    # Add a text search filter against the title and description
    search = filters.CharFilter(method="filter_by_search_text")
    negotiable = filters.BooleanFilter(field_name="negotiable")
    is_featured = filters.BooleanFilter(field_name="is_featured")
    is_active = filters.BooleanFilter(field_name="is_active")
    archived = filters.BooleanFilter(field_name="archived")
    min_rating = filters.NumberFilter(field_name="rating", lookup_expr="gte")
    # Match exact town (case-insensitive) in the location field, when provided as ?town=Town%20Name
    town = filters.CharFilter(method="filter_by_town")

    class Meta:
        model = Listing
        fields = [
            "category",
            "location",
            "negotiable",
            "is_featured",
            "is_active",
            "archived",
            "town",
        ]  # Allow exact filtering on these fields

    def filter_by_search_text(self, queryset, name, value):
        # This custom method allows searching across multiple fields
        from django.db.models import Q

        return queryset.filter(
            Q(title__icontains=value) | Q(description__icontains=value)
        )

    def filter_by_town(self, queryset, name, value):
        if not value:
            return queryset
        # Match the Listing.location exactly (case-insensitive) to the provided town name
        return queryset.filter(location__iexact=value)
