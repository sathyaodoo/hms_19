# -*- coding: utf-8 -*-
"""
Hospital Appointment Model
Handles patient appointments with preferred doctor, department, date & time,
reason (Consultation, Counselling, Yoga), and confirmation status check box.
Can be converted/registered directly into OP Registration.
"""
from odoo import api, fields, models
from odoo.exceptions import UserError


class HospitalAppointment(models.Model):
    _name = 'hospital.appointment'
    _description = 'Hospital Appointment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'appointment_datetime desc, id desc'
    _rec_name = 'name'

    name = fields.Char(
        string='Appointment ID',
        readonly=True,
        default='New',
        copy=False,
    )
    patient_id = fields.Many2one(
        'res.partner',
        string='Patient',
        domain="[('patient_seq', 'not in', ['Employee', 'User'])]",
        tracking=True,
        help='Select existing patient. For new patients, enter Name and Phone below.',
    )
    patient_name = fields.Char(
        string='Patient Name',
        tracking=True,
        required=True,
        help='Name of the patient',
    )
    patient_phone = fields.Char(
        string='Phone Number',
        tracking=True,
    )
    patient_email = fields.Char(
        string='Email',
    )
    department_id = fields.Many2one(
        'hospital.department',
        string='Department Preferred',
        required=False,
        tracking=True,
        help='Preferred medical department',
    )
    doctor_id = fields.Many2one(
        'hr.employee',
        string='Doctor Preferred',
        tracking=True,
        help='Preferred doctor/consultant',
    )
    appointment_datetime = fields.Datetime(
        string='Date and Time',
        default=fields.Datetime.now,
        required=True,
        tracking=True,
        help='Scheduled appointment date and time',
    )
    appointment_reason = fields.Selection(
        selection=[
            ('consultation', 'Consultation'),
            ('counselling', 'Counselling'),
            ('yoga', 'Yoga'),
        ],
        string='Reason for Appointment',
        required=True,
        default='consultation',
        tracking=True,
        help='Reason for booking this appointment',
    )
    is_confirmed = fields.Boolean(
        string='Confirmation Status',
        default=False,
        tracking=True,
        help='Check box indicating whether this appointment is confirmed with patient/doctor',
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Pending'),
            ('confirmed', 'Confirmed'),
            ('registered', 'Registered in OP'),
            ('cancel', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        tracking=True,
    )
    notes = fields.Text(
        string='Notes / Reason Details',
    )
    outpatient_id = fields.Many2one(
        'hospital.outpatient',
        string='Linked OP Registration',
        readonly=True,
        copy=False,
        help='OP Registration created from this appointment',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Hospital',
        default=lambda self: self.env.company,
    )

    @api.onchange('patient_id')
    def _onchange_patient_id(self):
        if self.patient_id:
            self.patient_name = self.patient_id.name or ''
            self.patient_phone = self.patient_id.phone or getattr(self.patient_id, 'mobile', '') or ''
            self.patient_email = self.patient_id.email or ''

    @api.onchange('doctor_id')
    def _onchange_doctor_id(self):
        if self.doctor_id and not self.department_id:
            dept = self.env['hospital.department'].search([('member_ids', 'in', self.doctor_id.id)], limit=1)
            if dept:
                self.department_id = dept

    @api.onchange('is_confirmed')
    def _onchange_is_confirmed(self):
        if self.is_confirmed and self.state == 'draft':
            self.state = 'confirmed'
        elif not self.is_confirmed and self.state == 'confirmed':
            self.state = 'draft'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('hospital.appointment') or 'APT/0001'
            if vals.get('is_confirmed') and vals.get('state') == 'draft':
                vals['state'] = 'confirmed'
        return super().create(vals_list)

    def write(self, vals):
        if 'is_confirmed' in vals:
            if vals['is_confirmed'] and self.state == 'draft':
                vals['state'] = 'confirmed'
            elif not vals['is_confirmed'] and self.state == 'confirmed':
                vals['state'] = 'draft'
        return super().write(vals)

    def action_confirm(self):
        """Confirm appointment and set checkbox"""
        for rec in self:
            rec.is_confirmed = True
            rec.state = 'confirmed'

    def action_cancel(self):
        """Cancel appointment"""
        for rec in self:
            rec.is_confirmed = False
            rec.state = 'cancel'

    def action_reset_draft(self):
        """Reset appointment to draft"""
        for rec in self:
            rec.is_confirmed = False
            rec.state = 'draft'

    def action_create_op_registration(self):
        """
        Proceed to Registration: Converts this appointment into an OP Registration.
        Pre-populates patient, preferred doctor, preferred department, reason, and date.
        """
        self.ensure_one()
        if self.outpatient_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'OP Registration',
                'res_model': 'hospital.outpatient',
                'res_id': self.outpatient_id.id,
                'view_mode': 'form',
                'target': 'current',
            }

        # Ensure patient partner exists
        partner = self.patient_id
        if not partner:
            partner = self.env['res.partner'].create({
                'name': self.patient_name,
                'phone': self.patient_phone,
                'email': self.patient_email,
                'patient_category': 'jeevanam',
            })
            self.patient_id = partner.id

        # Find or use doctor allocation if available
        today = fields.Date.today()
        allocation = False
        if self.doctor_id:
            allocation = self.env['doctor.allocation'].search([
                ('doctor_id', '=', self.doctor_id.id),
                ('date', '=', today),
                ('state', '=', 'confirm'),
            ], limit=1)
        if not allocation and self.department_id:
            allocation = self.env['doctor.allocation'].search([
                ('department_id', '=', self.department_id.id),
                ('date', '=', today),
                ('state', '=', 'confirm'),
            ], limit=1)
        if not allocation:
            allocation = self.env['doctor.allocation'].search([
                ('date', '=', today),
                ('state', '=', 'confirm'),
            ], limit=1)
        if not allocation:
            # Fallback to any active doctor allocation to satisfy base requirement
            allocation = self.env['doctor.allocation'].search([], limit=1)

        reason_label = dict(self._fields['appointment_reason'].selection).get(
            self.appointment_reason, self.appointment_reason
        )
        full_reason = f'{reason_label}' + (f': {self.notes}' if self.notes else '')

        doctor_dept = (
            self.env['hospital.department'].search([('member_ids', 'in', self.doctor_id.id)], limit=1).id
            if self.doctor_id else False
        )
        fallback_dept = (
            self.department_id.id if self.department_id
            else (allocation.department_id.id if allocation and allocation.department_id
                  else (doctor_dept or self.env['hospital.department'].search([], limit=1).id))
        )

        op_vals = {
            'patient_id': partner.id,
            'department_id': fallback_dept,
            'doctor_id': allocation.id if allocation else False,
            'op_date': today,
            'registration_datetime': self.appointment_datetime or fields.Datetime.now(),
            'reason': full_reason,
            'appointment_id': self.id,
            'appointment_reason': self.appointment_reason,
            'patient_category': partner.patient_category or 'jeevanam',
            'claim': partner.claim or 'no',
            'referred_by': partner.referred_by or '',
        }
        op = self.env['hospital.outpatient'].create(op_vals)

        self.write({
            'state': 'registered',
            'is_confirmed': True,
            'outpatient_id': op.id,
        })

        return {
            'type': 'ir.actions.act_window',
            'name': 'OP Registration',
            'res_model': 'hospital.outpatient',
            'res_id': op.id,
            'view_mode': 'form',
            'target': 'current',
        }
