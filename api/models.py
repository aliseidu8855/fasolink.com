from django.db import models
from django.contrib.auth.models import User


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    icon_name = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return self.name


class Listing(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    price = models.DecimalField(max_digits=12, decimal_places=2)
    category = models.ForeignKey(
        Category, related_name="listings", on_delete=models.PROTECT
    )
    location = models.CharField(max_length=150)
    user = models.ForeignKey(User, related_name="listings", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # New commerce-style metadata fields
    is_featured = models.BooleanField(default=False, db_index=True)
    negotiable = models.BooleanField(default=False, db_index=True)
    # Average rating (e.g., 4.5). Kept simple for now; a future Review model could derive this.
    rating = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    # Extended structured attributes (nullable & optional to avoid breaking existing data)
    brand = models.CharField(max_length=120, blank=True, null=True)
    condition = models.CharField(max_length=60, blank=True, null=True)  # e.g., Brand New, Used
    color = models.CharField(max_length=80, blank=True, null=True)
    material = models.CharField(max_length=120, blank=True, null=True)
    room = models.CharField(max_length=120, blank=True, null=True)
    # Store / pickup address details
    address_line = models.CharField(max_length=255, blank=True, null=True)
    address_city = models.CharField(max_length=120, blank=True, null=True)
    address_region = models.CharField(max_length=120, blank=True, null=True)
    address_postal_code = models.CharField(max_length=40, blank=True, null=True)
    # Opening hours (simple textual representation for now, e.g. "Mon - Sat, 07:00-18:00")
    opening_hours = models.CharField(max_length=180, blank=True, null=True)
    # Whether currently open (seller can toggle manually until we implement structured hours logic)
    is_open_now = models.BooleanField(default=False)
    # Contact phone (simple string; could be normalized later)
    contact_phone = models.CharField(max_length=40, blank=True, null=True, help_text="Primary contact phone for this listing")

    def __str__(self):
        return self.title


class ListingImage(models.Model):
    listing = models.ForeignKey(
        Listing, related_name="images", on_delete=models.CASCADE
    )
    image = models.ImageField(upload_to="listing_images/")

    def __str__(self):
        return f"Image for {self.listing.title}"


class Conversation(models.Model):
    listing = models.ForeignKey(
        Listing, related_name="conversations", on_delete=models.CASCADE
    )
    participants = models.ManyToManyField(User, related_name="conversations")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Ensures a unique conversation per listing between the same two users
        # Note: This simple constraint assumes a 2-participant conversation.
        # For group chats, a different approach would be needed.
        pass  # A more complex constraint might be needed depending on exact requirements

    def __str__(self):
        return f"Conversation about '{self.listing.title}'"


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation, related_name="messages", on_delete=models.CASCADE
    )
    sender = models.ForeignKey(
        User, related_name="sent_messages", on_delete=models.CASCADE
    )
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["timestamp"]

    def __str__(self):
        return f"Message from {self.sender.username} at {self.timestamp}"


class MessageRead(models.Model):
    """Tracks which user has read which message (basic read receipt)."""

    message = models.ForeignKey(Message, related_name="reads", on_delete=models.CASCADE)
    user = models.ForeignKey(
        User, related_name="message_reads", on_delete=models.CASCADE
    )
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("message", "user")
        indexes = [
            models.Index(fields=["user", "message"]),
        ]

    def __str__(self):
        return f"Read: {self.user.username} -> {self.message.id}"


class Review(models.Model):
    """Seller review: user (reviewer) -> seller (User), rating 1-5, optional comment."""
    reviewer = models.ForeignKey(User, related_name="given_reviews", on_delete=models.CASCADE)
    seller = models.ForeignKey(User, related_name="received_reviews", on_delete=models.CASCADE)
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["seller", "rating"]),
        ]
        unique_together = ("reviewer", "seller", "created_at")  # simplistic; could refine to one per transaction

    def __str__(self):
        return f"Review {self.rating}* {self.reviewer_id}->{self.seller_id}"

    def clean(self):
        from django.core.exceptions import ValidationError
        if not 1 <= self.rating <= 5:
            raise ValidationError({"rating": "Rating must be between 1 and 5"})


class ListingAttribute(models.Model):
    """Flexible key/value specification attached to a Listing.
    Enables different categories to store different structured fields (e.g. RAM, Color, Mileage).
    """
    listing = models.ForeignKey(Listing, related_name="attributes", on_delete=models.CASCADE)
    name = models.CharField(max_length=80, db_index=True)
    value = models.CharField(max_length=255)

    class Meta:
        indexes = [
            models.Index(fields=["listing", "name"]),
        ]
        unique_together = ("listing", "name")  # one value per attribute key per listing

    def __str__(self):
        return f"{self.listing_id}:{self.name}={self.value[:30]}"
