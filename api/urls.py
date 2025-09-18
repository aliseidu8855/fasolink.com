from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token
from .views import (
    RegisterView,
    MeView,
    StatsView,
    DashboardStatsView,
    CategoryListView,
    ListingListCreateView,
    ListingDetailView,
    ListingsFacetsView,
    StartConversationView,
    ConversationListView,
    ConversationDetailView,
    UserListingsView,
    ConversationMessagesView,
    MarkConversationReadView,
    SpecsMetadataView,
    LocationsSuggestView,
    RUMIngestView,
)

urlpatterns = [
    # Authentication
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/me/", MeView.as_view(), name="me"),
    path("stats/", StatsView.as_view(), name="stats"),
    path("dashboard/stats/", DashboardStatsView.as_view(), name="dashboard-stats"),
    path("auth/login/", obtain_auth_token, name="login"),
    # Core
    path("categories/", CategoryListView.as_view(), name="category-list"),
    path("listings/", ListingListCreateView.as_view(), name="listing-list-create"),
    path("listings/facets/", ListingsFacetsView.as_view(), name="listing-facets"),
    path("listings/<int:pk>/", ListingDetailView.as_view(), name="listing-detail"),
    path("conversations/", ConversationListView.as_view(), name="conversation-list"),
    path(
        "conversations/start/",
        StartConversationView.as_view(),
        name="start-conversation",
    ),
    path(
        "conversations/<int:pk>/",
        ConversationDetailView.as_view(),
        name="conversation-detail",
    ),
    path(
        "conversations/<int:conversation_id>/messages/",
        ConversationMessagesView.as_view(),
        name="conversation-messages",
    ),
    path(
        "conversations/<int:conversation_id>/mark-read/",
        MarkConversationReadView.as_view(),
        name="conversation-mark-read",
    ),
    path("profile/my-listings/", UserListingsView.as_view(), name="user-listings"),
    path("specs-metadata/", SpecsMetadataView.as_view(), name="specs-metadata"),
    path(
        "locations-suggest/", LocationsSuggestView.as_view(), name="locations-suggest"
    ),
    path("rum/", RUMIngestView.as_view(), name="rum-ingest"),
]
