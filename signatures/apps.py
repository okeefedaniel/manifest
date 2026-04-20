from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class SignaturesConfig(AppConfig):
    name = 'signatures'
    default_auto_field = 'django.db.models.BigAutoField'
    verbose_name = _('Signatures')

    def ready(self):
        self._register_notification_types()
        self._register_audited_models()

    def _register_audited_models(self):
        try:
            from keel.core.audit_signals import register_audited_model, connect_audit_signals
        except ImportError:
            return

        register_audited_model('signatures.SignatureFlow', 'Signature Flow')
        register_audited_model('signatures.SignatureFlowStep', 'Signature Flow Step')
        register_audited_model('signatures.SignatureRequest', 'Signature Request')
        register_audited_model('signatures.SignatureRole', 'Signature Role')
        register_audited_model('signatures.SigningPacket', 'Signing Packet')
        register_audited_model('signatures.SigningStep', 'Signing Step')
        register_audited_model('signatures.SignaturePlacement', 'Signature Placement')
        register_audited_model('signatures.UserSignature', 'User Signature')
        register_audited_model('signatures.SignatureDocument', 'Signature Document')

        connect_audit_signals()

    def _register_notification_types(self):
        try:
            from keel.notifications import register, NotificationType
        except ImportError:
            return

        register(NotificationType(
            key='signature_required',
            label='Signature Required',
            description='You are the next signer in a document signing flow.',
            category='Signatures',
            default_channels=['in_app', 'email'],
            priority='high',
            email_template='emails/signer_active.html',
            email_subject='Action Required: Signature Needed — {title}',
            allow_mute=False,
        ))

        register(NotificationType(
            key='signing_complete',
            label='Signing Complete',
            description='All signatures have been collected for a document.',
            category='Signatures',
            default_channels=['in_app', 'email'],
            priority='high',
            email_template='emails/packet_completed.html',
            email_subject='Signing Complete — {title}',
        ))

        register(NotificationType(
            key='signing_declined',
            label='Signature Declined',
            description='A signer has declined to sign a document.',
            category='Signatures',
            default_channels=['in_app', 'email'],
            priority='high',
            email_template='emails/packet_declined.html',
            email_subject='Signature Declined — {title}',
        ))

        register(NotificationType(
            key='signature_reminder',
            label='Signature Reminder',
            description='A reminder that your signature is needed.',
            category='Signatures',
            default_channels=['in_app', 'email'],
            priority='high',
            email_template='emails/signer_reminder.html',
            email_subject='Reminder: Signature Needed — {title}',
        ))
