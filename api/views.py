from django.contrib.auth.models import User
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework import status
from .models import (
    Category,
    Listing,
    Conversation,
    Message,
    MessageRead,
    MessageAttachment,
)
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
from .ws_events import broadcast_conversation_message, broadcast_conversation_read, notify_user
from rest_framework.views import APIView
from django.db import transaction
from rest_framework.pagination import PageNumberPagination
from django.db.models import Count, IntegerField, Sum, Case, When, Max, Q
from django.utils.http import http_date, parse_http_date_safe


# View for User Registration
class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (permissions.AllowAny,)
    serializer_class = UserSerializer


class MeView(APIView):
    """Return basic authenticated user info."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(
            {
                "id": request.user.id,
                "username": request.user.username,
                "email": request.user.email,
                "messages_count": (
                    Message.objects.filter(participants=request.user).count()
                    if hasattr(Message, "participants")
                    else 0
                ),
            }
        )

    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            data = serializer.data
            data.pop("password", None)
            return Response(data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class StatsView(APIView):
    """Simple aggregate stats for homepage hero."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        data = {
            "listings": Listing.objects.count(),
            "categories": Category.objects.count(),
            "users": User.objects.count(),
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
        active = listings_qs.filter(
            is_featured__in=[True, False]
        ).count()  # placeholder definition of active
        # Messages: count of all messages where user participates in conversation or sent
        convo_ids = Conversation.objects.filter(participants=user).values_list(
            "id", flat=True
        )
        messages = (
            Message.objects.filter(conversation_id__in=convo_ids)
            .exclude(sender=user)
            .count()
        )
        data = {
            "listings_total": total,
            "listings_active": active,
            "views": 0,  # TODO implement view tracking table
            "messages": messages,
        }
        return Response(data)


# View to list all categories
class CategoryListView(generics.ListAPIView):
    def get_queryset(self):
        return Category.objects.annotate(listings_count=Count('listings'))
    permission_classes = (permissions.AllowAny,)
    serializer_class = CategorySerializer

    def list(self, request, *args, **kwargs):
        # Compute weak ETag for conditional GET before doing the heavy work
        etag = None
        try:
            from hashlib import md5
            key = f"cats:{Category.objects.count()}"
            etag = 'W/"' + md5(key.encode()).hexdigest() + '"'
            inm = request.META.get("HTTP_IF_NONE_MATCH")
            if inm and inm == etag and request.method == 'GET':
                resp = Response(status=304)
                resp["ETag"] = etag
                resp["Cache-Control"] = "public, max-age=600"
                return resp
        except Exception:
            etag = None
        response = super().list(request, *args, **kwargs)
        response["Cache-Control"] = "public, max-age=600"
        if etag:
            response["ETag"] = etag
        return response


# View for creating and listing listings
class ListingListCreateView(generics.ListCreateAPIView):
    queryset = Listing.objects.filter(is_active=True, archived=False).order_by("-created_at")
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

    def list(self, request, *args, **kwargs):
        # Compute ETag/Last-Modified from filtered queryset state prior to serialization
        filtered_qs = self.filter_queryset(self.get_queryset())
        latest = filtered_qs.aggregate(ts=Max("updated_at"))
        last_ts = latest.get("ts")
        etag = None
        try:
            from hashlib import md5
            qp = request.query_params.dict()
            page = qp.get("page", "1")
            ordering = qp.get("ordering", "")
            count_hint = filtered_qs.count()
            key = f"list:{page}:{ordering}:{count_hint}:{last_ts.timestamp() if last_ts else ''}"
            etag = 'W/"' + md5(key.encode()).hexdigest() + '"'
            inm = request.META.get("HTTP_IF_NONE_MATCH")
            if inm and inm == etag and request.method == 'GET':
                resp = Response(status=304)
                resp["ETag"] = etag
                resp["Cache-Control"] = "public, max-age=30"
                if last_ts:
                    resp["Last-Modified"] = http_date(last_ts.timestamp())
                return resp
            # If-Modified-Since (fallback when no ETag match/header)
            ims = request.META.get("HTTP_IF_MODIFIED_SINCE")
            if ims and last_ts and request.method == 'GET':
                since = parse_http_date_safe(ims)
                if since is not None and int(last_ts.timestamp()) <= since:
                    resp = Response(status=304)
                    resp["Cache-Control"] = "public, max-age=30"
                    resp["ETag"] = etag
                    resp["Last-Modified"] = http_date(last_ts.timestamp())
                    return resp
        except Exception:
            etag = None
        response = super().list(request, *args, **kwargs)
        response["Cache-Control"] = "public, max-age=30"
        if etag:
            response["ETag"] = etag
        if last_ts:
            response["Last-Modified"] = http_date(last_ts.timestamp())
        return response


# View for retrieving, updating, and deleting a single listing
class ListingDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Listing.objects.all()
    serializer_class = ListingSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]

    def get_serializer_context(self):
        return {"request": self.request}

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        # Hide inactive/archived to non-owners
        if (not instance.is_active or instance.archived) and (not request.user.is_authenticated or request.user.id != instance.user_id):
            return Response(status=404)
        # Precompute ETag/Last-Modified
        etag = None
        last_ts = getattr(instance, "updated_at", None)
        try:
            from hashlib import md5
            etag_key = f"listing:{instance.pk}:{last_ts.timestamp() if last_ts else ''}"
            etag = 'W/"' + md5(etag_key.encode()).hexdigest() + '"'
            inm = request.META.get("HTTP_IF_NONE_MATCH")
            if inm and inm == etag and request.method == 'GET':
                resp = Response(status=304)
                resp["ETag"] = etag
                resp["Cache-Control"] = "public, max-age=120"
                if last_ts:
                    resp["Last-Modified"] = http_date(last_ts.timestamp())
                return resp
            ims = request.META.get("HTTP_IF_MODIFIED_SINCE")
            if ims and last_ts and request.method == 'GET':
                since = parse_http_date_safe(ims)
                if since is not None and int(last_ts.timestamp()) <= since:
                    resp = Response(status=304)
                    resp["Cache-Control"] = "public, max-age=120"
                    resp["ETag"] = etag
                    resp["Last-Modified"] = http_date(last_ts.timestamp())
                    return resp
        except Exception:
            etag = None
        response = super().retrieve(request, *args, **kwargs)
        response["Cache-Control"] = "public, max-age=120"
        if etag:
            response["ETag"] = etag
        if last_ts:
            response["Last-Modified"] = http_date(last_ts.timestamp())
        return response


class ListingQuickToggleView(APIView):
    """Owner-only lightweight toggle of status fields (active/archived/featured)."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        listing = get_object_or_404(Listing, pk=pk)
        if listing.user_id != request.user.id:
            raise PermissionDenied("Not owner")
        action = request.data.get("action")
        if action == "toggle_active":
            listing.is_active = not bool(listing.is_active)
        elif action == "toggle_featured":
            listing.is_featured = not bool(listing.is_featured)
        elif action == "archive":
            listing.archived = True
            listing.is_active = False
        elif action == "unarchive":
            listing.archived = False
            listing.is_active = True
        else:
            return Response({"error": "unknown action"}, status=status.HTTP_400_BAD_REQUEST)
        listing.save(update_fields=["is_active", "is_featured", "archived", "updated_at"])
        serializer = ListingSerializer(listing, context={"request": request})
        return Response(serializer.data)


class ListingsFacetsView(APIView):
    """Compute facets for Listings given current filters.
    Returns counts for categories, negotiable yes/no, featured yes/no, and price ranges.
    For each facet, we intentionally ignore that facet's own filter to provide full choices.
    """

    permission_classes = [permissions.AllowAny]

    PRICE_BUCKETS = [
        (0, 50000),
        (50000, 100000),
        (100000, 200000),
        (200000, 500000),
        (500000, None),  # 500k+
    ]

    def _apply_filters(self, request, exclude: set[str] | None = None):
        exclude = exclude or set()
        # Copy query params but drop excluded keys
        params = request.query_params.copy()
        for key in list(params.keys()):
            if key in exclude:
                params.pop(key)
        # Apply ListingFilter on the queryset
        base_qs = Listing.objects.filter(is_active=True, archived=False)
        filtered = ListingFilter(params, queryset=base_qs).qs
        return filtered

    def get(self, request):
        # Total with all filters applied
        total_qs = self._apply_filters(request)
        total = total_qs.count()

        # Categories facet (ignore current category filter)
        categories_qs = self._apply_filters(request, exclude={"category"})
        per_cat = (
            categories_qs.values("category").annotate(count=Count("id")).order_by()
        )
        # Map category id -> name
        cat_ids = [c["category"] for c in per_cat if c["category"] is not None]
        cat_map = {c.id: c.name for c in Category.objects.filter(id__in=cat_ids)}
        categories = [
            {"id": c["category"], "name": cat_map.get(c["category"], ""), "count": c["count"]}
            for c in per_cat
            if c["category"] is not None
        ]

        # Negotiable facet (ignore negotiable filter)
        negotiable_qs = self._apply_filters(request, exclude={"negotiable"})
        neg_counts_raw = negotiable_qs.values("negotiable").annotate(count=Count("id"))
        negotiable = {"true": 0, "false": 0}
        for row in neg_counts_raw:
            key = "true" if row["negotiable"] else "false"
            negotiable[key] = row["count"]

        # Featured facet (ignore is_featured filter)
        featured_qs = self._apply_filters(request, exclude={"is_featured"})
        feat_counts_raw = featured_qs.values("is_featured").annotate(count=Count("id"))
        featured = {"true": 0, "false": 0}
        for row in feat_counts_raw:
            key = "true" if row["is_featured"] else "false"
            featured[key] = row["count"]

        # Price ranges (ignore price filters so we show full distribution under other filters)
        price_qs = self._apply_filters(request, exclude={"min_price", "max_price"})
        # Aggregate counts per bucket in one query
        aggregations = {}
        for idx, (lo, hi) in enumerate(self.PRICE_BUCKETS):
            if hi is None:
                cond = When(price__gte=lo, then=1)
                label = f"{lo}+"
            else:
                cond = When(price__gte=lo, price__lt=hi, then=1)
                label = f"{lo}-{hi}"
            aggregations[f"b{idx}"] = Sum(Case(cond, default=0, output_field=IntegerField()))
        agg = price_qs.aggregate(**aggregations)
        price_ranges = []
        for idx, (lo, hi) in enumerate(self.PRICE_BUCKETS):
            label = (f"{int(lo)}+" if hi is None else f"{int(lo)}-{int(hi)}")
            price_ranges.append({
                "min": float(lo),
                "max": (float(hi) if hi is not None else None),
                "label": label,
                "count": int(agg.get(f"b{idx}") or 0),
            })

        return Response(
            {
                "total": total,
                "categories": categories,
                "negotiable": negotiable,
                "featured": featured,
                "price_ranges": price_ranges,
            }
        )


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
        qs = Listing.objects.filter(user=self.request.user)
        # Allow filtering via query params for dashboard chips
        is_active = self.request.query_params.get("is_active")
        archived = self.request.query_params.get("archived")
        if is_active is not None:
            qs = qs.filter(is_active=is_active in ["1","true","True"])
        if archived is not None:
            qs = qs.filter(archived=archived in ["1","true","True"])
        return with_seller_rating(qs).order_by("-updated_at", "-created_at")

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
        msg = serializer.save(sender=self.request.user, conversation=conversation)
        # Handle uploaded files (multipart)
        files = self.request.FILES.getlist('uploaded_files') or []
        if files:
            for f in files:
                MessageAttachment.objects.create(message=msg, file=f)
        # Broadcast new message to websocket listeners
        # Build attachments payload with absolute URLs
        atts = []
        try:
            for att in msg.attachments.all():
                url = att.file.url
                try:
                    url = self.request.build_absolute_uri(url)
                except Exception:
                    pass
                atts.append({"id": att.id, "url": url, "name": getattr(att.file, 'name', None)})
        except Exception:
            atts = []
        payload = {
            "id": msg.id,
            "content": msg.content,
            "sender_id": msg.sender_id,
            "sender": msg.sender.username,
            "timestamp": msg.timestamp.isoformat(),
            "attachments": atts,
        }
        try:
            broadcast_conversation_message(conversation.id, payload)
            # Notify the other participant on their user channel for list refresh/unread badge
            for u in conversation.participants.exclude(id=self.request.user.id):
                notify_user(u.id, {"event": "conversation.updated", "conversation_id": conversation.id})
        except Exception:
            # Non-blocking: do not fail REST on ws broadcast issues
            pass

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
        # Broadcast read receipts
        try:
            broadcast_conversation_read(conversation.id, request.user.id, created)
        except Exception:
            pass
        return Response({"updated": created}, status=status.HTTP_200_OK)


class SpecsMetadataView(APIView):
    """Return allowed specification fields for a given high-level category.
    Static for now; can move to DB later.
    /api/specs-metadata/?category=Electronics
    """

    permission_classes = [permissions.AllowAny]

    # Canonical category keys
    FASHION = "Fashion"
    PROPERTIES = "Properties"
    MOBILE_TABLET = "Mobile & Tablet"
    ELECTRONICS = "Electronics"

    # Finalized specs for the four categories
    CATEGORY_SPECS = {
        FASHION: [
            {"name": "Type", "key": "type", "required": True, "type": "select", "options": ["Clothing", "Shoes", "Bags & Accessories"]},
            {"name": "Brand", "key": "brand", "required": False, "type": "text"},
            {"name": "Gender", "key": "gender", "required": False, "type": "select", "options": ["Men", "Women", "Unisex", "Kids"]},
            {"name": "Size", "key": "size", "required": True, "type": "text"},
            {"name": "Color", "key": "color", "required": False, "type": "text"},
            {"name": "Material", "key": "material", "required": False, "type": "text"},
            {"name": "Condition", "key": "condition", "required": True, "type": "select", "options": ["New", "Used"]},
            {"name": "Authentic", "key": "authentic", "required": False, "type": "boolean"},
        ],
        PROPERTIES: [
            {"name": "Property Type", "key": "property_type", "required": True, "type": "select", "options": ["Apartment", "House", "Land", "Commercial"]},
            {"name": "Bedrooms", "key": "bedrooms", "required": False, "type": "number"},
            {"name": "Bathrooms", "key": "bathrooms", "required": False, "type": "number"},
            {"name": "Size (sqm)", "key": "size_sqm", "required": False, "type": "number"},
            {"name": "Furnished", "key": "furnished", "required": False, "type": "boolean"},
            {"name": "Year Built", "key": "year_built", "required": False, "type": "number"},
            {"name": "Condition", "key": "condition", "required": False, "type": "select", "options": ["New", "Used"]},
        ],
        MOBILE_TABLET: [
            {"name": "Device Type", "key": "device_type", "required": True, "type": "select", "options": ["Phone", "Tablet"]},
            {"name": "Brand", "key": "brand", "required": True, "type": "text"},
            {"name": "Model", "key": "model", "required": True, "type": "text"},
            {"name": "Condition", "key": "condition", "required": True, "type": "select", "options": ["New", "Used"]},
            {"name": "Storage", "key": "internal_storage", "required": True, "type": "select", "options": ["16GB", "32GB", "64GB", "128GB", "256GB", "512GB", "1TB"]},
            {"name": "RAM", "key": "ram", "required": False, "type": "select", "options": ["2GB", "3GB", "4GB", "6GB", "8GB", "12GB", "16GB"]},
            {"name": "Color", "key": "color", "required": True, "type": "text"},
            {"name": "Screen Size (in)", "key": "screen_size", "required": False, "type": "number"},
            {"name": "Battery (mAh)", "key": "battery", "required": False, "type": "number"},
            {"name": "OS", "key": "os", "required": False, "type": "select", "options": ["Android", "iOS", "HarmonyOS", "Other"]},
            {"name": "SIM", "key": "sim", "required": False, "type": "select", "options": ["Single SIM", "Dual SIM", "eSIM"]},
            {"name": "Network", "key": "network", "required": False, "type": "select", "options": ["2G", "3G", "4G", "5G"]},
            {"name": "Exchange Possible", "key": "exchange_possible", "required": False, "type": "boolean"},
        ],
        ELECTRONICS: [
            {"name": "Type", "key": "type", "required": True, "type": "select", "options": ["TV", "Laptop", "Camera", "Gaming", "Audio", "Appliance", "Other"]},
            {"name": "Brand", "key": "brand", "required": False, "type": "text"},
            {"name": "Model", "key": "model", "required": False, "type": "text"},
            {"name": "Condition", "key": "condition", "required": True, "type": "select", "options": ["New", "Used"]},
            {"name": "Power (W)", "key": "power_w", "required": False, "type": "number"},
        ],
    }

    # Accept legacy/synonym names from existing categories
    SYNONYMS = {
        "phones": MOBILE_TABLET,
        "phone": MOBILE_TABLET,
        "mobile": MOBILE_TABLET,
        "mobile & tablet": MOBILE_TABLET,
        "mobile and tablet": MOBILE_TABLET,
        "mobile phones & tablets": MOBILE_TABLET,
        "mobile phones and tablets": MOBILE_TABLET,
        "mobile phone & tablet": MOBILE_TABLET,
        "mobile phone and tablet": MOBILE_TABLET,
        "mobile phone or tablet": MOBILE_TABLET,
        "real estate": PROPERTIES,
        "properties": PROPERTIES,
        "property": PROPERTIES,
        "fashion": FASHION,
        "electronics": ELECTRONICS,
        "electonics": ELECTRONICS,  # common misspelling
    }

    def get(self, request):
        raw = request.query_params.get("category")
        if not raw:
            return Response({"error": "category query param required"}, status=400)
        key = (raw or "").strip()
        # Normalize case/spacing
        norm = key.lower().strip()
        canonical = self.SYNONYMS.get(norm, None)
        if canonical is None and key in self.CATEGORY_SPECS:
            canonical = key
        if canonical is None:
            return Response({"error": "unknown category"}, status=404)
        specs = self.CATEGORY_SPECS.get(canonical)
        return Response({"category": canonical, "specs": specs})


class LocationsSuggestView(APIView):
    """Return list of distinct locations for autocomplete (basic)."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        q = request.query_params.get("q", "").strip().lower()
        return_all = request.query_params.get("all") == "1"
        qs = Listing.objects.exclude(location__isnull=True).exclude(location="")
        if q:
            qs = qs.filter(location__icontains=q)
        values = qs.values_list("location", flat=True)
        unique = []
        seen = set()
        cap = 500 if return_all else 80
        for loc in values[:cap]:
            norm = (loc or "").strip()
            if norm and norm not in seen:
                seen.add(norm)
                unique.append(norm)
        # When returning all, provide sorted list
        if return_all:
            unique.sort(key=lambda s: s.lower())
        limit = 500 if return_all else 40
        return Response({"results": unique[:limit], "all": return_all})


class RUMIngestView(APIView):
    """Lightweight RUM/error ingest. Accepts arbitrary JSON events and logs them.
    Intentionally unauthenticated but throttle-protected via DRF throttling if configured.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        data = request.data
        # Minimal safety: drop excessively large payloads
        try:
            from json import dumps
            s = dumps(data)
            if len(s) > 10000:
                return Response(status=413)
            # Log to stdout; in real deployment route to logging/observability backend
            print("[RUM]", s[:2000])
        except Exception:
            pass
        return Response(status=204)
