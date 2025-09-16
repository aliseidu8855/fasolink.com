from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Category, Listing, ListingImage, Conversation, Message, MessageRead, ListingAttribute
from django.utils.translation import gettext_lazy as _

# Serializer for User Registration
class UserSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'password', 'email']
        extra_kwargs = {
            'password': {'write_only': True},
            'email': {'required': False}
        }

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User.objects.create_user(password=password, **validated_data)
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance

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
    # Use a method field for seller_rating so we can gracefully handle None / float / Decimal
    seller_rating = serializers.SerializerMethodField()
    seller_rating_count = serializers.IntegerField(read_only=True, required=False)

    attributes = serializers.ListField(child=serializers.DictField(), write_only=True, required=False, help_text="List of {name, value} specs")
    attributes_out = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Listing
        fields = [
            'id', 'title', 'description', 'price', 'category', 
            'location', 'user', 'created_at', 'updated_at', 'is_featured', 'negotiable', 'rating', 'seller_rating',
            'seller_rating_count', 'brand', 'condition', 'color', 'material', 'room', 'address_line', 'address_city',
            'address_region', 'address_postal_code', 'opening_hours', 'is_open_now', 'images', 'uploaded_images', 'attributes', 'attributes_out'
        ]
        read_only_fields = ['user', 'created_at', 'updated_at']

    def get_seller_rating(self, obj):
        # Annotation provided in queryset as seller_rating
        val = getattr(obj, 'seller_rating', None)
        if val is None:
            return None
        try:
            from decimal import Decimal, ROUND_HALF_UP
            # Coerce to Decimal with 2 places
            d = Decimal(str(val)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            # Ensure it fits within 0-5 logical bounds (defensive)
            if d < 0:
                return Decimal('0.00')
            if d > 5:
                return Decimal('5.00')
            return d
        except Exception:
            return None

    def get_attributes_out(self, obj):
        # Return dict list of dynamic attributes
        return [
            {"name": a.name, "value": a.value}
            for a in getattr(obj, 'attributes').all()
        ]

    def create(self, validated_data):
        uploaded_images = validated_data.pop('uploaded_images', [])
        attributes = validated_data.pop('attributes', [])
        # If attributes came as a JSON string (multipart form workaround), try to parse
        if isinstance(attributes, str):
            import json
            try:
                parsed = json.loads(attributes)
                if isinstance(parsed, list):
                    attributes = parsed
            except Exception:
                attributes = []  # ignore malformed input silently for now
        listing = Listing.objects.create(**validated_data)
        # Bulk create attributes
        attr_objs = []
        for attr in attributes:
            name = attr.get('name'); value = attr.get('value')
            if name and value:
                attr_objs.append(ListingAttribute(listing=listing, name=name[:80], value=value[:255]))
        if attr_objs:
            ListingAttribute.objects.bulk_create(attr_objs, ignore_conflicts=True)
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
