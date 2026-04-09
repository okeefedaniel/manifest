"""Manifest's /api/v1/helm-feed/ endpoint.

Exposes document signing metrics for Helm's executive dashboard.
"""
from datetime import timedelta

from django.conf import settings
from django.db.models import Avg, Count, ExpressionWrapper, F, DurationField
from django.utils import timezone

from keel.feed.views import helm_feed_view


def _product_url():
    if getattr(settings, 'DEMO_MODE', False):
        return 'https://demo-manifest.docklabs.ai'
    return 'https://manifest.docklabs.ai'


@helm_feed_view
def manifest_helm_feed(request):
    from signatures.models import SigningPacket, SigningStep

    now = timezone.now()
    base_url = _product_url()

    # ── Metrics ──────────────────────────────────────────────────
    pending_packets = SigningPacket.objects.filter(
        status__in=['draft', 'in_progress'],
    )
    pending_count = pending_packets.count()

    # Pending individual signatures (steps)
    pending_steps = SigningStep.objects.filter(
        status__in=['pending', 'active'],
    ).count()

    completed_this_month = SigningPacket.objects.filter(
        status='completed',
        completed_at__gte=now.replace(day=1, hour=0, minute=0, second=0),
    ).count()

    # Average turnaround for completed packets (last 90 days)
    recently_completed = SigningPacket.objects.filter(
        status='completed',
        completed_at__isnull=False,
        completed_at__gte=now - timedelta(days=90),
    )
    avg_turnaround = None
    if recently_completed.exists():
        avg_result = recently_completed.aggregate(
            avg_days=Avg(
                ExpressionWrapper(
                    F('completed_at') - F('created_at'),
                    output_field=DurationField(),
                )
            )
        )
        if avg_result['avg_days']:
            avg_turnaround = round(avg_result['avg_days'].total_seconds() / 86400, 1)

    metrics = [
        {
            'key': 'pending_signatures',
            'label': 'Pending Packets',
            'value': pending_count,
            'unit': None,
            'trend': None, 'trend_value': None, 'trend_period': None,
            'severity': 'normal',
            'deep_link': f'{base_url}/packets/?status=in_progress',
        },
        {
            'key': 'avg_turnaround',
            'label': 'Avg Turnaround',
            'value': avg_turnaround if avg_turnaround is not None else 0,
            'unit': 'days',
            'trend': None, 'trend_value': None, 'trend_period': None,
            'severity': 'normal',
            'deep_link': f'{base_url}/packets/',
        },
        {
            'key': 'signed_this_month',
            'label': 'Signed This Month',
            'value': completed_this_month,
            'unit': None,
            'trend': None, 'trend_value': None, 'trend_period': None,
            'severity': 'normal',
            'deep_link': f'{base_url}/packets/?status=completed',
        },
    ]

    # ── Action Items ─────────────────────────────────────────────
    action_items = []

    # Packets awaiting signatures (in_progress, ordered by age)
    in_progress = (
        SigningPacket.objects
        .filter(status='in_progress')
        .order_by('created_at')[:5]
    )
    for packet in in_progress:
        action_items.append({
            'id': f'manifest-sign-{packet.pk}',
            'type': 'signature',
            'title': f'Sign: {packet.title[:80]}',
            'description': '',
            'priority': 'high',
            'due_date': '',
            'assigned_to_role': 'executive',
            'deep_link': f'{base_url}/packets/{packet.pk}/',
            'created_at': packet.created_at.isoformat() if packet.created_at else '',
        })

    # ── Alerts ───────────────────────────────────────────────────
    alerts = []

    # Packets stale for > 7 days
    stale_packets = SigningPacket.objects.filter(
        status='in_progress',
        updated_at__lt=now - timedelta(days=7),
    ).count()
    if stale_packets > 0:
        alerts.append({
            'id': 'manifest-stale-packets',
            'type': 'overdue',
            'title': f'{stale_packets} signing packet{"s" if stale_packets != 1 else ""} stale for 7+ days',
            'severity': 'warning',
            'since': '',
            'deep_link': f'{base_url}/packets/?status=in_progress',
        })

    return {
        'product': 'manifest',
        'product_label': 'Manifest',
        'product_url': f'{base_url}/dashboard/',
        'metrics': metrics,
        'action_items': action_items,
        'alerts': alerts,
        'sparklines': {},
    }
