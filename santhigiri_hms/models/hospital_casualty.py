# -*- coding: utf-8 -*-
"""
Casualty Registration — completely new model.
BASE MODULE has no casualty module whatsoever.
Covers FRD sections 12.1–12.7: Registration, RMO assessment, intern assignment,
4-outcome workflow, referral letter, ambulance, casualty bill.
"""
from odoo import api, fields, models
from odoo.exceptions import UserError


class HospitalCasualty(models.Model):
    _name = 'hospital.casualty'
    _description = 'Casualty Registration'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'registration_datetime desc'
    _rec_name = 'casualty_reference'

    # ── Reference ─────────────────────────────────────────────────────────────
    casualty_reference = fields.Char(
        string='Casualty Reference',
        readonly=True,
        default='New',
        copy=False,
        tracking=True,
    )

    # ── Patient ───────────────────────────────────────────────────────────────
    patient_id = fields.Many2one(
        'res.partner',
        string='Patient',
        required=True,
        domain=[('patient_seq', '!=', False)],
        tracking=True,
    )
    patient_seq = fields.Char(related='patient_id.patient_seq', store=True, string='Patient No.')
    blood_group = fields.Selection(related='patient_id.blood_group', store=True)
    allergy_summary = fields.Char(related='patient_id.allergy_summary', store=True)
    has_allergy = fields.Boolean(related='patient_id.has_allergy', store=True)

    # ── Registration ──────────────────────────────────────────────────────────
    registration_datetime = fields.Datetime(
        string='Registration Date & Time',
        default=fields.Datetime.now,
        required=True,
    )
    chief_complaint = fields.Text(string='Chief Complaint', required=True)
    referred_by = fields.Char(string='Referred By (if applicable)')
    token_no = fields.Char(string='Token Number', readonly=True)

    # ── RMO ───────────────────────────────────────────────────────────────────
    rmo_id = fields.Many2one(
        'hr.employee',
        string='RMO On Duty',
        domain=[('is_rmo', '=', True)],
        required=True,
        tracking=True,
    )

    # ── Vitals ────────────────────────────────────────────────────────────────
    bp = fields.Char(string='Blood Pressure (BP)', help='e.g. 120/80 mmHg')
    temperature = fields.Float(string='Temperature (°F)')
    pulse = fields.Integer(string='Pulse (bpm)')
    respiratory_rate = fields.Integer(string='Respiratory Rate (breaths/min)')
    spo2 = fields.Float(string='SpO2 (%)')

    # ── Clinical Assessment ────────────────────────────────────────────────────
    clinical_history = fields.Text(string='Clinical History')
    examination_findings = fields.Text(string='Examination Findings')
    provisional_diagnosis = fields.Text(string='Provisional Diagnosis')
    special_instructions = fields.Text(string='Special Instructions')

    # ── Prescription (medicines prescribed by RMO) ───────────────────────────
    prescription_ids = fields.One2many(
        'prescription.line',
        'casualty_id',
        string='Medicines Prescribed',
    )

    # ── Interns ───────────────────────────────────────────────────────────────
    intern_ids = fields.Many2many(
        'hospital.intern',
        'casualty_intern_rel',
        'casualty_id',
        'intern_id',
        string='Attending Interns',
    )

    # ── Outcome ───────────────────────────────────────────────────────────────
    outcome = fields.Selection([
        ('pending', 'Pending Decision'),
        ('discharge', 'Treat & Discharge'),
        ('observation', 'Under Observation'),
        ('inpatient', 'IP Admission'),
        ('referral', 'Referral to External Facility'),
    ], string='Outcome', default='pending', tracking=True, required=True)

    state = fields.Selection([
        ('registered', 'Registered'),
        ('under_treatment', 'Under Treatment'),
        ('observation', 'Under Observation'),
        ('discharged', 'Discharged'),
        ('admitted', 'Admitted to IP'),
        ('referred', 'Referred'),
    ], string='Status', default='registered', tracking=True)

    # ── Referral Details ──────────────────────────────────────────────────────
    referral_hospital = fields.Char(string='Referred To (Hospital / Facility)')
    referral_reason = fields.Text(string='Reason for Referral')
    ambulance_no = fields.Char(string='Ambulance Number / Mode of Transfer')
    accompanying_staff_id = fields.Many2one(
        'hr.employee',
        string='Accompanying Doctor / Staff',
    )
    departure_datetime = fields.Datetime(string='Departure Date & Time')

    # ── Billing ───────────────────────────────────────────────────────────────
    casualty_fee = fields.Monetary(
        string='Casualty Consultation Fee',
        currency_field='currency_id',
        help='Configurable — can be zero or a fixed amount',
    )
    currency_id = fields.Many2one('res.currency',
                                   default=lambda s: s.env.company.currency_id)
    invoice_id = fields.Many2one('account.move', string='Casualty Invoice', readonly=True)

    # ── Link to IP Admission ───────────────────────────────────────────────────
    inpatient_id = fields.Many2one('hospital.inpatient', string='IP Admission', readonly=True)

    # ── Create with sequence ───────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('casualty_reference', 'New') == 'New':
                vals['casualty_reference'] = self.env['ir.sequence'].next_by_code(
                    'hospital.casualty'
                ) or 'CAS/001'
            if not vals.get('token_no'):
                vals['token_no'] = self.env['ir.sequence'].next_by_code(
                    'casualty.token'
                ) or 'T001'
        records = super().create(vals_list)
        # Auto-log case for each attending intern
        for rec in records:
            rec._log_intern_case()
        return records

    def write(self, vals):
        res = super().write(vals)
        if vals.get('intern_ids'):
            for rec in self:
                rec._log_intern_case()
        return res

    def _log_intern_case(self):
        CaseLog = self.env['hospital.case.log']
        for intern in self.intern_ids:
            existing = CaseLog.search([
                ('intern_id', '=', intern.id),
                ('source', '=', 'casualty'),
                ('casualty_id', '=', self.id),
            ], limit=1)
            if not existing:
                CaseLog.create({
                    'intern_id': intern.id,
                    'date': self.registration_datetime.date() if self.registration_datetime else fields.Date.today(),
                    'source': 'casualty',
                    'casualty_id': self.id,
                    'case_type': 'general',
                    'exposure_type': 'assisted',
                    'summary': f'Casualty case: {self.casualty_reference} — {self.chief_complaint or ""}',
                })

    # ── Outcome Action Buttons ────────────────────────────────────────────────
    def action_treat_and_discharge(self):
        self.ensure_one()
        self.outcome = 'discharge'
        self.state = 'discharged'
        return self._create_casualty_invoice()

    def action_under_observation(self):
        self.ensure_one()
        self.outcome = 'observation'
        self.state = 'observation'

    def action_admit_inpatient(self):
        """Convert casualty to IP admission."""
        self.ensure_one()
        self.outcome = 'inpatient'
        self.state = 'admitted'
        return {
            'name': 'IP Admission',
            'type': 'ir.actions.act_window',
            'res_model': 'hospital.inpatient',
            'view_mode': 'form',
            'context': {
                'default_patient_id': self.patient_id.id,
                'default_reason': self.provisional_diagnosis or self.chief_complaint,
                'default_source_casualty_id': self.id,
            },
        }

    def action_referral(self):
        """Mark as referred — referral letter to be printed separately."""
        self.ensure_one()
        if not self.referral_hospital:
            raise UserError('Please enter the name of the referred hospital/facility.')
        self.outcome = 'referral'
        self.state = 'referred'

    def action_create_invoice(self):
        """
        Manual invoice creation — available for ALL outcomes.
        Referral patients: billed for consultation + medicines given before referral.
        Observation patients: billed when they leave.
        Discharge patients: auto-billed, but this handles if auto failed.
        """
        self.ensure_one()
        return self._create_casualty_invoice()

    def action_view_invoice(self):
        """Open the existing invoice."""
        self.ensure_one()
        if not self.invoice_id:
            raise UserError('No invoice found for this casualty case.')
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
        }

    def action_print_referral_letter(self):
        self.ensure_one()
        if self.outcome != 'referral':
            raise UserError('Please select Referral outcome before printing the referral letter.')
        return self.env.ref('santhigiri_hms.action_report_referral_letter').report_action(self)

    def _create_casualty_invoice(self):
        """Create casualty bill: consultation fee + medicines + procedures + lab."""
        self.ensure_one()
        if self.invoice_id:
            return {'type': 'ir.actions.act_window',
                    'res_model': 'account.move', 'res_id': self.invoice_id.id,
                    'view_mode': 'form'}
        lines = []
        if self.casualty_fee:
            lines.append((0, 0, {
                'name': f'Casualty Consultation Fee — {self.casualty_reference}',
                'quantity': 1, 'price_unit': self.casualty_fee,
            }))
        for med in self.prescription_ids:
            price = med.medicine_id.list_price if med.medicine_id else 0
            if price:
                lines.append((0, 0, {
                    'name': f'Medicine: {med.medicine_id.name}',
                    'quantity': med.quantity, 'price_unit': price,
                }))
        if not lines:
            raise UserError('No chargeable items. Add consultation fee or medicines first.')
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.patient_id.id,
            'invoice_date': fields.Date.today(),
            'invoice_origin': self.casualty_reference,
            'invoice_line_ids': lines,
        })
        self.invoice_id = move.id
        return {'type': 'ir.actions.act_window',
                'res_model': 'account.move', 'res_id': move.id, 'view_mode': 'form'}