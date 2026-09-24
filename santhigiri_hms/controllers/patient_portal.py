# -*- coding: utf-8 -*-
"""
Santhigiri Patient Portal — website controller.

URL map (all pages except /patient/login* need a logged-in patient):

    /patient                                   dashboard
    /patient/login              GET/POST       Patient ID (or Odoo username) + password
    /patient/login/otp          GET/POST       Patient ID -> send OTP
    /patient/login/verify       GET/POST       enter OTP -> log in
    /patient/login/resend       POST           send a fresh OTP
    /patient/password           GET/POST       create / change the password
    /patient/logout             GET
    /patient/appointments                      OP visits (upcoming + past)
    /patient/appointments/<id>                 one visit, prescription, follow-up
    /patient/appointments/<id>/prescription    prescription PDF
    /patient/appointments/<id>/cancel  POST    cancel an upcoming booking
    /patient/book                              -> redirects to /santhigiri/book
    /patient/lab                               lab tests
    /patient/lab/<id>                          results of one lab test
    /patient/lab/result/<id>/download          result document
    /patient/admissions                        IP admissions
    /patient/admissions/<id>                   one admission
    /patient/admissions/<id>/discharge-summary discharge summary PDF
    /patient/procedures                        procedure / therapy courses
    /patient/followups                         follow-up reminders
    /patient/bills                             posted invoices + dues
    /patient/bills/<id>/pdf                    invoice PDF
    /patient/profile                           registered details (read-only)
    /patient/card                              patient ID card PDF

Booking is NOT part of the portal: patients book on the website page
/santhigiri/book (controllers/portal.py, Patient ID + OTP — unchanged).
Booked visits appear in the portal under "My Appointments", where they
can also be cancelled.

Three ways to log in
--------------------
1. Patient ID + password. The password belongs to a portal user
   (res.users, group "Portal") whose login is exactly the Patient ID,
   created by the patient after an OTP check (or the optional first
   login with the Patient ID). Odoo's own authentication is
   used: hashed passwords, login cool-down after repeated failures, a
   normal Odoo session. The same credentials also work on Odoo's
   standard /web/login. A portal user created the standard Odoo way
   (Contacts > Action > Grant portal access, or Settings > Users, with
   the e-mail as username) works too: log in with that username on
   /web/login or /patient/login.
2. Patient ID + one-time code (OTP) by SMS / e-mail. Needs no password;
   also used for "first time" and "forgot password".
3. Optional (system parameter
   santhigiri_hms.portal_first_login_with_patient_id = True):
   FIRST login with Patient ID as login AND Patient ID as password.
   Works only while the patient has no password yet; the patient must
   then create his own password before anything else is shown.

Security model
--------------
Records are read with sudo() because the patient data models have no
portal access rules. That is only safe because EVERY query below is
filtered on the logged-in patient (``_own()`` / ``_own_domain()``); a
record id coming from the URL is never browsed directly.
"""
import base64
import logging
import time

from odoo import _, http
from odoo.exceptions import AccessDenied, UserError, ValidationError
from odoo.http import content_disposition, request
from odoo.tools.mimetypes import guess_mimetype

from odoo.addons.santhigiri_hms.models.patient_portal import (
    OTP_VALIDITY_MINUTES,
    portal_local_now,
)
from odoo.addons.website.controllers.main import Website

_logger = logging.getLogger(__name__)

SESSION_PATIENT = 'shms_portal_patient_id'
SESSION_LAST_SEEN = 'shms_portal_last_seen'
SESSION_PENDING_OTP = 'shms_portal_pending_otp_id'
SESSION_REDIRECT = 'shms_portal_redirect'
SESSION_FLASH = 'shms_portal_flash'
SESSION_OTP_VERIFIED_AT = 'shms_portal_otp_verified_at'
# After an OTP login the patient may set a password without typing an
# old one, but only within this many seconds.
OTP_PASSWORD_WINDOW = 15 * 60

PARAM_TIMEOUT = 'santhigiri_hms.portal_session_timeout_minutes'
# When True, a patient who has NO password yet may log in ONE time with
# Patient ID as login AND Patient ID as password; he is then forced to
# choose his own password before he can see anything.
PARAM_FIRST_LOGIN_WITH_ID = 'santhigiri_hms.portal_first_login_with_patient_id'
SESSION_MUST_SET_PASSWORD = 'shms_portal_must_set_password'
PARAM_BOOKING_DAYS = 'santhigiri_hms.portal_booking_days'


def float_to_time(value):
    """10.5 -> '10:30' (doctor.allocation stores times as float hours)."""
    if value is None or value is False:
        return ''
    hours = int(value)
    minutes = int(round((value - hours) * 60))
    if minutes == 60:
        hours, minutes = hours + 1, 0
    return '%02d:%02d' % (hours, minutes)


def selection_label(record, field_name):
    """Human label of a selection field value ('' when empty)."""
    if not record:
        return ''
    value = record[field_name]
    if not value:
        return ''
    return dict(record._fields[field_name]._description_selection(
        record.env)).get(value, value)


class SanthigiriWebsiteLogin(Website):
    """A patient who logs in on Odoo's standard /web/login with Patient ID
    + password lands on the patient portal instead of /my."""

    def _login_redirect(self, uid, redirect=None):
        if not redirect:
            user = request.env['res.users'].sudo().browse(uid)
            if user.share and user.partner_id._portal_is_patient():
                redirect = '/patient'
        return super()._login_redirect(uid, redirect=redirect)


class SanthigiriPatientPortal(http.Controller):

    # ════════════════════════════════════════════════════════════════════
    #  Session helpers
    # ════════════════════════════════════════════════════════════════════
    def _param(self, key, default):
        return request.env['ir.config_parameter'].sudo().get_param(
            key, default)

    def _session_timeout_seconds(self):
        try:
            return max(int(self._param(PARAM_TIMEOUT, 30)), 5) * 60
        except (TypeError, ValueError):
            return 30 * 60

    def _current_patient(self):
        """Return the logged-in patient (sudo res.partner) or None.

        * Password login -> an Odoo session of the patient's portal user.
        * OTP login      -> the patient id stored in the session.
        A logged-in STAFF user is not treated as a patient.

        Sliding idle timeout: every page view pushes the expiry forward;
        after N idle minutes the patient must log in again (shared
        computers, kiosks, family phones)."""
        user = request.env.user
        if request.session.uid and not user._is_public():
            partner = user.sudo().partner_id
            if not (user.share and partner._portal_is_patient()):
                return None
            patient = partner
        else:
            patient_id = request.session.get(SESSION_PATIENT)
            if not patient_id:
                return None
            patient = request.env['res.partner'].sudo().browse(
                int(patient_id)).exists()
            if not patient or not patient._portal_is_patient():
                self._logout_session()
                return None

        # No timestamp yet = fresh login made outside this controller
        # (e.g. Odoo's /web/login) -> start the idle clock now.
        last_seen = request.session.get(SESSION_LAST_SEEN)
        if last_seen and time.time() - last_seen > self._session_timeout_seconds():
            self._logout_session()
            self._flash('warning', _('Your session expired. '
                                     'Please log in again.'))
            return None
        request.session[SESSION_LAST_SEEN] = time.time()
        if (request.session.get(SESSION_MUST_SET_PASSWORD)
                and request.httprequest.path != '/patient/password'):
            return None  # _require_login() sends him to /patient/password
        return patient

    def _first_login_with_id_enabled(self):
        return str(self._param(PARAM_FIRST_LOGIN_WITH_ID, 'False')).lower() in (
            '1', 'true')

    def _login_session(self, patient):
        """OTP login: remember the patient in the session."""
        request.session.pop(SESSION_PENDING_OTP, None)
        request.session[SESSION_PATIENT] = patient.id
        request.session[SESSION_LAST_SEEN] = time.time()
        request.session[SESSION_OTP_VERIFIED_AT] = time.time()
        # New session id after authentication (prevents session fixation)
        request.session.should_rotate = True

    def _authenticate_user(self, user, password):
        """Password login through Odoo's own authentication (hashing,
        brute-force cool-down, session token). Raises AccessDenied."""
        request.session.authenticate(request.env, {
            'login': user.login, 'password': password, 'type': 'password'})
        for key in (SESSION_PATIENT, SESSION_PENDING_OTP,
                    SESSION_MUST_SET_PASSWORD):
            request.session.pop(key, None)
        request.session[SESSION_LAST_SEEN] = time.time()

    def _logout_session(self):
        for key in (SESSION_PATIENT, SESSION_LAST_SEEN, SESSION_PENDING_OTP,
                    SESSION_OTP_VERIFIED_AT, SESSION_MUST_SET_PASSWORD):
            request.session.pop(key, None)
        if request.session.uid:
            request.session.logout(keep_db=True)

    def _require_login(self):
        """Redirect to login, remembering where the patient wanted to go."""
        if (request.session.get(SESSION_MUST_SET_PASSWORD)
                and request.session.get(SESSION_PATIENT)):
            self._flash('warning', _('Please create your own password first.'))
            return request.redirect('/patient/password')
        path = request.httprequest.path
        if path.startswith('/patient') and request.httprequest.method == 'GET':
            request.session[SESSION_REDIRECT] = request.httprequest.full_path
        return request.redirect('/patient/login')

    @staticmethod
    def _safe_redirect_target(target):
        """Only allow redirects back into the portal (no open redirect)."""
        if (target and target.startswith('/patient')
                and not target.startswith('//') and '\\' not in target):
            return target.rstrip('?')
        return '/patient'

    def _flash(self, level, text):
        request.session[SESSION_FLASH] = {'level': level, 'text': str(text)}

    def _render(self, template, patient=None, page=None, **values):
        values.update({
            'patient': patient,
            'portal_page': page,
            'flash': request.session.pop(SESSION_FLASH, None),
            'float_to_time': float_to_time,
            'selection_label': selection_label,
            'today': portal_local_now(request.env).date(),
            'first_login_enabled': self._first_login_with_id_enabled(),
            'hospital': request.env.company.sudo(),
        })
        return request.render(template, values)

    # ════════════════════════════════════════════════════════════════════
    #  Ownership helpers — the ONLY way records are fetched
    # ════════════════════════════════════════════════════════════════════
    _OWNER_FIELD = {
        'hospital.outpatient': 'patient_id',
        'hospital.inpatient': 'patient_id',
        'patient.lab.test': 'patient_id',
        'hospital.procedure.prescription': 'patient_id',
        'hospital.followup': 'patient_id',
        'account.move': 'partner_id',
    }

    def _own_domain(self, model, patient):
        return [(self._OWNER_FIELD[model], '=', patient.id)]

    def _own(self, model, record_id, patient, extra_domain=None):
        """Fetch one record by id ONLY if it belongs to ``patient``."""
        domain = [('id', '=', int(record_id))] + self._own_domain(
            model, patient) + (extra_domain or [])
        return request.env[model].sudo().search(domain, limit=1)

    @staticmethod
    def _invoice_domain():
        return [('move_type', 'in', ('out_invoice', 'out_refund')),
                ('state', '=', 'posted')]

    def _pdf_response(self, pdf, filename):
        return request.make_response(pdf, headers=[
            ('Content-Type', 'application/pdf'),
            ('Content-Length', len(pdf)),
            ('Content-Disposition', content_disposition(filename)),
            ('Cache-Control', 'no-store'),
        ])

    def _render_pdf(self, report_xmlid, record, filename):
        try:
            pdf, _type = request.env['ir.actions.report'].sudo(
            )._render_qweb_pdf(report_xmlid, res_ids=record.ids)
        except Exception:
            _logger.exception('Patient portal: PDF rendering failed (%s)',
                              report_xmlid)
            return None
        return self._pdf_response(pdf, filename)

    # ════════════════════════════════════════════════════════════════════
    #  Login  (Patient ID  ->  OTP  ->  session)
    # ════════════════════════════════════════════════════════════════════
    def _find_patient(self, patient_ref):
        """Patient ID lookup, case-insensitive ('pat-0001' == 'PAT-0001')."""
        patient_ref = (patient_ref or '').strip()
        if not patient_ref:
            return request.env['res.partner']
        return request.env['res.partner'].sudo().search([
            ('patient_seq', '=ilike', patient_ref),
            ('is_company', '=', False),
            ('patient_seq', 'not in', ('New', 'Employee', 'User')),
        ], limit=1)

    def _find_patient_by_username(self, username):
        """Patient whose Odoo portal user has this username (login), e.g.
        an e-mail set by 'Grant portal access'. Returns (patient, user)."""
        username = (username or '').strip()
        if not username:
            return request.env['res.partner'], request.env['res.users']
        user = request.env['res.users'].sudo().search(
            [('login', '=ilike', username), ('share', '=', True)], limit=1)
        if user and user.partner_id._portal_is_patient():
            return user.partner_id, user
        return request.env['res.partner'], request.env['res.users']

    # ── 1. Patient ID (or Odoo username) + password ───────────────────
    @http.route('/patient/login', type='http', auth='public', website=True,
                methods=['GET'], sitemap=False)
    def portal_login(self, **kw):
        if self._current_patient():
            return request.redirect('/patient')
        return self._render('santhigiri_hms.patient_portal_login')

    @http.route('/patient/login', type='http', auth='public', website=True,
                methods=['POST'], sitemap=False)
    def portal_login_submit(self, patient_ref=None, password=None, **kw):
        patient_ref = (patient_ref or '').strip()
        if not patient_ref or not password:
            return self._render(
                'santhigiri_hms.patient_portal_login', patient_ref=patient_ref,
                error=_('Please enter your Patient ID and password.'))

        patient = self._find_patient(patient_ref)
        user = patient._portal_user() if patient else None
        if not patient:
            # Not a Patient ID: maybe the patient's Odoo username (e-mail)
            patient, user = self._find_patient_by_username(patient_ref)
        if patient and not (user and patient._portal_has_password()):
            # No password yet (no user, or a user created by "Grant portal
            # access" whose password was never set).
            # ── Optional first login: Patient ID as the password ──────
            if (self._first_login_with_id_enabled()
                    and (user or not patient._portal_user_any())
                    and password.strip().upper()
                    == (patient.patient_seq or '').upper()):
                if request.session.uid:
                    request.session.logout(keep_db=True)
                self._login_session(patient)
                request.session[SESSION_MUST_SET_PASSWORD] = True
                patient.message_post(
                    body=_('Patient portal FIRST login with Patient ID as '
                           'password (IP %s).',
                           request.httprequest.remote_addr or '-'),
                    message_type='comment', subtype_xmlid='mail.mt_note')
                self._flash('info', _('Welcome! For your safety, please '
                                      'create your own password now. Your '
                                      'Patient ID will not work as a '
                                      'password after this.'))
                return request.redirect('/patient/password')
            return self._render(
                'santhigiri_hms.patient_portal_login', patient_ref=patient_ref,
                no_password=True,
                error=_('Wrong Patient ID or password. If this is your first '
                        'login, use your Patient ID as the password or log '
                        'in with a one-time code (OTP).')
                if self._first_login_with_id_enabled() else
                _('No password has been created for this Patient ID '
                  'yet. Log in once with a one-time code (OTP) and '
                  'create your password.'))
        if not user:
            return self._render(
                'santhigiri_hms.patient_portal_login', patient_ref=patient_ref,
                error=_('Wrong Patient ID or password.'))
        try:
            self._authenticate_user(user, password)
        except AccessDenied as err:
            message = (err.args[0] if err.args and err.args != AccessDenied().args
                       else _('Wrong Patient ID or password.'))
            return self._render('santhigiri_hms.patient_portal_login',
                                patient_ref=patient_ref, error=message)

        patient.message_post(
            body=_('Patient portal login with password (IP %s).',
                   request.httprequest.remote_addr or '-'),
            message_type='comment', subtype_xmlid='mail.mt_note')
        return request.redirect(self._safe_redirect_target(
            request.session.pop(SESSION_REDIRECT, None)))

    # ── 2. Patient ID + one-time code ─────────────────────────────────
    @http.route('/patient/login/otp', type='http', auth='public',
                website=True, methods=['GET'], sitemap=False)
    def portal_login_otp(self, patient_ref=None, **kw):
        if self._current_patient():
            return request.redirect('/patient')
        return self._render('santhigiri_hms.patient_portal_login_otp',
                            patient_ref=patient_ref or '')

    @http.route('/patient/login/otp', type='http', auth='public',
                website=True, methods=['POST'], sitemap=False)
    def portal_login_otp_submit(self, patient_ref=None, **kw):
        patient_ref = (patient_ref or '').strip()
        if not patient_ref:
            return self._render('santhigiri_hms.patient_portal_login_otp',
                                error=_('Please enter your Patient ID.'))
        patient = self._find_patient(patient_ref)
        if not patient:
            return self._render(
                'santhigiri_hms.patient_portal_login_otp',
                patient_ref=patient_ref,
                error=_('We could not find a patient with this ID. Please '
                        'check your ID card or contact the reception.'))
        return self._send_code(patient, patient_ref)

    def _send_code(self, patient, patient_ref=''):
        Otp = request.env['santhigiri.patient.portal.otp'].sudo()
        try:
            otp, code = Otp._issue_for(
                patient, ip_address=request.httprequest.remote_addr)
        except UserError as err:
            # A code may still be pending: let the patient type it in.
            if request.session.get(SESSION_PENDING_OTP):
                self._flash('warning', err.args[0])
                return request.redirect('/patient/login/verify')
            return self._render('santhigiri_hms.patient_portal_login_otp',
                                patient_ref=patient_ref, error=err.args[0])

        channels = otp._deliver(code)
        if not channels:
            otp.state = 'expired'
            return self._render(
                'santhigiri_hms.patient_portal_login_otp',
                patient_ref=patient_ref,
                error=_('No mobile number or e-mail that can receive a login '
                        'code is registered for this Patient ID. Please '
                        'contact the reception to add your mobile number '
                        'or e-mail.'))

        request.session[SESSION_PENDING_OTP] = otp.id
        if 'debug' in channels:
            # Shown on the next page only while TEST MODE is switched on.
            request.session['shms_portal_debug_code'] = code
        return request.redirect('/patient/login/verify')

    def _pending_otp(self):
        otp_id = request.session.get(SESSION_PENDING_OTP)
        if not otp_id:
            return request.env['santhigiri.patient.portal.otp']
        return request.env['santhigiri.patient.portal.otp'].sudo().browse(
            int(otp_id)).exists()

    def _render_verify(self, otp, error=None):
        patient = otp.patient_id
        channels = (otp.channel or '').split(',')
        return self._render(
            'santhigiri_hms.patient_portal_verify',
            error=error,
            masked_phone=patient._portal_masked_phone()
            if 'sms' in channels else '',
            masked_email=patient._portal_masked_email()
            if 'email' in channels else '',
            debug_code=request.session.pop('shms_portal_debug_code', None),
            validity=OTP_VALIDITY_MINUTES,
        )

    @http.route('/patient/login/verify', type='http', auth='public',
                website=True, methods=['GET'], sitemap=False)
    def portal_verify(self, **kw):
        otp = self._pending_otp()
        if not otp or otp.state != 'pending':
            self._flash('warning', _('Please enter your Patient ID to '
                                     'receive a login code.'))
            return request.redirect('/patient/login/otp')
        return self._render_verify(otp)

    @http.route('/patient/login/verify', type='http', auth='public',
                website=True, methods=['POST'], sitemap=False)
    def portal_verify_submit(self, otp_code=None, **kw):
        otp = self._pending_otp()
        if not otp:
            self._flash('warning', _('Your login attempt expired. '
                                     'Please start again.'))
            return request.redirect('/patient/login')

        ok, error = otp._verify_code(otp_code)
        if not ok:
            if otp.state != 'pending':  # expired / blocked -> start over
                request.session.pop(SESSION_PENDING_OTP, None)
                self._flash('danger', error)
                return request.redirect('/patient/login/otp')
            return self._render_verify(otp, error=error)

        patient = otp.patient_id
        if request.session.uid:  # someone else (e.g. staff) was logged in
            request.session.logout(keep_db=True)
        self._login_session(patient)
        patient.message_post(
            body=_('Patient portal login with OTP (IP %s).',
                   request.httprequest.remote_addr or '-'),
            message_type='comment', subtype_xmlid='mail.mt_note')
        if not patient._portal_has_password():
            self._flash('info', _('Welcome! Create a password so that next '
                                  'time you can log in with your Patient '
                                  'ID and password.'))
            return request.redirect('/patient/password')
        target = self._safe_redirect_target(
            request.session.pop(SESSION_REDIRECT, None))
        return request.redirect(target)

    @http.route('/patient/login/resend', type='http', auth='public',
                website=True, methods=['POST'], sitemap=False)
    def portal_resend(self, **kw):
        otp = self._pending_otp()
        if not otp:
            return request.redirect('/patient/login/otp')
        return self._send_code(otp.patient_id)

    # ── Create / change password ──────────────────────────────────────
    def _otp_recently_verified(self):
        verified_at = request.session.get(SESSION_OTP_VERIFIED_AT) or 0
        return (not request.session.uid
                and time.time() - verified_at <= OTP_PASSWORD_WINDOW)

    @http.route('/patient/password', type='http', auth='public',
                website=True, methods=['GET'], sitemap=False)
    def portal_password(self, **kw):
        patient = self._current_patient()
        if not patient:
            return self._require_login()
        return self._render_password(patient)

    def _render_password(self, patient, error=None):
        has_password = patient._portal_has_password()
        # Old password is required, except right after an OTP login.
        need_old = has_password and not self._otp_recently_verified()
        otp_expired = (not has_password and not request.session.uid
                       and not self._otp_recently_verified())
        return self._render('santhigiri_hms.patient_portal_password',
                            patient, 'profile', error=error,
                            has_password=has_password, need_old=need_old,
                            otp_expired=otp_expired,
                            must_set=bool(request.session.get(
                                SESSION_MUST_SET_PASSWORD)))

    @http.route('/patient/password', type='http', auth='public',
                website=True, methods=['POST'], sitemap=False)
    def portal_password_submit(self, old_password=None, new_password=None,
                               confirm_password=None, **kw):
        patient = self._current_patient()
        if not patient:
            return self._require_login()
        user = patient._portal_user()
        has_password = patient._portal_has_password()
        need_old = has_password and not self._otp_recently_verified()

        if (not has_password and not request.session.uid
                and not self._otp_recently_verified()):
            # OTP session older than the window: prove identity again
            return self._render_password(patient, error=_(
                'For your security, please log in again with a one-time '
                'code before setting a password.'))
        if need_old:
            try:
                request.env['res.users'].sudo().browse(user.id)._check_credentials(
                    {'login': user.login, 'password': old_password or '',
                     'type': 'password'}, {'interactive': True})
            except AccessDenied:
                return self._render_password(
                    patient, error=_('Your current password is incorrect.'))
        if not new_password or new_password != confirm_password:
            return self._render_password(
                patient, error=_('The two new passwords do not match.'))
        try:
            user = patient._portal_set_password(new_password)
        except (UserError, ValidationError) as err:
            return self._render_password(patient, error=err.args[0])

        # Changing the password invalidates the current session token, so
        # log in again with the new password (also turns an OTP session
        # into a normal password session).
        try:
            self._authenticate_user(user, new_password)
        except AccessDenied:
            self._logout_session()
            self._flash('success', _('Password saved. Please log in.'))
            return request.redirect('/patient/login')
        request.session.pop(SESSION_OTP_VERIFIED_AT, None)
        patient.message_post(
            body=_('Patient portal password %s by the patient.',
                   _('changed') if need_old else _('created')),
            message_type='comment', subtype_xmlid='mail.mt_note')
        self._flash('success', _('Your password has been saved. From now on '
                                 'you can log in with Patient ID %s and this '
                                 'password.', patient.patient_seq))
        return request.redirect('/patient')

    @http.route('/patient/logout', type='http', auth='public', website=True,
                sitemap=False)
    def portal_logout(self, **kw):
        self._logout_session()
        request.session.should_rotate = True
        self._flash('success', _('You have been logged out.'))
        return request.redirect('/patient/login')

    # ════════════════════════════════════════════════════════════════════
    #  Dashboard
    # ════════════════════════════════════════════════════════════════════
    @http.route('/patient', type='http', auth='public', website=True,
                sitemap=False)
    def portal_dashboard(self, **kw):
        patient = self._current_patient()
        if not patient:
            return self._require_login()
        env = request.env
        today = portal_local_now(env).date()

        upcoming = env['hospital.outpatient'].sudo().search(
            self._own_domain('hospital.outpatient', patient) + [
                ('op_date', '>=', today), ('state', 'in', ('draft', 'op'))],
            order='op_date asc, slot asc', limit=5)
        admission = env['hospital.inpatient'].sudo().search(
            self._own_domain('hospital.inpatient', patient) + [
                ('state', 'in', ('reserve', 'admit'))], limit=1)
        followups = env['hospital.followup'].sudo().search(
            self._own_domain('hospital.followup', patient) + [
                ('status', 'in', ('pending', 'rescheduled'))],
            order='followup_date asc', limit=5)
        lab_tests = env['patient.lab.test'].sudo().search(
            self._own_domain('patient.lab.test', patient),
            order='date desc, id desc', limit=5)
        procedures = env['hospital.procedure.prescription'].sudo().search(
            self._own_domain('hospital.procedure.prescription', patient) + [
                ('state', 'in', ('confirmed', 'in_progress'))])
        invoices = env['account.move'].sudo().search(
            self._own_domain('account.move', patient)
            + self._invoice_domain()
            + [('move_type', '=', 'out_invoice'),
               ('payment_state', 'not in', ('paid', 'in_payment', 'reversed'))])
        return self._render(
            'santhigiri_hms.patient_portal_dashboard', patient, 'home',
            upcoming=upcoming, admission=admission, followups=followups,
            lab_tests=lab_tests, procedures=procedures,
            amount_due=sum(invoices.mapped('amount_residual')),
            currency=patient.currency_id or env.company.currency_id,
        )

    # ════════════════════════════════════════════════════════════════════
    #  Appointments (OP visits)
    # ════════════════════════════════════════════════════════════════════
    @http.route('/patient/appointments', type='http', auth='public',
                website=True, sitemap=False)
    def portal_appointments(self, **kw):
        patient = self._current_patient()
        if not patient:
            return self._require_login()
        today = portal_local_now(request.env).date()
        visits = request.env['hospital.outpatient'].sudo().search(
            self._own_domain('hospital.outpatient', patient),
            order='op_date desc, id desc')
        upcoming = visits.filtered(
            lambda v: v.op_date and v.op_date >= today
            and v.state in ('draft', 'op')).sorted(lambda v: (v.op_date, v.slot))
        past = visits - upcoming
        return self._render('santhigiri_hms.patient_portal_appointments',
                            patient, 'appointments',
                            upcoming=upcoming, past=past)

    @http.route('/patient/appointments/<int:op_id>', type='http',
                auth='public', website=True, sitemap=False)
    def portal_appointment_detail(self, op_id, **kw):
        patient = self._current_patient()
        if not patient:
            return self._require_login()
        visit = self._own('hospital.outpatient', op_id, patient)
        if not visit:
            return request.not_found()
        return self._render('santhigiri_hms.patient_portal_appointment_detail',
                            patient, 'appointments', visit=visit)

    @http.route('/patient/appointments/<int:op_id>/prescription',
                type='http', auth='public', website=True, sitemap=False)
    def portal_appointment_prescription(self, op_id, **kw):
        patient = self._current_patient()
        if not patient:
            return self._require_login()
        visit = self._own('hospital.outpatient', op_id, patient)
        if not visit or not visit.prescription_ids:
            return request.not_found()
        response = self._render_pdf(
            'santhigiri_hms.action_report_portal_op_prescription', visit,
            'Prescription_%s.pdf' % (visit.op_reference or visit.id))
        if response is None:
            self._flash('danger', _('The prescription could not be '
                                    'generated right now. Please try '
                                    'again later.'))
            return request.redirect('/patient/appointments/%s' % visit.id)
        return response

    @http.route('/patient/appointments/<int:op_id>/cancel', type='http',
                auth='public', website=True, methods=['POST'], sitemap=False)
    def portal_appointment_cancel(self, op_id, **kw):
        patient = self._current_patient()
        if not patient:
            return self._require_login()
        visit = self._own('hospital.outpatient', op_id, patient)
        if not visit:
            return request.not_found()
        if not visit._portal_can_cancel():
            self._flash('danger', _('This appointment can no longer be '
                                    'cancelled online. Please contact the '
                                    'reception.'))
        else:
            visit.action_op_cancel()
            visit.message_post(
                body=_('Appointment cancelled by the patient via the '
                       'patient portal.'),
                message_type='comment', subtype_xmlid='mail.mt_note')
            self._flash('success', _('Appointment %s has been cancelled.',
                                     visit.op_reference))
        return request.redirect('/patient/appointments')

    # ════════════════════════════════════════════════════════════════════
    #  Booking — not in the portal; the website booking page is used
    # ════════════════════════════════════════════════════════════════════
    @http.route('/patient/book', type='http', auth='public', website=True,
                sitemap=False)
    def portal_book(self, **kw):
        """Old links / bookmarks to the portal booking page go to the
        website booking page (controllers/portal.py)."""
        return request.redirect('/santhigiri/book')

    # ════════════════════════════════════════════════════════════════════
    #  Lab
    # ════════════════════════════════════════════════════════════════════
    @http.route('/patient/lab', type='http', auth='public', website=True,
                sitemap=False)
    def portal_lab(self, **kw):
        patient = self._current_patient()
        if not patient:
            return self._require_login()
        tests = request.env['patient.lab.test'].sudo().search(
            self._own_domain('patient.lab.test', patient),
            order='date desc, id desc')
        return self._render('santhigiri_hms.patient_portal_lab', patient,
                            'lab', tests=tests)

    @http.route('/patient/lab/<int:test_id>', type='http', auth='public',
                website=True, sitemap=False)
    def portal_lab_detail(self, test_id, **kw):
        patient = self._current_patient()
        if not patient:
            return self._require_login()
        test = self._own('patient.lab.test', test_id, patient)
        if not test:
            return request.not_found()
        return self._render('santhigiri_hms.patient_portal_lab_detail',
                            patient, 'lab', test=test)

    @http.route('/patient/lab/result/<int:result_id>/download', type='http',
                auth='public', website=True, sitemap=False)
    def portal_lab_result_download(self, result_id, **kw):
        patient = self._current_patient()
        if not patient:
            return self._require_login()
        result = request.env['lab.test.result'].sudo().search([
            ('id', '=', result_id),
            ('parent_id.patient_id', '=', patient.id),
        ], limit=1)
        if not result or not result.attachment:
            return request.not_found()
        content = base64.b64decode(result.attachment)
        mimetype = guess_mimetype(content, default='application/octet-stream')
        extension = {
            'application/pdf': '.pdf', 'image/png': '.png',
            'image/jpeg': '.jpg',
        }.get(mimetype, '')
        filename = 'Lab_Result_%s%s' % (
            (result.test_id.name or result.id), extension)
        return request.make_response(content, headers=[
            ('Content-Type', mimetype),
            ('Content-Length', len(content)),
            ('Content-Disposition', content_disposition(filename)),
            ('Cache-Control', 'no-store'),
        ])

    # ════════════════════════════════════════════════════════════════════
    #  Admissions (IP)
    # ════════════════════════════════════════════════════════════════════
    @http.route('/patient/admissions', type='http', auth='public',
                website=True, sitemap=False)
    def portal_admissions(self, **kw):
        patient = self._current_patient()
        if not patient:
            return self._require_login()
        admissions = request.env['hospital.inpatient'].sudo().search(
            self._own_domain('hospital.inpatient', patient) + [
                ('state', '!=', 'draft')],
            order='hosp_date desc, id desc')
        return self._render('santhigiri_hms.patient_portal_admissions',
                            patient, 'admissions', admissions=admissions)

    @http.route('/patient/admissions/<int:ip_id>', type='http',
                auth='public', website=True, sitemap=False)
    def portal_admission_detail(self, ip_id, **kw):
        patient = self._current_patient()
        if not patient:
            return self._require_login()
        admission = self._own('hospital.inpatient', ip_id, patient,
                              [('state', '!=', 'draft')])
        if not admission:
            return request.not_found()
        return self._render('santhigiri_hms.patient_portal_admission_detail',
                            patient, 'admissions', admission=admission)

    '''@http.route('/patient/admissions/<int:ip_id>/discharge-summary',
                type='http', auth='public', website=True, sitemap=False)
    def portal_discharge_summary(self, ip_id, **kw):
        patient = self._current_patient()
        if not patient:
            return self._require_login()
        admission = self._own('hospital.inpatient', ip_id, patient,
                              [('state', 'in', ('dis', 'invoice'))])
        if not admission:
            return request.not_found()
        response = self._render_pdf(
            'santhigiri_hms.action_report_discharge_summary', admission,
            'Discharge_Summary_%s.pdf' % (admission.name or admission.id))
        if response is None:
            self._flash('danger', _('The discharge summary could not be '
                                    'generated right now.'))
            return request.redirect('/patient/admissions/%s' % admission.id)
        return response'''

    # ════════════════════════════════════════════════════════════════════
    #  Procedures & follow-ups
    # ════════════════════════════════════════════════════════════════════
    @http.route('/patient/procedures', type='http', auth='public',
                website=True, sitemap=False)
    def portal_procedures(self, **kw):
        patient = self._current_patient()
        if not patient:
            return self._require_login()
        courses = request.env['hospital.procedure.prescription'].sudo().search(
            self._own_domain('hospital.procedure.prescription', patient) + [
                ('state', '!=', 'draft')],
            order='start_date desc, id desc')
        return self._render('santhigiri_hms.patient_portal_procedures',
                            patient, 'procedures', courses=courses)

    @http.route('/patient/followups', type='http', auth='public',
                website=True, sitemap=False)
    def portal_followups(self, **kw):
        patient = self._current_patient()
        if not patient:
            return self._require_login()
        followups = request.env['hospital.followup'].sudo().search(
            self._own_domain('hospital.followup', patient),
            order='followup_date desc, id desc')
        return self._render('santhigiri_hms.patient_portal_followups',
                            patient, 'followups', followups=followups)

    # ════════════════════════════════════════════════════════════════════
    #  Bills
    # ════════════════════════════════════════════════════════════════════
    @http.route('/patient/bills', type='http', auth='public', website=True,
                sitemap=False)
    def portal_bills(self, **kw):
        patient = self._current_patient()
        if not patient:
            return self._require_login()
        moves = request.env['account.move'].sudo().search(
            self._own_domain('account.move', patient)
            + self._invoice_domain(),
            order='invoice_date desc, id desc')
        due = moves.filtered(
            lambda m: m.move_type == 'out_invoice'
            and m.payment_state not in ('paid', 'in_payment', 'reversed'))
        return self._render(
            'santhigiri_hms.patient_portal_bills', patient, 'bills',
            moves=moves, amount_due=sum(due.mapped('amount_residual')),
            currency=patient.currency_id or request.env.company.currency_id)

    @http.route('/patient/bills/<int:move_id>/pdf', type='http',
                auth='public', website=True, sitemap=False)
    def portal_bill_pdf(self, move_id, **kw):
        patient = self._current_patient()
        if not patient:
            return self._require_login()
        move = self._own('account.move', move_id, patient,
                         self._invoice_domain())
        if not move:
            return request.not_found()
        response = self._render_pdf(
            'account.account_invoices', move,
            '%s.pdf' % (move.name or 'Invoice').replace('/', '_'))
        if response is None:
            self._flash('danger', _('The invoice could not be generated '
                                    'right now.'))
            return request.redirect('/patient/bills')
        return response

    # ════════════════════════════════════════════════════════════════════
    #  Profile & ID card
    # ════════════════════════════════════════════════════════════════════
    @http.route('/patient/profile', type='http', auth='public', website=True,
                methods=['GET'], sitemap=False)
    def portal_profile(self, **kw):
        """Read-only profile: registered details, ID card, login & security.
        Patients cannot edit their details online; changes are made at the
        reception."""
        patient = self._current_patient()
        if not patient:
            return self._require_login()
        return self._render('santhigiri_hms.patient_portal_profile',
                            patient, 'profile')

    @http.route('/patient/card', type='http', auth='public', website=True,
                sitemap=False)
    def portal_patient_card(self, **kw):
        patient = self._current_patient()
        if not patient:
            return self._require_login()
        response = self._render_pdf(
            'base_hospital_management.action_report_patient_card', patient,
            'Patient_Card_%s.pdf' % (patient.patient_seq or patient.id))
        if response is None:
            self._flash('danger', _('The patient card could not be '
                                    'generated right now.'))
            return request.redirect('/patient/profile')
        return response