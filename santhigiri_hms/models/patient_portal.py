# -*- coding: utf-8 -*-
"""
Patient Portal — backend models.

Reception registers a patient as a res.partner with a Patient ID. The
portal lets that patient log in with Patient ID + password (a portal
user whose login is the Patient ID) or Patient ID + one-time code (OTP)
sent by SMS / e-mail.  This file contains:

  * santhigiri.patient.portal.otp  — every OTP that was issued, stored
    only as an HMAC hash, with expiry, attempt counter and rate limits.
  * res.partner helpers            — phone lookup, masking, default OP
    category for online bookings, and PASSWORD LOGIN: a patient can own
    a portal user (res.users, group Portal) whose login is exactly the
    Patient ID, so "Patient ID + password" works on /patient/login and
    on Odoo's standard /web/login.
  * portal.wizard.user extension   — Odoo's standard "Grant portal
    access" (Contacts > Action > Portal Access Management) works for
    patients too: login = Patient ID, e-mail optional.
  * hospital.outpatient helpers    — "can the patient cancel this?"
  * doctor.allocation fix          — cancelled OPs no longer hold a slot,
    so a slot freed by a portal cancellation can be booked again.
"""
import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta

import pytz

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import email_normalize

_logger = logging.getLogger(__name__)

# ── Tunables (kept as constants; the ones hospitals usually change are
#    ir.config_parameter values, see data/patient_portal_data.xml) ─────────
OTP_LENGTH = 6
OTP_VALIDITY_MINUTES = 10
MAX_VERIFY_ATTEMPTS = 5          # wrong guesses allowed per code
RESEND_COOLDOWN_SECONDS = 60     # min gap between two codes
MAX_CODES_PER_WINDOW = 5         # codes allowed per patient ...
CODE_WINDOW_MINUTES = 30         # ... within this window
PURGE_AFTER_DAYS = 7
MIN_PASSWORD_LENGTH = 8

DEFAULT_TZ = 'Asia/Kolkata'
PARAM_DEBUG = 'santhigiri_hms.portal_otp_debug'
PARAM_USE_ODOO_SMS = 'santhigiri_hms.portal_otp_use_odoo_sms'


def portal_local_now(env):
    """Current date-time in the hospital's timezone.

    Portal visitors are anonymous (public user, no timezone), so "today"
    and "is this slot already over?" must be decided in the hospital's
    own timezone — otherwise, between 00:00 and 05:30 IST, UTC would
    still say it is yesterday."""
    tz_name = env.company.sudo().partner_id.tz or DEFAULT_TZ
    try:
        tz = pytz.timezone(tz_name)
    except pytz.UnknownTimeZoneError:
        tz = pytz.timezone(DEFAULT_TZ)
    return datetime.now(tz).replace(tzinfo=None)


class PatientPortalOtp(models.Model):
    _name = 'santhigiri.patient.portal.otp'
    _description = 'Patient Portal One-Time Password'
    _order = 'create_date desc, id desc'
    _rec_name = 'patient_id'

    patient_id = fields.Many2one(
        'res.partner', string='Patient', required=True,
        ondelete='cascade', index=True)
    patient_seq = fields.Char(related='patient_id.patient_seq',
                              string='Patient ID')
    otp_hash = fields.Char(string='Code Hash', required=True, copy=False,
                           groups='base.group_system')
    expires_at = fields.Datetime(string='Expires At', required=True)
    attempts = fields.Integer(string='Wrong Attempts', default=0)
    state = fields.Selection([
        ('pending', 'Pending'),
        ('verified', 'Verified (logged in)'),
        ('expired', 'Expired / Replaced'),
        ('blocked', 'Blocked (too many attempts)'),
    ], string='Status', default='pending', required=True, index=True)
    channel = fields.Char(string='Sent Via',
                          help='Comma-separated list: sms, email, debug')
    ip_address = fields.Char(string='Requested From IP')
    verified_at = fields.Datetime(string='Verified At')

    # ── Hashing ──────────────────────────────────────────────────────────
    @api.model
    def _hash_code(self, patient_id, code):
        """HMAC-SHA256 keyed with the database secret: a DB dump alone
        is not enough to recover codes, and hashes differ per patient."""
        secret = self.env['ir.config_parameter'].sudo().get_param(
            'database.secret') or ''
        message = f'{patient_id}:{code}'.encode()
        return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()

    # ── Issue ────────────────────────────────────────────────────────────
    @api.model
    def _issue_for(self, patient, ip_address=None):
        """Create a new OTP for ``patient`` and return (record, code).

        Raises UserError when the rate limits are hit.  Any older pending
        code for the same patient is invalidated so only the latest one
        works.
        """
        patient.ensure_one()
        now = fields.Datetime.now()
        recent = self.sudo().search([
            ('patient_id', '=', patient.id),
            ('create_date', '>=', now - timedelta(minutes=CODE_WINDOW_MINUTES)),
        ])
        if len(recent) >= MAX_CODES_PER_WINDOW:
            raise UserError(_(
                'Too many codes were requested for this Patient ID. '
                'Please try again after %(minutes)s minutes or contact '
                'the reception.', minutes=CODE_WINDOW_MINUTES))
        if recent:
            elapsed = (now - recent[0].create_date).total_seconds()
            if elapsed < RESEND_COOLDOWN_SECONDS:
                raise UserError(_(
                    'A code was sent just now. Please wait %(seconds)s '
                    'seconds before requesting another one.',
                    seconds=int(RESEND_COOLDOWN_SECONDS - elapsed) + 1))

        self.sudo().search([
            ('patient_id', '=', patient.id), ('state', '=', 'pending'),
        ]).write({'state': 'expired'})

        code = ''.join(secrets.choice('0123456789') for _i in range(OTP_LENGTH))
        record = self.sudo().create({
            'patient_id': patient.id,
            'otp_hash': self._hash_code(patient.id, code),
            'expires_at': now + timedelta(minutes=OTP_VALIDITY_MINUTES),
            'ip_address': ip_address,
        })
        return record, code

    # ── Verify ───────────────────────────────────────────────────────────
    def _verify_code(self, code):
        """Return (ok, error_message). Counts wrong attempts and blocks
        the code after MAX_VERIFY_ATTEMPTS."""
        self.ensure_one()
        if self.state != 'pending':
            return False, _('This code is no longer valid. '
                            'Please request a new one.')
        if fields.Datetime.now() > self.expires_at:
            self.state = 'expired'
            return False, _('This code has expired. Please request a new one.')

        code = (code or '').strip()
        expected = self.otp_hash
        if code.isdigit() and len(code) == OTP_LENGTH and hmac.compare_digest(
                self._hash_code(self.patient_id.id, code), expected):
            self.write({'state': 'verified',
                        'verified_at': fields.Datetime.now()})
            return True, ''

        self.attempts += 1
        if self.attempts >= MAX_VERIFY_ATTEMPTS:
            self.state = 'blocked'
            return False, _('Too many incorrect attempts. '
                            'Please request a new code.')
        return False, _('Incorrect code. %(left)s attempt(s) left.',
                        left=MAX_VERIFY_ATTEMPTS - self.attempts)

    # ── Delivery ─────────────────────────────────────────────────────────
    def _deliver(self, code):
        """Send ``code`` to the patient. Returns the list of channels
        that succeeded (possibly empty)."""
        self.ensure_one()
        patient = self.patient_id
        company = self.env.company
        text = _('%(code)s is your %(hospital)s patient portal code. '
                 'It is valid for %(minutes)s minutes. Do not share it '
                 'with anyone.', code=code, hospital=company.name,
                 minutes=OTP_VALIDITY_MINUTES)
        channels = []

        phone = patient._portal_phone()
        if phone:
            try:
                if self._send_sms(phone, text):
                    channels.append('sms')
            except Exception:  # never let a gateway error break login
                _logger.exception('Patient portal: SMS delivery failed')

        if patient.email:
            try:
                self.env['mail.mail'].sudo().create({
                    'subject': _('Your patient portal login code'),
                    'body_html': '<p>%s</p>' % text,
                    'email_to': patient.email,
                    'email_from': company.email or False,
                    'auto_delete': True,
                }).send(raise_exception=False)
                channels.append('email')
            except Exception:
                _logger.exception('Patient portal: e-mail delivery failed')

        if self._is_debug_mode():
            # TEST ONLY — see santhigiri_hms.portal_otp_debug
            _logger.warning('PATIENT PORTAL DEBUG: OTP for %s is %s',
                            patient.patient_seq, code)
            channels.append('debug')

        self.channel = ','.join(channels)
        return channels

    def _send_sms(self, phone, text):
        """SMS hook. Return True when the message was handed to a gateway.

        Option 1 — Odoo's own SMS app (IAP credits needed): install the
        ``sms`` module and set system parameter
        santhigiri_hms.portal_otp_use_odoo_sms = True.

        Option 2 — your own gateway (MSG91, Twilio, Kaleyra ...): override
        this method in a small module, e.g.::

            import requests
            def _send_sms(self, phone, text):
                resp = requests.post('https://api.msg91.com/api/v5/flow/',
                                     json={...}, timeout=10)
                return resp.ok
        """
        use_odoo_sms = self.env['ir.config_parameter'].sudo().get_param(
            PARAM_USE_ODOO_SMS)
        if use_odoo_sms in ('1', 'True', 'true') and 'sms.sms' in self.env:
            sms = self.env['sms.sms'].sudo().create(
                {'number': phone, 'body': text})
            sms.send()
            return True
        return False

    @api.model
    def _is_debug_mode(self):
        value = self.env['ir.config_parameter'].sudo().get_param(PARAM_DEBUG)
        return value in ('1', 'True', 'true')

    # ── Housekeeping ─────────────────────────────────────────────────────
    @api.model
    def _cron_purge_old_codes(self):
        limit = fields.Datetime.now() - timedelta(days=PURGE_AFTER_DAYS)
        self.sudo().search([('create_date', '<', limit)]).unlink()


class ResPartnerPortal(models.Model):
    _inherit = 'res.partner'

    portal_password_set = fields.Boolean(
        string='Portal Password Login', compute='_compute_portal_password_set',
        help='True when this patient can log in to the patient portal with '
             'Patient ID + password.')

    def _compute_portal_password_set(self):
        for rec in self:
            rec.portal_password_set = rec._portal_has_password()

    # ── Password login ───────────────────────────────────────────────────
    def _portal_user(self):
        """The (active) portal user linked to this patient, if any."""
        self.ensure_one()
        return self.sudo().user_ids.filtered(lambda u: u.share)[:1]

    def _portal_has_password(self):
        """True when the patient's portal user exists AND has a password.

        A user created with "Grant portal access" has no password until the
        patient sets one (invitation e-mail link, or OTP login on
        /patient/login), so "has a user" is not the same as "can log in
        with a password"."""
        self.ensure_one()
        user = self._portal_user()
        if not user:
            return False
        self.env.cr.execute(
            "SELECT COALESCE(password, '') <> '' FROM res_users WHERE id = %s",
            [user.id])
        row = self.env.cr.fetchone()
        return bool(row and row[0])

    def _portal_user_any(self):
        """Portal user of this patient INCLUDING archived (revoked) ones.
        A revoked patient must not get back in with Patient ID as the
        password."""
        self.ensure_one()
        return self.env['res.users'].sudo().with_context(
            active_test=False).search([('partner_id', '=', self.id),
                                       ('share', '=', True)], limit=1)

    @api.model
    def _portal_check_password_strength(self, password, patient=None):
        """Simple policy; returns an error message or ''."""
        password = password or ''
        if len(password) < MIN_PASSWORD_LENGTH:
            return _('The password must have at least %(n)s characters.',
                     n=MIN_PASSWORD_LENGTH)
        if patient and patient.patient_seq and (
                patient.patient_seq.lower() in password.lower()):
            return _('The password must not contain your Patient ID.')
        if password.isdigit() and len(set(password)) <= 2:
            return _('This password is too easy to guess.')
        return ''

    def _portal_set_password(self, password):
        """Create the patient's portal user (login = Patient ID) or, when a
        portal user already exists, only reset its password (its username
        is kept). Returns the res.users record."""
        self.ensure_one()
        if not self._portal_is_patient():
            raise UserError(_('Only registered patients can get portal access.'))
        error = self._portal_check_password_strength(password, self)
        if error:
            raise ValidationError(error)
        if self.sudo().user_ids.filtered(lambda u: not u.share):
            raise UserError(_(
                'This patient record is linked to an internal (staff) user, '
                'so a separate portal login cannot be created for it.'))

        Users = self.env['res.users'].sudo().with_context(
            no_reset_password=True, active_test=False)
        user = Users.search([('partner_id', '=', self.id),
                             ('share', '=', True)], limit=1)
        if user:
            # Keep the existing username: a portal user created the standard
            # Odoo way (Contacts > Grant portal access, or Settings > Users)
            # usually has the e-mail as login and must keep working on
            # /web/login. Patient ID login still works on /patient/login.
            user.write({'password': password, 'active': True})
            return user

        clash = Users.search([('login', '=ilike', self.patient_seq)], limit=1)
        if clash:
            raise UserError(_(
                'The login "%(login)s" is already used by another user '
                '(%(name)s).', login=self.patient_seq, name=clash.name))
        return Users.create({
            'name': self.name,
            'login': self.patient_seq,
            'partner_id': self.id,
            'password': password,
            'group_ids': [Command.set([self.env.ref('base.group_portal').id])],
        })

    def _portal_is_patient(self):
        """Same rule the base module uses for its Patient menu."""
        self.ensure_one()
        return bool(not self.is_company and self.patient_seq
                    and self.patient_seq not in ('New', 'Employee', 'User'))

    def _portal_phone(self):
        self.ensure_one()
        # 'mobile' does not exist on res.partner in every Odoo version
        return self.phone or getattr(self, 'mobile', False) or ''

    def _portal_masked_phone(self):
        phone = ''.join(ch for ch in self._portal_phone() if ch.isdigit())
        return ('•' * 6 + phone[-4:]) if len(phone) >= 4 else ''

    def _portal_masked_email(self):
        self.ensure_one()
        email = (self.email or '').strip()
        if '@' not in email:
            return ''
        local, domain = email.split('@', 1)
        return '%s%s@%s' % (local[:1], '•' * max(len(local) - 1, 3), domain)

    def _portal_default_op_category(self):
        """Pre-fill the OP category for an online booking from the
        patient's registration data. Reception can still change it when
        the patient arrives (e.g. after checking a BPL card)."""
        self.ensure_one()
        if self.jeevanam_scheme:
            return 'jeevanam'
        if self.vulnerability == 'bpl':
            return 'bpl'
        if self.vulnerability == 'senior_citizen' or (self.age or 0) >= 60:
            return 'senior_citizen'
        return 'general'


class HospitalOutpatientPortal(models.Model):
    _inherit = 'hospital.outpatient'

    def _portal_can_cancel(self):
        """A patient may cancel only a future / today's booking that has
        not been consulted or billed yet."""
        self.ensure_one()
        return (self.state in ('draft', 'op')
                and not self.invoice_id
                and self.op_date
                and self.op_date >= portal_local_now(self.env).date())

    def _portal_slot_display(self):
        self.ensure_one()
        if not self.slot:
            return ''
        hours = int(self.slot)
        minutes = int(round((self.slot - hours) * 60))
        if minutes == 60:
            hours, minutes = hours + 1, 0
        return '%02d:%02d' % (hours, minutes)


class DoctorAllocationPortal(models.Model):
    """Base module counts EVERY OP (including cancelled ones) against the
    allocation limit, so a cancelled booking kept the slot blocked
    forever. Only non-cancelled OPs consume a slot now."""
    _inherit = 'doctor.allocation'

    @api.depends('op_ids', 'op_ids.state')
    def _compute_patient_count(self):
        for rec in self:
            rec.patient_count = len(
                rec.op_ids.filtered(lambda op: op.state != 'cancel'))

    @api.depends('op_ids', 'op_ids.state', 'patient_limit')
    def _compute_slot_remaining(self):
        for rec in self:
            active_ops = rec.op_ids.filtered(lambda op: op.state != 'cancel')
            rec.slot_remaining = rec.patient_limit - len(active_ops)


class PortalWizardUserPatient(models.TransientModel):
    """Odoo's standard "Grant portal access" window, adapted for patients.

    Standard Odoo requires a valid, unique e-mail for every contact because
    the e-mail becomes the login. For PATIENTS this extension:
      * uses the Patient ID as the login (same as the patient portal),
      * makes the e-mail optional (Grant Access is offered without one),
      * sends Odoo's invitation e-mail only when there is an e-mail;
        otherwise the patient creates the password with a one-time code
        on /patient/login.
    Other contacts (customers, vendors ...) keep Odoo's normal behaviour.
    """
    _inherit = 'portal.wizard.user'

    @api.depends('email')
    def _compute_email_state(self):
        patient_lines = self.filtered(
            lambda line: line.partner_id._portal_is_patient())
        super(PortalWizardUserPatient,
              self - patient_lines)._compute_email_state()
        Users = self.env['res.users'].sudo().with_context(active_test=False)
        for line in patient_lines:
            if line.email and not email_normalize(line.email):
                line.email_state = 'ko'       # typed an invalid e-mail
            elif Users.search_count([
                    ('login', '=ilike', line.partner_id.patient_seq),
                    ('id', '!=', line.user_id.id or 0)]):
                line.email_state = 'exist'    # Patient ID already a login
            else:
                line.email_state = 'ok'       # e-mail optional

    def _create_user(self):
        if not self.partner_id._portal_is_patient():
            return super()._create_user()
        return self.env['res.users'].with_context(
            no_reset_password=True)._create_user_from_template({
                'email': email_normalize(self.email or '') or False,
                'login': self.partner_id.patient_seq,
                'partner_id': self.partner_id.id,
                'company_id': self.env.company.id,
                'company_ids': [(6, 0, self.env.company.ids)],
            })

    def _patient_without_email(self):
        self.ensure_one()
        return (self.partner_id._portal_is_patient()
                and not email_normalize(self.email or '')
                and not email_normalize(self.partner_id.email or ''))

    def _send_email(self):
        self.ensure_one()
        if self._patient_without_email():
            # No address to send the invitation to: log it instead.
            self.partner_id.sudo().message_post(
                body=_('Portal access granted. Login: %(login)s. No e-mail on '
                       'file, so no invitation was sent: the patient creates '
                       'the password at /patient/login > "Log in with a '
                       'one-time code".', login=self.partner_id.patient_seq),
                message_type='comment', subtype_xmlid='mail.mt_note')
            return True
        return super()._send_email()

    def action_invite_again(self):
        self.ensure_one()
        if self._patient_without_email():
            raise UserError(_(
                'The patient "%s" has no e-mail, so an invitation cannot be '
                'sent. The patient can create the password at /patient/login '
                'with "Log in with a one-time code" (sent to the registered '
                'mobile number).', self.partner_id.name))
        return super().action_invite_again()