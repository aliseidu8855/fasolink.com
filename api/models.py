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
    category = models.ForeignKey(Category, related_name='listings', on_delete=models.PROTECT)
    location = models.CharField(max_length=150)
    user = models.ForeignKey(User, related_name='listings', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

class ListingImage(models.Model):
    listing = models.ForeignKey(Listing, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='listing_images/')

    def __str__(self):
        return f"Image for {self.listing.title}"




class Conversation(models.Model):
    listing = models.ForeignKey(Listing, related_name='conversations', on_delete=models.CASCADE)
    participants = models.ManyToManyField(User, related_name='conversations')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Ensures a unique conversation per listing between the same two users
        # Note: This simple constraint assumes a 2-participant conversation.
        # For group chats, a different approach would be needed.
        pass # A more complex constraint might be needed depending on exact requirements

    def __str__(self):
        return f"Conversation about '{self.listing.title}'"

class Message(models.Model):
    conversation = models.ForeignKey(Conversation, related_name='messages', on_delete=models.CASCADE)
    sender = models.ForeignKey(User, related_name='sent_messages', on_delete=models.CASCADE)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"Message from {self.sender.username} at {self.timestamp}"


class MessageRead(models.Model):
    """Tracks which user has read which message (basic read receipt)."""
    message = models.ForeignKey(Message, related_name='reads', on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name='message_reads', on_delete=models.CASCADE)
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('message', 'user')
        indexes = [
            models.Index(fields=['user', 'message']),
        ]

    def __str__(self):
        return f"Read: {self.user.username} -> {self.message.id}"