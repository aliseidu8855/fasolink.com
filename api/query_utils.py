from django.db.models import Avg, Count, Q


def with_seller_rating(queryset):
  """Apply seller rating and rating count annotations to a queryset of Listings.

  Returns the queryset annotated with:
    - seller_rating: average rating from received_reviews
    - seller_rating_count: count of received reviews with a non-null rating
  """
  return queryset.annotate(
    seller_rating=Avg('user__received_reviews__rating'),
    seller_rating_count=Count(
      'user__received_reviews',
      filter=Q(user__received_reviews__rating__isnull=False)
    )
  )
