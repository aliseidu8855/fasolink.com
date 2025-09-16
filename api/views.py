from django.contrib.auth.models import User
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework import status
from .models import Category, Listing, Conversation, Message, MessageRead, Review, ListingAttribute
from .query_utils import with_seller_rating
from .serializers import (
    UserSerializer,
    CategorySerializer,
    ListingSerializer,
    ConversationSerializer,
    MessageSerializer,
    ConversationDetailSerializer,
)
from .permissions import IsOwnerOrReadOnly
from django.shortcuts import get_object_or_404
from rest_framework import filters as drf_filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.exceptions import PermissionDenied
from .filters import ListingFilter
from rest_framework.views import APIView
from django.db import transaction
from rest_framework.pagination import PageNumberPagination
from django.db.models import Value as V
from django.db.models.functions import Lower


# View for User Registration
class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (permissions.AllowAny,)
    serializer_class = UserSerializer


class MeView(APIView):
    """Return basic authenticated user info."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response({
            "id": request.user.id,
            "username": request.user.username,
            "email": request.user.email,
            "messages_count": Message.objects.filter(participants=request.user).count() if hasattr(Message, 'participants') else 0,
        })

    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            data = serializer.data
            data.pop('password', None)
            return Response(data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class StatsView(APIView):
    """Simple aggregate stats for homepage hero."""
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        from django.contrib.auth.models import User as DjangoUser
        data = {
            "listings": Listing.objects.count(),
            "categories": Category.objects.count(),
            "users": DjangoUser.objects.count(),
        }
        return Response(data)


class DashboardStatsView(APIView):
    """Authenticated user dashboard stats: listing counts, views, messages.
    For now views are placeholder (0) until tracking implemented.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        listings_qs = Listing.objects.filter(user=user)
        total = listings_qs.count()
        active = listings_qs.filter(is_featured__in=[True, False]).count()  # placeholder definition of active
        # Messages: count of all messages where user participates in conversation or sent
        convo_ids = Conversation.objects.filter(participants=user).values_list('id', flat=True)
        messages = Message.objects.filter(conversation_id__in=convo_ids).exclude(sender=user).count()
        data = {
            "listings_total": total,
            "listings_active": active,
            "views": 0,  # TODO implement view tracking table
            "messages": messages,
        }
        return Response(data)


# View to list all categories
class CategoryListView(generics.ListAPIView):
    queryset = Category.objects.all()
    permission_classes = (permissions.AllowAny,)
    serializer_class = CategorySerializer


# View for creating and listing listings
class ListingListCreateView(generics.ListCreateAPIView):
    queryset = Listing.objects.all().order_by("-created_at")
    serializer_class = ListingSerializer
    permission_classes = [
        permissions.IsAuthenticatedOrReadOnly
    ]  # Only logged-in users can create
    pagination_class = PageNumberPagination

    # Configure filtering and searching
    filter_backends = [
        DjangoFilterBackend,
        drf_filters.SearchFilter,
        drf_filters.OrderingFilter,
    ]
    filterset_class = ListingFilter  # Use our custom filterset

    # Fallback search fields for the SearchFilter backend
    search_fields = ["title", "description", "location"]

    # Fields that the user can order the results by
    ordering_fields = ["created_at", "price", "rating"]

    def get_serializer_context(self):
        return {"request": self.request}

    def get_queryset(self):
        qs = super().get_queryset()
        return with_seller_rating(qs)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# View for retrieving, updating, and deleting a single listing
class ListingDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Listing.objects.all()
    serializer_class = ListingSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    def get_serializer_context(self):
        return {"request": self.request}


# View to list all of a user's conversations
class ConversationListView(generics.ListAPIView):
    serializer_class = ConversationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Annotate last message content and timestamp for efficient list rendering
        from django.db.models import OuterRef, Subquery, DateTimeField, TextField

        last_message_subquery = Message.objects.filter(
            conversation=OuterRef("pk")
        ).order_by("-timestamp")
        qs = (
            self.request.user.conversations.all()
            .annotate(
                last_message_timestamp=Subquery(
                    last_message_subquery.values("timestamp")[:1],
                    output_field=DateTimeField(),
                ),
                last_message=Subquery(
                    last_message_subquery.values("content")[:1],
                    output_field=TextField(),
                ),
            )
            .order_by("-last_message_timestamp", "-created_at")
        )
        return qs


# View to retrieve a single conversation and its messages, or create a new one
class ConversationDetailView(generics.RetrieveAPIView):
    serializer_class = ConversationDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Conversation.objects.all()


# View to create a message within a conversation
class MessageCreateView(generics.CreateAPIView):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        conversation = get_object_or_404(
            Conversation, pk=self.kwargs["conversation_id"]
        )
        # Simple check to ensure the user is part of the conversation
        if self.request.user not in conversation.participants.all():
            raise PermissionDenied("You are not a participant in this conversation.")
        serializer.save(sender=self.request.user, conversation=conversation)


# View to initiate a conversation (or retrieve an existing one)
class StartConversationView(generics.CreateAPIView):
    serializer_class = (
        ConversationDetailSerializer  # return full detail including messages
    )
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        listing_id = request.data.get("listing_id")
        if not listing_id:
            return Response(
                {"error": "listing_id is required."}, status=status.HTTP_400_BAD_REQUEST
            )
        listing = get_object_or_404(Listing, pk=listing_id)

        if listing.user == request.user:
            return Response(
                {"error": "You cannot start a conversation on your own listing."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check existing conversation between the two participants for this listing
        conversation = (
            Conversation.objects.filter(listing=listing, participants=request.user)
            .filter(participants=listing.user)
            .first()
        )

        created = False
        if not conversation:
            conversation = Conversation.objects.create(listing=listing)
            conversation.participants.add(request.user, listing.user)
            created = True

        serializer = self.get_serializer(conversation)
        payload = dict(serializer.data)
        payload["created"] = created
        return Response(
            payload, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )


class UserListingsView(generics.ListAPIView):
    """
    This view returns a list of all the listings
    for the currently authenticated user.
    """

    serializer_class = ListingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return with_seller_rating(
            Listing.objects.filter(user=self.request.user)
        ).order_by("-created_at")

    def get_serializer_context(self):
        return {"request": self.request}


class ConversationMessagesPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class ConversationMessagesView(generics.ListCreateAPIView):
    """List (paginated) and create messages for a conversation.
    GET: paginated messages (oldest first) for infinite scroll.
    POST: create a new message in the conversation.
    """

    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = ConversationMessagesPagination

    def get_queryset(self):
        conversation = get_object_or_404(
            Conversation, pk=self.kwargs["conversation_id"]
        )
        if self.request.user not in conversation.participants.all():
            raise PermissionDenied("You are not a participant in this conversation.")
        return conversation.messages.select_related("sender").order_by("timestamp")

    def perform_create(self, serializer):
        conversation = get_object_or_404(
            Conversation, pk=self.kwargs["conversation_id"]
        )
        if self.request.user not in conversation.participants.all():
            raise PermissionDenied("You are not a participant in this conversation.")
        serializer.save(sender=self.request.user, conversation=conversation)

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx


class MarkConversationReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, conversation_id):
        conversation = get_object_or_404(Conversation, pk=conversation_id)
        if request.user not in conversation.participants.all():
            raise PermissionDenied("You are not a participant in this conversation.")
        unread_messages = conversation.messages.exclude(sender=request.user).exclude(
            reads__user=request.user
        )
        created = 0
        with transaction.atomic():
            to_create = [
                MessageRead(message=m, user=request.user) for m in unread_messages
            ]
            if to_create:
                MessageRead.objects.bulk_create(to_create, ignore_conflicts=True)
                created = len(to_create)
        return Response({"updated": created}, status=status.HTTP_200_OK)


class SpecsMetadataView(APIView):
    """Return allowed specification fields for a given high-level category.
    For now static definitions; can be moved to database later.
    /api/specs-metadata/?category=Phones
    """
    permission_classes = [permissions.AllowAny]

    CATEGORY_SPECS = {
        "Phones": [
            {"name": "Brand", "key": "brand", "required": True, "type": "text"},
            {"name": "Model", "key": "model", "required": True, "type": "text"},
            {"name": "Condition", "key": "condition", "required": True, "type": "select", "options": ["New", "Used"]},
            {"name": "Second Condition", "key": "second_condition", "required": False, "type": "text"},
            {"name": "Screen Size (inches)", "key": "screen_size", "required": False, "type": "number"},
            {"name": "Ram", "key": "ram", "required": False, "type": "text"},
            {"name": "Internal Storage", "key": "internal_storage", "required": True, "type": "text"},
            {"name": "Color", "key": "color", "required": True, "type": "text"},
            {"name": "Operating System", "key": "os", "required": False, "type": "text"},
            {"name": "Display Type", "key": "display_type", "required": False, "type": "text"},
            {"name": "Resolution", "key": "resolution", "required": False, "type": "text"},
            {"name": "SIM", "key": "sim", "required": False, "type": "text"},
            {"name": "Card Slot", "key": "card_slot", "required": False, "type": "text"},
            {"name": "Main Camera", "key": "main_camera", "required": False, "type": "text"},
            {"name": "Selfie Camera", "key": "selfie_camera", "required": False, "type": "text"},
            {"name": "Battery (mAh)", "key": "battery", "required": False, "type": "number"},
            {"name": "Features", "key": "features", "required": False, "type": "text"},
            {"name": "Exchange Possible", "key": "exchange_possible", "required": False, "type": "boolean"},
        ],
        "Cars": [
            {"name": "Make", "key": "make", "required": True, "type": "text"},
            {"name": "Model", "key": "model", "required": True, "type": "text"},
            {"name": "Year", "key": "year", "required": True, "type": "number"},
            {"name": "Transmission", "key": "transmission", "required": False, "type": "select", "options": ["Automatic", "Manual"]},
            {"name": "Fuel Type", "key": "fuel_type", "required": False, "type": "select", "options": ["Petrol", "Diesel", "Electric", "Hybrid"]},
            {"name": "Mileage", "key": "mileage", "required": False, "type": "number"},
            {"name": "Color", "key": "color", "required": False, "type": "text"},
            {"name": "Condition", "key": "condition", "required": True, "type": "select", "options": ["New", "Used"]},
        ],
        "Real Estate": [
            {"name": "Property Type", "key": "property_type", "required": True, "type": "select", "options": ["Apartment", "House", "Land"]},
            {"name": "Bedrooms", "key": "bedrooms", "required": False, "type": "number"},
            {"name": "Bathrooms", "key": "bathrooms", "required": False, "type": "number"},
            {"name": "Size (sqm)", "key": "size", "required": False, "type": "number"},
            {"name": "Furnished", "key": "furnished", "required": False, "type": "boolean"},
        ],
        "Electronics": [
            {"name": "Brand", "key": "brand", "required": False, "type": "text"},
            {"name": "Model", "key": "model", "required": False, "type": "text"},
            {"name": "Condition", "key": "condition", "required": True, "type": "select", "options": ["New", "Used"]},
        ],
    }

    def get(self, request):
        category = request.query_params.get("category")
        if not category:
            return Response({"error": "category query param required"}, status=400)
        specs = self.CATEGORY_SPECS.get(category)
        if specs is None:
            return Response({"error": "unknown category"}, status=404)
        return Response({"category": category, "specs": specs})


class LocationsSuggestView(APIView):
    """Return list of distinct locations for autocomplete (basic)."""
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        q = request.query_params.get('q', '').strip().lower()
        return_all = request.query_params.get('all') == '1'
        qs = Listing.objects.exclude(location__isnull=True).exclude(location="")
        if q:
            qs = qs.filter(location__icontains=q)
        values = qs.values_list('location', flat=True)
        unique = []
        seen = set()
        cap = 500 if return_all else 80
        for loc in values[:cap]:
            norm = (loc or '').strip()
            if norm and norm not in seen:
                seen.add(norm)
                unique.append(norm)
        # When returning all, provide sorted list
        if return_all:
            unique.sort(key=lambda s: s.lower())
        limit = 500 if return_all else 40
        return Response({"results": unique[:limit], "all": return_all})
