# -*- coding: utf-8 -*-
import random
import string
from datetime import datetime, timedelta

from odoo import fields, http
from odoo.http import request

from odoo.addons.base_hospital_management.controllers.patient_booking import (
    PatientBooking,
)


class SanthigiriPatientBooking(PatientBooking):
    """Inherits base controller — redirects /patient_booking to our OTP portal."""

    @http.route('/patient_booking', type='http', auth='public', website=True)
    def patient_booking(self, **kw):
        return request.redirect('/santhigiri/book')


class SanthigiriOTPPortal(http.Controller):

    def _send_otp_sms(self, phone, otp):
        """
        Add your SMS gateway here.
        MSG91: requests.post('https://api.msg91.com/api/v5/otp', json={...})
        """
        pass  # TODO: SMS gateway

    @http.route('/santhigiri/book', type='http', auth='public', website=True)
    def portal_booking_home(self, **kw):
        return request.render('santhigiri_hms.portal_booking_home', {
            'error': kw.get('error'),
            'success': kw.get('success'),
        })

    @http.route('/santhigiri/book/send_otp', type='http', auth='public',
                website=True, methods=['POST'], csrf=True)
    def portal_send_otp(self, patient_id=None, **kw):
        if not patient_id or not patient_id.strip():
            return request.redirect(
                '/santhigiri/book?error=Please enter your Patient ID.')

        # Search by patient_seq field
        patient = request.env['res.partner'].sudo().search(
            [('patient_seq', '=', patient_id.strip())], limit=1)

        if not patient:
            return request.redirect(
                '/santhigiri/book?error=Patient ID not found. '
                'Please check your ID card or visit reception.')

        # If same patient already has a valid OTP in session, reuse it (prevent double log)
        existing_otp = request.session.get('booking_otp')
        existing_pid = request.session.get('booking_patient_id')
        if existing_otp and existing_pid == patient.id:
            # OTP already generated for this patient — just show OTP page again
            otp = existing_otp
        else:
            # Generate new OTP
            otp = ''.join(random.choices(string.digits, k=6))
            request.session['booking_otp'] = otp
            request.session['booking_patient_id'] = patient.id
            request.session['booking_otp_created'] = datetime.now().isoformat()
            # Log OTP (only once)
            patient.sudo().message_post(
                body=f'OTP for portal booking: {otp} (valid 10 minutes)',
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )

        # Send SMS only if phone exists
        phone = getattr(patient, 'phone', None) or ''
        if phone:
            self._send_otp_sms(phone, otp)
        phone_masked = phone[-4:] if len(phone) >= 4 else ''

        return request.render('santhigiri_hms.portal_booking_otp', {
            'patient_name': patient.name,
            'patient_phone': phone_masked,
            'phone_registered': bool(phone),
        })

    @http.route('/santhigiri/book/verify_otp', type='http', auth='public',
                website=True, methods=['POST'], csrf=True)
    def portal_verify_otp(self, otp=None, **kw):
        stored_otp = request.session.get('booking_otp')
        patient_id = request.session.get('booking_patient_id')
        otp_created = request.session.get('booking_otp_created')

        if not stored_otp or not patient_id:
            return request.redirect(
                '/santhigiri/book?error=Session expired. Please start again.')

        # Expiry check
        if otp_created:
            try:
                created_dt = datetime.fromisoformat(otp_created)
                if (datetime.now() - created_dt).total_seconds() > 600:
                    for k in ('booking_otp', 'booking_patient_id',
                              'booking_otp_created'):
                        request.session.pop(k, None)
                    return request.redirect(
                        '/santhigiri/book?error=OTP expired. Please start again.')
            except (ValueError, TypeError):
                pass

        # Wrong OTP
        if not otp or otp.strip() != stored_otp:
            patient = request.env['res.partner'].sudo().browse(patient_id)
            phone = getattr(patient, 'phone', '') or '' if patient.exists() else ''
            return request.render('santhigiri_hms.portal_booking_otp', {
                'error': 'Incorrect OTP. Please try again.',
                'patient_name': patient.name if patient.exists() else '',
                'patient_phone': phone[-4:] if len(phone) >= 4 else '',
                'phone_registered': bool(phone),
            })

        patient = request.env['res.partner'].sudo().browse(patient_id)
        if not patient.exists():
            return request.redirect('/santhigiri/book?error=Patient not found.')

        request.session.pop('booking_otp', None)
        request.session.pop('booking_otp_created', None)

        today = fields.Date.today()
        allocations = request.env['doctor.allocation'].sudo().search([
            ('date', '>=', today),
            ('date', '<=', today + timedelta(days=7)),
            ('state', '=', 'confirm'),
            ('slot_remaining', '>', 0),
        ], order='date asc, work_from asc')

        return request.render('santhigiri_hms.portal_booking_slots', {
            'patient': patient,
            'allocations': allocations,
        })

    @http.route('/santhigiri/book/confirm', type='http', auth='public',
                website=True, methods=['POST'], csrf=True)
    def portal_confirm_booking(self, allocation_id=None, **kw):
        patient_id = request.session.get('booking_patient_id')
        if not patient_id or not allocation_id:
            return request.redirect(
                '/santhigiri/book?error=Invalid request. Please start again.')

        patient = request.env['res.partner'].sudo().browse(int(patient_id))
        if not patient.exists():
            return request.redirect('/santhigiri/book?error=Patient not found.')

        try:
            allocation = request.env['doctor.allocation'].sudo().browse(
                int(allocation_id))
        except (ValueError, TypeError):
            return request.redirect('/santhigiri/book?error=Invalid slot.')

        if not allocation.exists() or allocation.slot_remaining <= 0:
            return request.redirect(
                '/santhigiri/book?error=Slot no longer available. '
                'Please select another.')

        try:
            op = request.env['hospital.outpatient'].sudo().create({
                'patient_id': patient.id,
                'doctor_id': allocation.id,
                'op_date': allocation.date,
                'reason': 'Online appointment — patient portal',
                'patient_category': 'general',
            })
            op.sudo().action_confirm()
        except Exception:
            return request.redirect(
                '/santhigiri/book?error=Booking failed. '
                'Please call the hospital or visit reception.')

        request.session.pop('booking_patient_id', None)

        # Email confirmation
        email = getattr(patient, 'email', None) or ''
        if email:
            try:
                request.env['mail.mail'].sudo().create({
                    'subject': f'Appointment Confirmed — {op.op_reference}',
                    'body_html': (
                        f'<p>Dear {patient.name},</p>'
                        f'<p>Your appointment is confirmed at '
                        f'<b>Santhigiri Ayurveda Hospital</b>.</p>'
                        f'<p>OP Reference: <b>{op.op_reference}</b><br/>'
                        f'Date: <b>{op.op_date}</b></p>'
                        f'<p>Please bring your Patient ID card when you visit.</p>'
                    ),
                    'email_to': email,
                }).send()
            except Exception:
                pass

        return request.render('santhigiri_hms.portal_booking_success', {
            'op': op,
            'patient': patient,
        })