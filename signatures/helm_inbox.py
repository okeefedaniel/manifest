"""Per-user Helm inbox endpoint for Manifest.

Returns the signing items where the requesting user is the gating
signer right now (their step is ACTIVE on an IN_PROGRESS packet),
plus that user's unread notifications.

Conforms to ``helm.dashboard.feed_contract.UserInbox``. Auth mirrors
``keel.feed.views.helm_feed_view``: Bearer token via ``HELM_FEED_API_KEY``,
demo-mode bypass, 60-req/min rate limit, but cache key includes the
``user_sub`` query param so users never see each other's inbox.

This decorator lives in Manifest as the pilot consumer. When peer #2
adopts (Harbor), promote it to ``keel.feed.views`` as ``helm_inbox_view``.
"""
import functools
import hmac
import logging
import time

from allauth.socialaccount.models import SocialAccount
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from .models import Notification, SigningPacket, SigningStep

logger = logging.getLogger(__name__)
User = get_user_model()

_RATE_LIMIT_REQUESTS = 60
_RATE_LIMIT_WINDOW_SECONDS = 60
_CACHE_TTL_SECONDS = 60


def _rate_limited(api_key: str) -> bool:
    key = f'keel:helm_inbox_rate:{api_key[:16]}'
    now = time.time()
    bucket = [t for t in (cache.get(key) or []) if now - t < _RATE_LIMIT_WINDOW_SECONDS]
    if len(bucket) >= _RATE_LIMIT_REQUESTS:
        return True
    bucket.append(now)
    cache.set(key, bucket, timeout=_RATE_LIMIT_WINDOW_SECONDS)
    return False


def _resolve_user_from_sub(sub: str):
    """OIDC sub → local KeelUser via SocialAccount.uid (provider='keel')."""
    if not sub:
        return None
    sa = (
        SocialAccount.objects
        .filter(provider='keel', uid=sub)
        .select_related('user')
        .first()
    )
    return sa.user if sa else None


def helm_inbox_view(build_inbox_func):
    """Auth + per-user cache wrapper for inbox endpoints.

    Wrapped function signature: ``build_inbox(request, user) -> dict``
    where ``user`` is the resolved local KeelUser. Returns a dict
    matching ``UserInbox`` shape.
    """

    @csrf_exempt
    @require_GET
    @functools.wraps(build_inbox_func)
    def wrapper(request):
        demo_mode = getattr(settings, 'DEMO_MODE', False)
        if demo_mode:
            expected = (
                getattr(settings, 'HELM_FEED_DEMO_API_KEY', '')
                or getattr(settings, 'HELM_FEED_API_KEY', '')
                or ''
            )
        else:
            expected = getattr(settings, 'HELM_FEED_API_KEY', '') or ''

        if not expected:
            return JsonResponse(
                {'error': 'Helm feed not configured (HELM_FEED_API_KEY missing).'},
                status=503,
            )

        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer ') or not hmac.compare_digest(
            auth_header[7:].strip(), expected,
        ):
            return JsonResponse({'error': 'Invalid API key.'}, status=401)

        if _rate_limited(expected):
            return JsonResponse({'error': 'Rate limit exceeded.'}, status=429)

        user_sub = (request.GET.get('user_sub') or '').strip()
        if not user_sub:
            return JsonResponse({'error': 'user_sub query parameter is required.'}, status=400)

        # Per-user cache: path + sub. Never serves user A's payload to user B.
        cache_key = f'keel:helm_inbox_cache:{request.path}:{user_sub}'
        cached = cache.get(cache_key)
        if cached is not None:
            return JsonResponse(cached)

        user = _resolve_user_from_sub(user_sub)
        if user is None:
            # Unknown sub: return an empty inbox rather than 404 so the
            # aggregator can render "0 items" without an error path. The
            # response still identifies which product reported the empty.
            payload = {
                'product': getattr(settings, 'KEEL_PRODUCT_CODE', 'manifest'),
                'product_label': getattr(settings, 'KEEL_PRODUCT_NAME', 'Manifest'),
                'product_url': getattr(settings, 'PRODUCT_URL', ''),
                'user_sub': user_sub,
                'items': [],
                'unread_notifications': [],
                'fetched_at': timezone.now().isoformat(),
            }
            cache.set(cache_key, payload, timeout=_CACHE_TTL_SECONDS)
            return JsonResponse(payload)

        try:
            payload = build_inbox_func(request, user)
        except Exception:
            logger.exception('Error building helm inbox for user_sub=%s', user_sub)
            return JsonResponse({'error': 'Internal error building inbox.'}, status=500)

        if not payload.get('user_sub'):
            payload['user_sub'] = user_sub
        if not payload.get('fetched_at'):
            payload['fetched_at'] = timezone.now().isoformat()

        cache.set(cache_key, payload, timeout=_CACHE_TTL_SECONDS)
        return JsonResponse(payload)

    return wrapper


@helm_inbox_view
def manifest_helm_feed_inbox(request, user):
    """Build Manifest's per-user inbox.

    Inbox items: SigningSteps where this user is the signer, the step is
    ACTIVE (their turn), and the parent packet is IN_PROGRESS.

    Notifications: unread Notification rows for this user.
    """
    product_url = getattr(settings, 'PRODUCT_URL', '').rstrip('/')

    active_steps = (
        SigningStep.objects
        .filter(
            signer=user,
            status=SigningStep.Status.ACTIVE,
            packet__status=SigningPacket.Status.IN_PROGRESS,
        )
        .select_related('packet')
        .order_by('packet__created_at')
    )

    items = []
    for step in active_steps:
        packet = step.packet
        deep_link = f'{product_url}/signatures/packets/{packet.id}/' if product_url else f'/signatures/packets/{packet.id}/'
        items.append({
            'id': str(step.id),
            'type': 'signature',
            'title': f'Sign: {packet.title}',
            'deep_link': deep_link,
            'waiting_since': step.updated_at.isoformat() if getattr(step, 'updated_at', None) else packet.created_at.isoformat(),
            'due_date': None,
            'priority': 'high',
        })

    unread = (
        Notification.objects
        .filter(recipient=user, is_read=False)
        .order_by('-created_at')[:50]
    )

    notifications = []
    for n in unread:
        link = n.link or ''
        if link and product_url and link.startswith('/'):
            link = f'{product_url}{link}'
        notifications.append({
            'id': str(n.id),
            'title': n.title,
            'body': getattr(n, 'message', '') or '',
            'deep_link': link,
            'created_at': n.created_at.isoformat(),
            'priority': (n.priority or 'normal').lower(),
        })

    return {
        'product': getattr(settings, 'KEEL_PRODUCT_CODE', 'manifest'),
        'product_label': getattr(settings, 'KEEL_PRODUCT_NAME', 'Manifest'),
        'product_url': product_url,
        'user_sub': '',  # filled by decorator
        'items': items,
        'unread_notifications': notifications,
        'fetched_at': '',  # filled by decorator
    }
