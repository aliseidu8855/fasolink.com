from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from django.contrib.auth.models import User
from .models import Listing, Category
from .serializers import ListingSerializer
from .query_utils import with_seller_rating


class ListingSerializerResilienceTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username="seller", password="pass1234")
		self.category = Category.objects.create(name="Phones")
		self.listing = Listing.objects.create(
			title="iPhone 13",
			description="Good condition",
			price=500,
			category=self.category,
			location="Paris",
			user=self.user,
		)

	def test_serializer_without_annotation(self):
		# Plain queryset object (no seller_rating attributes)
		ser = ListingSerializer(instance=self.listing)
		data = ser.data
		# seller_rating should be present (None) not raising error
		self.assertIn("seller_rating", data)
		self.assertIsNone(data["seller_rating"])

	def test_serializer_with_annotation(self):
		qs = with_seller_rating(Listing.objects.filter(id=self.listing.id))
		obj = qs.first()
		ser = ListingSerializer(instance=obj)
		data = ser.data
		self.assertIn("seller_rating", data)
		# No reviews yet -> None
		self.assertIsNone(data["seller_rating"])


class ListingsEndpointTests(TestCase):
	def setUp(self):
		self.client = APIClient()
		user = User.objects.create_user(username="seller", password="pass1234")
		cat = Category.objects.create(name="Laptops")
		for i in range(3):
			Listing.objects.create(
				title=f"Laptop {i}",
				description="Specs...",
				price=1000 + i,
				category=cat,
				location="Berlin",
				user=user,
			)

	def test_listings_endpoint_ok(self):
		url = reverse('listing-list') if 'listing-list' in [r.name for r in self.client.handler._request_middleware] else '/api/listings/'
		# Fallback to hard-coded path (router not used in provided code)
		response = self.client.get('/api/listings/?page=1')
		self.assertEqual(response.status_code, 200, msg=response.content)
		self.assertIn('results', response.data)
		self.assertGreaterEqual(len(response.data['results']), 1)
		first = response.data['results'][0]
		self.assertIn('seller_rating', first)
		self.assertIn('seller_rating_count', first)
