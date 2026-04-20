"""Declarative workflows for the signatures app.

Adoption plan (see DockLabs engineering principles — keel/CLAUDE.md
§ Workflows & Status Tracking): define every valid transition here,
then migrate view-level ``packet.status = X; packet.save()`` calls to
``PACKET_WORKFLOW.execute(packet, X, user=...)``. The engine enforces
role checks and emits status-history rows centrally.

This file is the **first** half of the adoption. The models in
``models.py`` still allow direct status writes; callers in ``views.py``
should migrate to the engine one path at a time so the system is never
left in a half-converted state.
"""
from keel.core.workflow import Transition, WorkflowEngine


# ---------------------------------------------------------------------------
# SigningPacket workflow
# ---------------------------------------------------------------------------
# Packet lifecycle: DRAFT → IN_PROGRESS → (COMPLETED | CANCELLED | DECLINED).
# Only agency staff can create/cancel; the DECLINED terminal state is
# reached when any signer declines during IN_PROGRESS (driven by step
# workflow below, surfaced via an on_complete hook).
PACKET_WORKFLOW = WorkflowEngine([
    Transition(
        from_status='draft',
        to_status='in_progress',
        roles=['agency_staff', 'grant_manager'],
        label='Send for signing',
        description='Starts the signing flow by emailing the first signer.',
    ),
    Transition(
        from_status='in_progress',
        to_status='completed',
        roles=['any'],
        label='All signers completed',
        description='Terminal state: every step is signed.',
    ),
    Transition(
        from_status='in_progress',
        to_status='cancelled',
        roles=['agency_staff', 'grant_manager'],
        label='Cancel packet',
        require_comment=True,
    ),
    Transition(
        from_status='in_progress',
        to_status='declined',
        roles=['any'],
        label='Signer declined',
        description='Terminal state: a signer declined to sign.',
    ),
    Transition(
        from_status='draft',
        to_status='cancelled',
        roles=['agency_staff', 'grant_manager'],
        label='Discard draft',
    ),
])


# ---------------------------------------------------------------------------
# SigningStep workflow
# ---------------------------------------------------------------------------
# Step lifecycle: PENDING → ACTIVE → (SIGNED | DECLINED | SKIPPED).
STEP_WORKFLOW = WorkflowEngine([
    Transition(
        from_status='pending',
        to_status='active',
        roles=['any'],
        label='Advance to signer',
        description='Driven by the packet engine — prior step completed.',
    ),
    Transition(
        from_status='active',
        to_status='signed',
        roles=['any'],  # the signer themselves; role check on the packet side
        label='Sign',
    ),
    Transition(
        from_status='active',
        to_status='declined',
        roles=['any'],
        label='Decline',
        require_comment=True,
    ),
    Transition(
        from_status='active',
        to_status='skipped',
        roles=['agency_staff', 'grant_manager'],
        label='Skip this signer',
        require_comment=True,
    ),
])
