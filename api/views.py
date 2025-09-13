from django.contrib.auth.models import User
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework import status
from .models import Category, Listing, Conversation
from .serializers import UserSerializer, CategorySerializer, ListingSerializer, ConversationSerializer, MessageSerializer, ConversationDetailSerializer
from .permissions import IsOwnerOrReadOnly
from django.shortcuts import get_object_or_404
from rest_framework import filters as drf_filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.exceptions import PermissionDenied
from .filters import ListingFilter



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
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

# View for retrieving, updating, and deleting a single listing
class ListingDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Listing.objects.all()
    serializer_class = ListingSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]
    # We will add custom permissions here later to ensure only owners can edit/delete


# View to list all of a user's conversations
class ConversationListView(generics.ListAPIView):
    serializer_class = ConversationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Return conversations where the current user is a participant
        return self.request.user.conversations.all().order_by('-created_at')

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
    serializer_class = ConversationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        listing_id = request.data.get('listing_id')
        listing = get_object_or_404(Listing, pk=listing_id)
        
        if listing.user == request.user:
            return Response({'error': 'You cannot start a conversation on your own listing.'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if a conversation already exists between these users for this listing
        conversation = Conversation.objects.filter(listing=listing, participants=request.user).filter(participants=listing.user).first()

        if conversation:
            # Conversation already exists, return it
            serializer = self.get_serializer(conversation)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            # Create a new conversation
            conversation = Conversation.objects.create(listing=listing)
            conversation.participants.add(request.user, listing.user)
            serializer = self.get_serializer(conversation)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        

