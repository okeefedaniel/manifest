"""
Management command to seed Manifest with demo data.
Usage: python manage.py seed_demo
"""
import random
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from keel.accounts.models import ProductAccess
from signatures.models import (
    SignatureFlow,
    SignatureFlowStep,
    SignatureRole,
    SigningPacket,
    SigningStep,
)

User = get_user_model()

# Demo users are passwordless (keel >= 0.20.1) — login via /demo-login/.
# See keel CLAUDE.md → "Demo authentication — passwordless contract".


class Command(BaseCommand):
    help = 'Seed Manifest with demo roles, flows, packets, and sample signing data.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force', action='store_true',
            help='Run even when DEMO_MODE is not enabled.',
        )
        parser.add_argument(
            '--reset', action='store_true',
            help='Delete existing demo data before seeding.',
        )

    def handle(self, *args, **options):
        if not getattr(settings, 'DEMO_MODE', False) and not options['force']:
            self.stdout.write(self.style.WARNING(
                'DEMO_MODE is not enabled. Use --force to seed anyway.'
            ))
            return

        if options['reset']:
            self._reset()

        self.stdout.write('Seeding Manifest demo data...\n')

        users = self._seed_users()
        roles = self._seed_roles()
        flows = self._seed_flows(users, roles)
        self._seed_packets(users, flows)

        self.stdout.write(self.style.SUCCESS(
            '\nManifest demo seed complete!'
        ))

    def _reset(self):
        self.stdout.write('  Resetting demo data...')
        SigningStep.objects.all().delete()
        SigningPacket.objects.all().delete()
        SignatureFlowStep.objects.all().delete()
        SignatureFlow.objects.all().delete()
        SignatureRole.objects.all().delete()
        self.stdout.write(self.style.WARNING('  All signature data deleted.'))

    def _seed_users(self):
        """Ensure demo users exist with correct ProductAccess."""
        user_defs = [
            ('admin', 'Alex', 'Director', 'admin', True),
            ('staff', 'Sarah', 'Thompson', 'staff', True),
            ('signer', 'Chris', 'Martinez', 'signer', False),
        ]
        users = {}
        for username, first, last, role, is_staff in user_defs:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': first,
                    'last_name': last,
                    'email': f'{username}@manifest.docklabs.ai',
                    'is_staff': is_staff,
                },
            )
            if created:
                user.set_unusable_password()
                user.save()

            ProductAccess.objects.get_or_create(
                user=user,
                product='manifest',
                defaults={'role': role, 'is_active': True},
            )
            users[role] = user
            self.stdout.write(
                f"  User: {user.get_full_name()} ({role}) "
                f"({'created' if created else 'exists'})"
            )

        # Ensure admin is superuser
        admin = users['admin']
        if not admin.is_superuser:
            admin.is_superuser = True
            admin.is_staff = True
            admin.save()

        return users

    def _seed_roles(self):
        """Create SignatureRole records for standalone mode."""
        role_defs = [
            ('director', 'Director',
             'Agency or division director with final sign-off authority.'),
            ('program_officer', 'Program Officer',
             'Manages grant programs and initiates signature flows.'),
            ('fiscal_officer', 'Fiscal Officer',
             'Reviews and certifies financial aspects of agreements.'),
            ('legal_counsel', 'Legal Counsel',
             'Reviews contracts and agreements for legal compliance.'),
            ('grantee', 'Grantee',
             'External party receiving grant funds who must sign agreements.'),
            ('executive', 'Executive',
             'Senior leadership providing executive approval.'),
        ]
        roles = {}
        for key, label, description in role_defs:
            role, created = SignatureRole.objects.get_or_create(
                key=key,
                defaults={'label': label, 'description': description},
            )
            roles[key] = role
            self.stdout.write(
                f"  Role: {label} ({'created' if created else 'exists'})"
            )
        return roles

    def _seed_flows(self, users, roles):
        """Create SignatureFlow templates with steps."""
        admin = users['admin']

        flow_defs = [
            {
                'name': 'Grant Award Agreement',
                'description': (
                    'Standard signature flow for executing new grant award '
                    'agreements. Requires program officer initiation, fiscal '
                    'certification, grantee acceptance, and director approval.'
                ),
                'steps': [
                    (1, 'Program Officer Initiation', 'role', 'program_officer'),
                    (2, 'Fiscal Certification', 'role', 'fiscal_officer'),
                    (3, 'Grantee Signature', 'role', 'grantee'),
                    (4, 'Director Approval', 'role', 'director'),
                ],
            },
            {
                'name': 'Budget Modification',
                'description': (
                    'Approval flow for grant budget modifications. '
                    'Requires fiscal review and program officer sign-off.'
                ),
                'steps': [
                    (1, 'Fiscal Review', 'role', 'fiscal_officer'),
                    (2, 'Grantee Acknowledgment', 'role', 'grantee'),
                    (3, 'Program Officer Approval', 'role', 'program_officer'),
                ],
            },
            {
                'name': 'Close-out Certification',
                'description': (
                    'Final certification flow for grant close-out. All parties '
                    'confirm deliverables met and funds properly expended.'
                ),
                'steps': [
                    (1, 'Grantee Final Report Certification', 'role', 'grantee'),
                    (2, 'Program Officer Verification', 'role', 'program_officer'),
                    (3, 'Fiscal Close-out Certification', 'role', 'fiscal_officer'),
                    (4, 'Director Final Approval', 'role', 'director'),
                ],
            },
            {
                'name': 'Memorandum of Understanding',
                'description': (
                    'Inter-agency or external partnership MOU requiring '
                    'legal review and executive sign-off from both parties.'
                ),
                'steps': [
                    (1, 'Legal Counsel Review', 'role', 'legal_counsel'),
                    (2, 'External Party Signature', 'role', 'grantee'),
                    (3, 'Executive Approval', 'role', 'executive'),
                ],
            },
            {
                'name': 'Contract Amendment',
                'description': (
                    'Amendment to an existing contract or agreement. '
                    'Requires legal review, counterparty acceptance, and '
                    'fiscal certification.'
                ),
                'steps': [
                    (1, 'Legal Review', 'role', 'legal_counsel'),
                    (2, 'Fiscal Impact Assessment', 'role', 'fiscal_officer'),
                    (3, 'Counterparty Signature', 'role', 'grantee'),
                    (4, 'Director Authorization', 'role', 'director'),
                ],
            },
            {
                'name': 'Simple Acknowledgment',
                'description': (
                    'Lightweight single-signature acknowledgment for '
                    'policy updates, training certifications, or notices.'
                ),
                'steps': [
                    (1, 'Recipient Acknowledgment', 'role', 'grantee'),
                ],
            },
        ]

        flows = {}
        for flow_def in flow_defs:
            flow, created = SignatureFlow.objects.get_or_create(
                name=flow_def['name'],
                defaults={
                    'description': flow_def['description'],
                    'created_by': admin,
                    'is_active': True,
                },
            )
            flows[flow_def['name']] = flow
            self.stdout.write(
                f"  Flow: {flow.name} ({'created' if created else 'exists'})"
            )

            if created:
                for order, label, assign_type, role_key in flow_def['steps']:
                    SignatureFlowStep.objects.create(
                        flow=flow,
                        order=order,
                        label=label,
                        assignment_type=assign_type,
                        assigned_role=role_key,
                        is_required=True,
                    )
                self.stdout.write(
                    f"    {len(flow_def['steps'])} steps created"
                )

        return flows

    def _seed_packets(self, users, flows):
        """Create SigningPacket instances in various statuses."""
        now = timezone.now()
        admin = users['admin']
        staff = users['staff']
        signer = users['signer']

        existing = SigningPacket.objects.count()
        if existing >= 15:
            self.stdout.write(
                f"  Packets: {existing} already exist, skipping seed"
            )
            return

        packet_defs = [
            # Completed packets
            {
                'flow': 'Grant Award Agreement',
                'title': 'FY2026 Community Development Block Grant — City of Hartford',
                'status': 'completed',
                'initiated_by': staff,
                'days_ago': 45,
                'completed_days_ago': 12,
            },
            {
                'flow': 'Grant Award Agreement',
                'title': 'FY2026 Workforce Innovation Grant — Bridgeport',
                'status': 'completed',
                'initiated_by': staff,
                'days_ago': 60,
                'completed_days_ago': 30,
            },
            {
                'flow': 'Simple Acknowledgment',
                'title': 'Data Security Policy Update — Q1 2026',
                'status': 'completed',
                'initiated_by': admin,
                'days_ago': 30,
                'completed_days_ago': 28,
            },
            {
                'flow': 'Close-out Certification',
                'title': 'FY2025 Small Business Recovery Fund — Close-out',
                'status': 'completed',
                'initiated_by': staff,
                'days_ago': 90,
                'completed_days_ago': 45,
            },
            # In-progress packets
            {
                'flow': 'Grant Award Agreement',
                'title': 'FY2026 STEM Education Initiative — New Haven Public Schools',
                'status': 'in_progress',
                'initiated_by': staff,
                'days_ago': 5,
                'active_step': 3,
            },
            {
                'flow': 'Budget Modification',
                'title': 'Budget Mod #2 — CT Innovation Fund (Reallocation)',
                'status': 'in_progress',
                'initiated_by': staff,
                'days_ago': 3,
                'active_step': 2,
            },
            {
                'flow': 'Memorandum of Understanding',
                'title': 'MOU — DECD & UConn Research Partnership',
                'status': 'in_progress',
                'initiated_by': admin,
                'days_ago': 10,
                'active_step': 2,
            },
            {
                'flow': 'Contract Amendment',
                'title': 'Amendment #1 — Stamford Innovation Hub Lease',
                'status': 'in_progress',
                'initiated_by': staff,
                'days_ago': 8,
                'active_step': 1,
            },
            {
                'flow': 'Close-out Certification',
                'title': 'FY2025 Brownfield Remediation Grant — Waterbury',
                'status': 'in_progress',
                'initiated_by': staff,
                'days_ago': 14,
                'active_step': 2,
            },
            # Draft packets
            {
                'flow': 'Grant Award Agreement',
                'title': 'FY2026 Rural Broadband Expansion — Litchfield County',
                'status': 'draft',
                'initiated_by': staff,
                'days_ago': 1,
            },
            {
                'flow': 'Memorandum of Understanding',
                'title': 'MOU — DECD & CT Department of Labor (Workforce Pipeline)',
                'status': 'draft',
                'initiated_by': admin,
                'days_ago': 2,
            },
            # Cancelled packet
            {
                'flow': 'Grant Award Agreement',
                'title': 'FY2026 Tourism Recovery Grant — Mystic (Withdrawn)',
                'status': 'cancelled',
                'initiated_by': staff,
                'days_ago': 20,
                'cancelled_days_ago': 15,
                'cancel_reason': 'Applicant withdrew application prior to execution.',
            },
            # Declined packet
            {
                'flow': 'Contract Amendment',
                'title': 'Amendment #3 — Hartford Convention Center Services',
                'status': 'declined',
                'initiated_by': staff,
                'days_ago': 25,
            },
            # More in-progress for variety
            {
                'flow': 'Grant Award Agreement',
                'title': 'FY2026 Clean Energy Manufacturing — Danbury',
                'status': 'in_progress',
                'initiated_by': staff,
                'days_ago': 2,
                'active_step': 1,
            },
            {
                'flow': 'Simple Acknowledgment',
                'title': 'Conflict of Interest Disclosure — Annual Review',
                'status': 'in_progress',
                'initiated_by': admin,
                'days_ago': 1,
                'active_step': 1,
            },
        ]

        # Map users to roles for signing step assignment
        role_signers = {
            'director': admin,
            'program_officer': staff,
            'fiscal_officer': staff,
            'legal_counsel': staff,
            'grantee': signer,
            'executive': admin,
        }

        for pdef in packet_defs:
            flow = flows[pdef['flow']]
            created_at = now - timedelta(days=pdef['days_ago'])

            packet = SigningPacket.objects.create(
                flow=flow,
                title=pdef['title'],
                status=pdef['status'],
                initiated_by=pdef['initiated_by'],
            )
            # Backdate created_at
            SigningPacket.objects.filter(pk=packet.pk).update(
                created_at=created_at,
            )

            if pdef['status'] == 'completed':
                completed_at = now - timedelta(
                    days=pdef.get('completed_days_ago', 0)
                )
                SigningPacket.objects.filter(pk=packet.pk).update(
                    completed_at=completed_at,
                )

            if pdef['status'] == 'cancelled':
                cancelled_at = now - timedelta(
                    days=pdef.get('cancelled_days_ago', 0)
                )
                SigningPacket.objects.filter(pk=packet.pk).update(
                    cancelled_at=cancelled_at,
                    cancelled_by=admin,
                    cancel_reason=pdef.get('cancel_reason', ''),
                )

            # Create signing steps for this packet
            flow_steps = flow.steps.order_by('order')
            active_step_order = pdef.get('active_step')

            for fstep in flow_steps:
                step_signer = role_signers.get(fstep.assigned_role, signer)

                if pdef['status'] == 'completed':
                    step_status = 'signed'
                    signed_at = created_at + timedelta(
                        days=random.randint(1, pdef['days_ago'] - pdef.get('completed_days_ago', 0))
                    )
                elif pdef['status'] in ('cancelled', 'declined'):
                    if fstep.order == 1:
                        step_status = 'signed'
                        signed_at = created_at + timedelta(days=1)
                    elif pdef['status'] == 'declined' and fstep.order == 2:
                        step_status = 'declined'
                        signed_at = None
                    else:
                        step_status = 'pending'
                        signed_at = None
                elif pdef['status'] == 'in_progress' and active_step_order:
                    if fstep.order < active_step_order:
                        step_status = 'signed'
                        signed_at = created_at + timedelta(
                            days=fstep.order
                        )
                    elif fstep.order == active_step_order:
                        step_status = 'active'
                        signed_at = None
                    else:
                        step_status = 'pending'
                        signed_at = None
                else:
                    step_status = 'pending'
                    signed_at = None

                step = SigningStep.objects.create(
                    packet=packet,
                    flow_step=fstep,
                    order=fstep.order,
                    signer=step_signer,
                    status=step_status,
                )

                if step_status == 'signed' and signed_at:
                    SigningStep.objects.filter(pk=step.pk).update(
                        signed_at=signed_at,
                        signature_type='typed',
                        typed_name=step_signer.get_full_name(),
                        signed_ip='10.0.0.1',
                    )
                elif step_status == 'declined':
                    SigningStep.objects.filter(pk=step.pk).update(
                        declined_at=created_at + timedelta(days=2),
                        decline_reason='Terms require revision before signing.',
                    )

        self.stdout.write(f"  Packets: {len(packet_defs)} created")
