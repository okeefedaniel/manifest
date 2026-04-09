"""Manifest standalone URL configuration."""
from django.contrib import admin
from django.contrib.auth.views import LoginView
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

from keel.core.views import health_check, robots_txt, SuiteLogoutView
from keel.core.demo import demo_login_view
from keel.accounts.forms import LoginForm
from keel.core.search_views import search_view
from signatures.helm_feed import manifest_helm_feed
from signatures.views import PacketListView


urlpatterns = [
    path('robots.txt', robots_txt, name='robots_txt'),
    path('health/', health_check),
    path('admin/', admin.site.urls),

    # Custom login/logout views using the shared keel LoginForm so the
    # input fields render with Bootstrap styling. Mounted before the
    # allauth include so they shadow allauth's bare LoginView.
    path('accounts/login/', LoginView.as_view(
        template_name='account/login.html',
        authentication_form=LoginForm,
    ), name='account_login'),
    path('accounts/logout/', SuiteLogoutView.as_view(), name='account_logout'),
    path('accounts/', include('allauth.urls')),

    # Convenience named URL for the "Sign in with Microsoft" button
    path(
        'auth/sso/microsoft/',
        RedirectView.as_view(url='/accounts/microsoft/login/?process=login', query_string=False),
        name='microsoft_login',
    ),

    # Canonical suite-wide post-login URL. Mounts the real Manifest
    # dashboard view (PacketListView) directly so the URL bar stays at
    # /dashboard/ instead of 302'ing to /packets/. The legacy
    # signatures:packet-list URL still resolves to /packets/ for any
    # reverse() calls in templates.
    path('dashboard/', PacketListView.as_view(), name='dashboard_alias'),

    path('demo-login/', demo_login_view, name='demo_login'),
    # Helm executive dashboard feed
    path('api/v1/helm-feed/', manifest_helm_feed, name='helm-feed'),
    path('notifications/', include('keel.notifications.urls')),
    path('', include('signatures.urls')),
    path('search/', search_view, name='search'),
    path('keel/requests/', include('keel.requests.urls')),
    path('keel/', include('keel.accounts.urls')),
    path('keel/', include('keel.core.foia_urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
