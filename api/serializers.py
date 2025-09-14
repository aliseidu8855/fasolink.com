from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Category, Listing, ListingImage, Conversation, Message, MessageRead
from django.utils.translation import gettext_lazy as _

# Serializer for User Registration
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'password']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            password=validated_data['password']
        )
        return user

# Serializer for Categories
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'icon_name']

# Serializers for Listings (will be expanded later)
class ListingImageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = ListingImage
        fields = ['id', 'image']

    def get_image(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return None

class ListingSerializer(serializers.ModelSerializer):
    images = ListingImageSerializer(many=True, read_only=True)
    user = serializers.ReadOnlyField(source='user.username')
    uploaded_images = serializers.ListField(
        child=serializers.ImageField(use_url=False),
        write_only=True,
        required=False
    )

    class Meta:
        model = Listing
        fields = [
            'id', 'title', 'description', 'price', 'category', 
            'location', 'user', 'created_at', 'updated_at', 'is_featured', 'negotiable', 'rating',
            'images', 'uploaded_images'
        ]
        read_only_fields = ['user', 'created_at', 'updated_at']

    def create(self, validated_data):
        uploaded_images = validated_data.pop('uploaded_images', [])
        listing = Listing.objects.create(**validated_data)
        for image in uploaded_images:
            ListingImage.objects.create(listing=listing, image=image)
        return listing



class MessageSerializer(serializers.ModelSerializer):
    sender = serializers.ReadOnlyField(source='sender.username')
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ['id', 'sender', 'content', 'timestamp', 'is_read']

    def get_is_read(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        if obj.sender_id == request.user.id:
            return True  # Always consider own messages as read
        return MessageRead.objects.filter(message=obj, user=request.user).exists()

class ConversationSerializer(serializers.ModelSerializer):
    """Lightweight conversation serializer used for conversation list.
    Now includes last message preview & timestamp (annotated in queryset)."""
    participants = serializers.StringRelatedField(many=True)
    listing_title = serializers.CharField(source='listing.title', read_only=True)
    last_message = serializers.CharField(read_only=True, allow_null=True)
    last_message_timestamp = serializers.DateTimeField(read_only=True, allow_null=True)
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            'id', 'listing', 'listing_title', 'participants', 'created_at',
            'last_message', 'last_message_timestamp', 'unread_count'
        ]

    def get_unread_count(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return 0
        # Count messages not sent by user and not read
        qs = obj.messages.exclude(sender=request.user)
        unread = qs.exclude(reads__user=request.user).count()
        return unread

class ConversationDetailSerializer(serializers.ModelSerializer):
    participants = serializers.StringRelatedField(many=True)
    messages = MessageSerializer(many=True, read_only=True)
    listing = ListingSerializer(read_only=True)
    last_message = serializers.SerializerMethodField()
    last_message_timestamp = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            'id', 'listing', 'participants', 'messages', 'created_at',
            'last_message', 'last_message_timestamp', 'unread_count'
        ]

    def get_last_message(self, obj):
        msg = obj.messages.last()
        return msg.content if msg else None

    def get_last_message_timestamp(self, obj):
        msg = obj.messages.last()
        return msg.timestamp if msg else None

    def get_unread_count(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return 0
        qs = obj.messages.exclude(sender=request.user)
        return qs.exclude(reads__user=request.user).count()
