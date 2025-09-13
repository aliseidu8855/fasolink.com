from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Category, Listing, ListingImage, Conversation, Message
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
    class Meta:
        model = ListingImage
        fields = ['id', 'image']

class ListingSerializer(serializers.ModelSerializer):
    images = ListingImageSerializer(many=True, read_only=True)
    user = serializers.ReadOnlyField(source='user.username')
    uploaded_images = serializers.ListField(
        child=serializers.ImageField(max_length=1000000, allow_empty_file=False, use_url=False),
        write_only=True,
        required=False # Make it optional
    )
    title = serializers.CharField(
        max_length=255,
        error_messages={'blank': _('Title cannot be blank.')}
    )
    description = serializers.CharField(
        error_messages={'blank': _('Description cannot be blank.')}
    )
    price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        error_messages={'invalid': _('Please enter a valid price.')}
    )

    class Meta:
        model = Listing
        fields = ['id', 'title', 'description', 'price', 'category', 'location', 'user', 'created_at', 'images', 'uploaded_images']
    
    def create(self, validated_data):
        uploaded_images = validated_data.pop('uploaded_images', [])
        listing = Listing.objects.create(**validated_data)
        for image in uploaded_images:
            ListingImage.objects.create(listing=listing, image=image)
        return listing



class MessageSerializer(serializers.ModelSerializer):
    sender = serializers.ReadOnlyField(source='sender.username')

    class Meta:
        model = Message
        fields = ['id', 'sender', 'content', 'timestamp']

class ConversationSerializer(serializers.ModelSerializer):
    # Use a simple string representation for participants for the list view
    participants = serializers.StringRelatedField(many=True)
    listing_title = serializers.CharField(source='listing.title', read_only=True)

    class Meta:
        model = Conversation
        fields = ['id', 'listing', 'listing_title', 'participants', 'created_at']

class ConversationDetailSerializer(serializers.ModelSerializer):
    participants = serializers.StringRelatedField(many=True)
    messages = MessageSerializer(many=True, read_only=True)
    listing = ListingSerializer(read_only=True)

    class Meta:
        model = Conversation
        fields = ['id', 'listing', 'participants', 'messages', 'created_at']
