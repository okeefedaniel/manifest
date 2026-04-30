# Manifest User Manual

Manifest is the e-signature platform for the DockLabs suite. It captures
multi-party signatures on PDFs through configurable, ordered workflows
and serves as the cross-product signing handoff layer — peer products
(Harbor, Bounty, Helm, Lookout, etc.) hand off documents to Manifest for
signature, and Manifest returns the signed PDF and a completion event
when the packet is done.

This manual covers the user-facing surface end to end. For operations,
see [CLAUDE.md](../CLAUDE.md).

---

## Contents

1. [Overview](#overview)
2. [Roles](#roles)
3. [Getting Started](#getting-started)
4. [Flows (templates)](#flows-templates)
5. [Steps & signers](#steps--signers)
6. [Documents & placements](#documents--placements)
7. [Roles registry](#roles-registry)
8. [Template Builder wizard](#template-builder-wizard)
9. [Packets (active signing sessions)](#packets-active-signing-sessions)
10. [The signing experience](#the-signing-experience)
11. [Saved signatures](#saved-signatures)
12. [Cross-product handoff](#cross-product-handoff)
13. [Helm inbox feed](#helm-inbox-feed)
14. [Audit trail](#audit-trail)
15. [Notifications](#notifications)
16. [Status reference](#status-reference)
17. [Keyboard shortcuts](#keyboard-shortcuts)
18. [Support](#support)

---

## Overview

Manifest has two complementary surfaces:

- **Admin** — `/flows/` and `/roles/` — where staff define reusable
  signing flows: ordered steps, signer assignments, document templates,
  and signature placements.
- **Active signing** — `/packets/` (also mounted at `/dashboard/`) —
  where a flow is instantiated against a real entity, signers complete
  their steps in order, and the final signed PDF is sealed with an
  audit trail.

Manifest is the cross-product **signing handoff layer** for the
DockLabs suite. Peer products call `keel.signatures.client.send_to_manifest()`
to hand off a document; Manifest signs it; a `packet_approved` event
returns the signed PDF and any completion metadata back to the source.

---

## Roles

Manifest's signer roles can be sourced two ways:

- **Suite mode** (deployed alongside other DockLabs products) — roles
  come from `KeelUser.Role` via SSO claims (`product_access`).
- **Standalone mode** — roles are managed in the Manifest UI at
  `/roles/`. Each role has a `key`, `label`, optional description, and
  an `is_active` flag.

Staff-only surfaces (creating flows, editing placements, initiating and
cancelling packets, viewing audit trails) are gated to users with
`is_staff` plus the `grant_manager` or equivalent agency-staff role.
Any authenticated user can sign their own assigned step.

---

## Getting Started

### Signing in

1. From any DockLabs product, click **Manifest** in the fleet switcher,
   or visit `https://manifest.docklabs.ai/`.
2. Click **Sign in with DockLabs** (the suite OIDC button).
3. You'll land on `/dashboard/` — the Packets list.

If you arrived via an email signing link (`/sign/<step_id>/`), you'll
be sent through the same login flow and bounced back to the signing
page once authenticated.

### What you'll see first

- **Packets** — every signing session you can see, with status, signer
  progress, and quick links.
- **My Signatures** — the list of pending signing steps assigned to
  you across every packet.

---

## Flows (templates)

A **SignatureFlow** is the reusable template that drives every packet:
a name, an optional description, an ordered list of steps, the document
templates that will be signed, and the signature placements on those
documents.

`/flows/` lists every active flow. Click a flow to drill in:

- **Steps** — the ordered signing sequence (see below).
- **Documents** — the PDF templates attached to the flow.
- **Placements** — where each signer signs on each page.

Flows are reusable. The same "Grant Award Agreement" flow can drive
hundreds of packets — one per award.

### Creating a flow

`/flows/create/` (staff only). Provide a name and optional description.
After creation, add steps, upload documents, and define placements.

Flows can be linked to a `GrantProgram` (when deployed alongside Harbor)
or stand alone.

---

## Steps & signers

A **SignatureFlowStep** is one signer in the flow. Each step carries:

- **Order** — execution sequence (1 = first signer).
- **Label** — e.g. "Program Officer Approval", "Director Sign-off".
- **Assignment type** — `user` (a specific person) or `role` (a role
  key like `director`).
- **Required** — whether the step blocks completion.

Steps are executed **sequentially**. Step 2 only becomes ACTIVE after
step 1 is SIGNED. The packet completes when every required step has
been signed.

### Editing steps

`/flows/<flow_id>/steps/create/` and `/steps/<id>/edit/` (staff only).

---

## Documents & placements

A **SignatureDocument** is the PDF template attached to a flow. Files
are validated by Keel's `FileSecurityValidator` (extension allowlist,
size limit, malware scan). Page count is auto-populated on upload.

A **SignaturePlacement** says "this field, on this page, at this
position, belongs to this signer." Coordinates are stored as
**percentages** of page dimensions, so placements stay correct
regardless of rendering DPI or zoom level.

Field types:

| Field type | Purpose |
|---|---|
| **Signature** | A captured signature image. |
| **Initials** | A short initials capture. |
| **Date** | The auto-stamped signing date. |
| **Printed name** | The signer's typed name. |

### Placement editor

`/documents/<id>/placements/` opens the visual placement editor — a
PDF preview with drag-to-position fields. Save sends each placement to
the JSON API at `/api/documents/<id>/placements/`.

---

## Roles registry

`/roles/` (staff only) is the standalone-mode role manager. Use it when
Manifest is deployed alone and you can't rely on SSO-issued role
claims.

Each role has:

- **Key** — machine-readable slug (e.g. `director`).
- **Label** — human-readable name.
- **Description** — optional context.
- **Active flag** — toggle without deleting.

When a step's assignment type is **role**, the matching role key is
resolved at packet-initiation time to whichever user holds that role.

---

## Template Builder wizard

`/builder/` (or `/builder/<flow_id>/` to edit) is a unified wizard that
walks staff through:

1. Flow metadata (name, description).
2. Steps + signer assignments.
3. Document upload.
4. Placement editor.
5. Save.

The wizard saves through `/api/builder/save/` — a single round-trip
that creates or updates the flow plus its dependents atomically.

---

## Packets (active signing sessions)

A **SigningPacket** is an instance of a flow being executed. Packets
are listed at `/packets/`.

Each packet carries:

- **Flow** — the template it was instantiated from.
- **Title** — descriptive label.
- **Source entity** — optional generic FK to any model (Harbor Award,
  Bounty Opportunity, etc.) so the packet links back to whatever
  drove its creation.
- **Status** — Draft / In Progress / Completed / Cancelled / Declined.
- **Signed document** — the final sealed PDF, generated when every
  step is signed.
- **Initiated by** + timestamps for create / complete / cancel.

### Initiating a packet

`/packets/initiate/<flow_id>/` (staff only). Pick the source entity
(if any), confirm signer assignments, and submit. Manifest creates a
SigningStep for each flow step, sets step 1 to ACTIVE, sends the first
signer their email link, and the packet enters IN_PROGRESS.

### Cancelling a packet

`/packets/<id>/cancel/` (staff only) — record a reason. Cancelled
packets are terminal; signers can no longer sign.

---

## The signing experience

When you're the active signer, you receive:

- An email with a `/sign/<step_id>/` link.
- A `signature_required` notification visible in your sidebar bell.
- An item in your Helm dashboard's **Awaiting Me** column.

Click the link. Manifest renders:

- The PDF with your placement fields highlighted.
- A signature capture pad — type, draw, or upload an image.
- A signing intent confirmation.
- A **Sign** button (and a **Decline** button, with a required reason).

### Signing

Submit fires `/sign/<step_id>/complete/`. Manifest:

1. Records the signature image, IP, and timestamp.
2. Marks the step SIGNED.
3. Activates the next step (if any) and emails its signer.
4. If yours was the last step, generates the final signed PDF and
   marks the packet COMPLETED.

### Declining

`/sign/<step_id>/decline/` — record a reason. Declining marks the step
DECLINED and the packet DECLINED (terminal). Other signers stop
receiving prompts.

---

## Saved signatures

`/my/signatures/` — your library of saved signatures for fast reuse:

- **Typed** — a font-rendered signature from your name.
- **Drawn** — captured on a touch / mouse pad.
- **Uploaded** — a PNG you supplied.

Each signature has a label (e.g. "Formal", "Initials") and an optional
**default** flag. Defaults pre-populate the signing pad when you sign.

`/my/signatures/<id>/default/` toggles the default; `/delete/` removes
a saved signature.

---

## Cross-product handoff

Manifest is the suite's signing handoff layer. The contract:

1. **Inbound** — a peer product (Harbor, Bounty, Helm, etc.) calls
   `keel.signatures.client.send_to_manifest(source_obj, flow, signers,
   ...)`. The peer creates a `ManifestHandoff` row pointing at the
   Manifest packet UUID.
2. **Manifest signs** — the packet runs through its normal step
   sequence. Signers receive their email links and complete in order.
3. **Outbound completion** — when the packet completes, Manifest
   POSTs the signed PDF to the source product's webhook
   (`/keel/signatures/webhook/`) signed with `MANIFEST_WEBHOOK_SECRET`.
   The source's `packet_approved` signal handler attaches the signed
   PDF, advances the source workflow status, notifies collaborators,
   and registers the file with `keel.foia.export`.

### Standalone mode

Manifest works fully standalone — no peer products required. A flow
with no `source_entity` GFK runs the same way; the signed PDF is
available at `/packets/<id>/` and via direct download.

Conversely, peer products work when Manifest is unavailable: their
"Send to Manifest" controls are gated by an `is_available()` check
and fall back to a local "mark approved + upload signed PDF" path.

### Incoming hand-offs in the UI

When a packet is initiated by a peer call, the Packet detail page
shows the **source entity** (with a clickable URL back to the source
product when configured). The source label and URL ride through on
provenance fields and surface as a "Origin" row in the packet header.

---

## Helm inbox feed

Manifest exposes two helm-feed endpoints:

| Endpoint | Purpose |
|---|---|
| `/api/v1/helm-feed/` | Aggregate metrics for Helm's "Across the suite" dashboard (active packets, completed in period, declined, etc.). |
| `/api/v1/helm-feed/inbox/?user_sub=<sub>` | Per-user inbox: the SigningSteps where this user is the active signer and the parent packet is IN_PROGRESS, plus that user's unread Manifest notifications. |

Both require `Authorization: Bearer $HELM_FEED_API_KEY` (skipped in
`DEMO_MODE`). The per-user endpoint resolves the OIDC `sub` claim to
the local user via `SocialAccount(provider='keel', uid=sub)` — unknown
subs return an empty `items[]` (200), not 404.

The data Helm displays in **Awaiting Me → Manifest** comes from the
inbox endpoint: title `Sign: <packet title>`, deep link to
`/packets/<id>/`, priority `high`.

---

## Audit trail

Every meaningful event is written to a Keel `AuditLog` row, immutable
and FOIA-exportable:

- Flow created / edited / deleted.
- Document uploaded / deleted.
- Placement created / moved / deleted.
- Packet initiated / cancelled.
- Step activated / signed / declined / reminded.
- Signed PDF generated.

`/packets/<id>/audit/` (staff only) renders the per-packet trail with
timestamps, actor, IP, and structured payload. The trail is what gives
ESIGN / UETA-compliant evidence of consent and process.

---

## Notifications

Manifest fires the following notification events:

| Event | When it fires |
|---|---|
| `signature_required` | Your signing step has just become ACTIVE. |
| `signature_reminder` | A reminder was sent for your pending step. |
| `signing_complete` | A packet you're on completed. |
| `signing_declined` | A packet you're on was declined by another signer. |

Channels (in-app + email) are user-configurable at
`/notifications/preferences/`. The link is in the sidebar user-menu
dropdown.

---

## Status reference

### Packet status

| Status | Meaning |
|---|---|
| **Draft** | Created but not yet sent to the first signer. |
| **In Progress** | At least one step is ACTIVE; others may be PENDING. |
| **Completed** | Every required step is SIGNED. Signed PDF available. |
| **Cancelled** | Staff cancelled the packet. Terminal. |
| **Declined** | A signer declined. Terminal. |

### Step status

| Status | Meaning |
|---|---|
| **Pending** | Not the signer's turn yet (a prior step is still active). |
| **Active** | The signer's turn now. |
| **Signed** | Signed and stamped. |
| **Declined** | Signer refused; carries a reason. |
| **Skipped** | Optional step skipped. |

### Signature type

| Type | Meaning |
|---|---|
| **Typed** | Rendered from typed name in a script font. |
| **Drawn** | Captured on a signature pad. |
| **Uploaded** | A PNG image supplied by the signer. |

### Field type

Signature, Initials, Date, Printed Name.

---

## Keyboard shortcuts

| Key | Action |
|---|---|
| **⌘K** / **Ctrl+K** | Open the suite-wide search modal. |

---

## Support

- **Email** — info@docklabs.ai (1–2 business day response).
- **Feedback widget** — bottom-right corner of every page; routes to
  the shared support queue.
- **Per-product help** — for questions specific to Harbor, Helm,
  Beacon, etc., open the help link inside that product.

---

*Last updated: 2026-04-30.*
