from django.contrib.auth.models import User
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework import status
from .models import Category, Listing, Conversation, Message, MessageRead
from .serializers import UserSerializer, CategorySerializer, ListingSerializer, ConversationSerializer, MessageSerializer, ConversationDetailSerializer
from .permissions import IsOwnerOrReadOnly
from django.shortcuts import get_object_or_404
from rest_framework import filters as drf_filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.exceptions import PermissionDenied
from .filters import ListingFilter
from rest_framework.views import APIView
from django.db import transaction
from rest_framework.pagination import PageNumberPagination



# View for User Registration
class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (permissions.AllowAny,)
    serializer_class = UserSerializer

# View to list all categories
class CategoryListView(generics.ListAPIView):
    queryset = Category.objects.all()
    permission_classes = (permissions.AllowAny,)
    serializer_class = CategorySerializer

# View for creating and listing listings
class ListingListCreateView(generics.ListCreateAPIView):
    queryset = Listing.objects.all().order_by('-created_at')
    serializer_class = ListingSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly] # Only logged-in users can create

    # Configure filtering and searching
    filter_backends = [DjangoFilterBackend, drf_filters.SearchFilter, drf_filters.OrderingFilter]
    filterset_class = ListingFilter # Use our custom filterset
    
    # Fallback search fields for the SearchFilter backend
    search_fields = ['title', 'description', 'location']
    
    # Fields that the user can order the results by
    ordering_fields = ['created_at', 'price']

    def get_serializer_context(self):
        return {'request': self.request}
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

# View for retrieving, updating, and deleting a single listing
class ListingDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Listing.objects.all()
    serializer_class = ListingSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]
    
    def get_serializer_context(self):
        return {'request': self.request}

# View to list all of a user's conversations
class ConversationListView(generics.ListAPIView):
    serializer_class = ConversationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Annotate last message content and timestamp for efficient list rendering
        from django.db.models import OuterRef, Subquery, DateTimeField, TextField
        last_message_subquery = Message.objects.filter(conversation=OuterRef('pk')).order_by('-timestamp')
        qs = (
            self.request.user.conversations
            .all()
            .annotate(
                last_message_timestamp=Subquery(last_message_subquery.values('timestamp')[:1], output_field=DateTimeField()),
                last_message=Subquery(last_message_subquery.values('content')[:1], output_field=TextField()),
            )
            .order_by('-last_message_timestamp', '-created_at')
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
        conversation = get_object_or_404(Conversation, pk=self.kwargs['conversation_id'])
        # Simple check to ensure the user is part of the conversation
        if self.request.user not in conversation.participants.all():
            raise PermissionDenied("You are not a participant in this conversation.")
        serializer.save(sender=self.request.user, conversation=conversation)

# View to initiate a conversation (or retrieve an existing one)
class StartConversationView(generics.CreateAPIView):
    serializer_class = ConversationDetailSerializer  # return full detail including messages
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        listing_id = request.data.get('listing_id')
        if not listing_id:
            return Response({'error': 'listing_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        listing = get_object_or_404(Listing, pk=listing_id)

        if listing.user == request.user:
            return Response({'error': 'You cannot start a conversation on your own listing.'}, status=status.HTTP_400_BAD_REQUEST)

        # Check existing conversation between the two participants for this listing
        conversation = (
            Conversation.objects
            .filter(listing=listing, participants=request.user)
            .filter(participants=listing.user)
            .first()
        )

        created = False
        if not conversation:
            conversation = Conversation.objects.create(listing=listing)
            conversation.participants.add(request.user, listing.user)
            created = True

    serializer = self.get_serializer(conversation)
    # Include a flag so the frontend can distinguish creation vs existing without relying on status code alone
    payload = serializer.data | { 'created': created }
    return Response(payload, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

class UserListingsView(generics.ListAPIView):
    """
    This view returns a list of all the listings
    for the currently authenticated user.
    """
    serializer_class = ListingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Listing.objects.filter(user=self.request.user).order_by('-created_at')

    def get_serializer_context(self):
        return {'request': self.request}


class ConversationMessagesPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
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
        conversation = get_object_or_404(Conversation, pk=self.kwargs['conversation_id'])
        if self.request.user not in conversation.participants.all():
            raise PermissionDenied("You are not a participant in this conversation.")
        return conversation.messages.select_related('sender').order_by('timestamp')

    def perform_create(self, serializer):
        conversation = get_object_or_404(Conversation, pk=self.kwargs['conversation_id'])
        if self.request.user not in conversation.participants.all():
            raise PermissionDenied("You are not a participant in this conversation.")
        serializer.save(sender=self.request.user, conversation=conversation)

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx


class MarkConversationReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, conversation_id):
        conversation = get_object_or_404(Conversation, pk=conversation_id)
        if request.user not in conversation.participants.all():
            raise PermissionDenied("You are not a participant in this conversation.")
        unread_messages = conversation.messages.exclude(sender=request.user).exclude(reads__user=request.user)
        created = 0
        with transaction.atomic():
            to_create = [MessageRead(message=m, user=request.user) for m in unread_messages]
            if to_create:
                MessageRead.objects.bulk_create(to_create, ignore_conflicts=True)
                created = len(to_create)
        return Response({'updated': created}, status=status.HTTP_200_OK)
