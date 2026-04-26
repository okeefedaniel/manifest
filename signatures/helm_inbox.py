"""Per-user Helm inbox endpoint for Manifest.

Returns the signing items where the requesting user is the gating
signer right now (their step is ACTIVE on an IN_PROGRESS packet),
plus that user's unread notifications.

Conforms to ``helm.dashboard.feed_contract.UserInbox``. Auth + cache
+ user resolution all come from ``keel.feed.views.helm_inbox_view``
(promoted from this file's pilot implementation in keel 0.18.0).
"""
from django.conf import settings
from keel.feed.views import helm_inbox_view

from .models import Notification, SigningPacket, SigningStep


@helm_inbox_view
def manifest_helm_feed_inbox(request, user):
    """Build Manifest's per-user inbox.

    Inbox items: SigningSteps where this user is the signer, the step
    is ACTIVE (their turn), and the parent packet is IN_PROGRESS.

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
        path = f'/signatures/packets/{packet.id}/'
        items.append({
            'id': str(step.id),
            'type': 'signature',
            'title': f'Sign: {packet.title}',
            'deep_link': f'{product_url}{path}' if product_url else path,
            'waiting_since': step.updated_at.isoformat(),
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
