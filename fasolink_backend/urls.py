from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from api import views as api_views


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    # SEO helpers at root
    path('robots.txt', api_views.RobotsTxtView.as_view(), name='robots-txt'),
    path('sitemap.xml', api_views.SitemapIndexView.as_view(), name='sitemap-index'),
    path('sitemap-static.xml', api_views.SitemapStaticView.as_view(), name='sitemap-static'),
    path('sitemap-categories.xml', api_views.SitemapCategoriesView.as_view(), name='sitemap-categories'),
    path('sitemap-listings.xml', api_views.SitemapListingsView.as_view(), name='sitemap-listings'),
]

# urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += [
    # API Schema:
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    # Optional UI:
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]


# if settings.DEBUG or not settings.DEBUG:
#     urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)