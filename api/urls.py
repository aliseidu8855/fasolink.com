from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token
from .views import RegisterView, CategoryListView, ListingListCreateView, ListingDetailView, StartConversationView ,ConversationListView, ConversationDetailView, MessageCreateView

urlpatterns = [
    # Authentication
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', obtain_auth_token, name='login'),

    # Core
    path('categories/', CategoryListView.as_view(), name='category-list'),
    path('listings/', ListingListCreateView.as_view(), name='listing-list-create'),
    path('listings/<int:pk>/', ListingDetailView.as_view(), name='listing-detail'),
    path('conversations/', ConversationListView.as_view(), name='conversation-list'),
    path('conversations/start/', StartConversationView.as_view(), name='start-conversation'),
    path('conversations/<int:pk>/', ConversationDetailView.as_view(), name='conversation-detail'),
    path('conversations/<int:conversation_id>/messages/', MessageCreateView.as_view(), name='create-message'),
]