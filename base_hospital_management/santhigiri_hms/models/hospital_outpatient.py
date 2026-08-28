# -*- coding: utf-8 -*-
"""
hospital.outpatient extensions.
BASE MODULE already handles:
  op_reference, patient_id, doctor_id (→ doctor.allocation), op_date, reason,
  state (draft/op/inpatient/invoice/cancel), prescription_ids, test_ids, invoice_id,
  create_invoice(), action_convert_to_inpatient(), action_confirm(), action_print_prescription().
THIS FILE ADDS:
  patient_category field, category-based fee lookup, 3-outcome routing
  (Regular OP / Daily Procedures / IP Admission), observer_intern_ids.
"""
from odoo import api, fields, models
from odoo.exceptions import UserError


class HospitalOutpatient(models.Model):
    _inherit = 'hospital.outpatient'

    # ── Category & Fee ─────────────────────────────────────────────────────────
    camp_id = fields.Many2one(
        'hospital.camp',
        string='Medical Camp',
        domain=[('state', '=', 'active')],
        help='Link this OP visit to a Medical Camp for auto-discount billing.',
    )

    # §9.5 Referral Management
    is_referred = fields.Boolean(string='Referred Patient', default=False)
    referred_by = fields.Char(string='Referred By (Doctor Name)')
    referring_hospital = fields.Char(string='Referring Hospital / Clinic')
    referral_date = fields.Date(string='Referral Date')
    referral_reason = fields.Text(string='Reason for Referral')
    referral_document_ids = fields.Many2many(
        'ir.attachment',
        'op_referral_doc_rel',
        'op_id', 'attachment_id',
        string='Referral Letter / Documents',
    )

    patient_category = fields.Selection([
        ('general', 'General'),
        ('vip', 'VIP'),
        ('senior_citizen', 'Senior Citizen'),
        ('bpl', 'BPL / Karunyam'),
        ('payward', 'Pay Ward'),
        ('ardram', 'Ardram'),
        ('jeevanam', 'Jeevanam'),
    ], string='Patient Category', default='general', required=True)

    category_fee = fields.Monetary(
        string='Consultation Fee (Category)',
        compute='_compute_category_fee',
        store=True,
        currency_field='currency_id',
        help='Auto-fetched from fee master based on category',
    )
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda s: s.env.company.currency_id,
    )

    # ── Outcome / Routing ─────────────────────────────────────────────────────
    outcome = fields.Selection([
        ('regular', 'Regular OP (Discharged)'),
        ('procedure', 'OP + Daily Procedures'),
        ('inpatient', 'IP Admission'),
    ], string='Consultation Outcome', tracking=True)

    procedure_prescription_ids = fields.One2many(
        'hospital.procedure.prescription',
        'outpatient_id',
        string='Procedure Prescriptions',
    )

    # ── Interns observing this consultation ───────────────────────────────────
    observer_intern_ids = fields.Many2many(
        'hospital.intern',
        'op_intern_observer_rel',
        'op_id',
        'intern_id',
        string='Observing Interns',
    )

    # ── Follow-up ─────────────────────────────────────────────────────────────
    followup_date = fields.Date(string='Follow-Up Date')
    followup_notes = fields.Text(string='Follow-Up Instructions')
    followup_id = fields.Many2one('hospital.followup', string='Follow-Up Record', readonly=True)

    # ── Case Sheet Fields ─────────────────────────────────────────────────────
    chief_complaint = fields.Text(string='Chief Complaint')
    examination_findings = fields.Text(string='Examination Findings')
    provisional_diagnosis = fields.Text(string='Provisional Diagnosis')
    treatment_notes = fields.Text(string='Treatment Notes / Plan')

    # ── Computed ───────────────────────────────────────────────────────────────
    @api.depends('patient_category')
    def _compute_category_fee(self):
        FeeMaster = self.env['hospital.fee.master']
        for rec in self:
            fee_rec = FeeMaster.search([
                ('patient_category', '=', rec.patient_category),
                ('active', '=', True),
            ], limit=1)
            rec.category_fee = fee_rec.amount if fee_rec else 0.0

    # ── Override create_invoice to use category fee ───────────────────────────
    def create_invoice(self):
        """Override to use category-based consultation fee."""
        for rec in self:
            if rec.invoice_id:
                raise UserError('Invoice already created for this OP.')
            fee = rec.category_fee or 0.0
            move = self.env['account.move'].create({
                'move_type': 'out_invoice',
                'partner_id': rec.patient_id.id,
                'invoice_date': fields.Date.today(),
                'invoice_line_ids': [(0, 0, {
                    'name': f'Consultation Fee — {rec.op_reference} ({rec.get_patient_category_label()})',
                    'quantity': 1,
                    'price_unit': fee,
                })],
            })
            rec.invoice_id = move.id
            rec.state = 'invoice'
        return True

    def get_patient_category_label(self):
        self.ensure_one()
        labels = dict(self._fields['patient_category'].selection)
        return labels.get(self.patient_category, '')

    # ── 3-Outcome Routing Buttons ─────────────────────────────────────────────
    def action_outcome_regular(self):
        """Outcome 1: Regular OP — prescription routed to pharmacy."""
        self.ensure_one()
        self.outcome = 'regular'
        self.state = 'invoice'
        # Create follow-up if date set
        if self.followup_date:
            self._create_followup()
        return True

    def action_outcome_procedures(self):
        """Outcome 2: OP + Daily Procedures — opens procedure prescription wizard."""
        self.ensure_one()
        self.outcome = 'procedure'
        return {
            'name': 'Create Procedure Prescription',
            'type': 'ir.actions.act_window',
            'res_model': 'hospital.procedure.prescription',
            'view_mode': 'form',
            'context': {
                'default_outpatient_id': self.id,
                'default_patient_id': self.patient_id.id,
            },
            'target': 'new',
        }

    def action_outcome_inpatient(self):
        """Outcome 3: IP Admission — create IP record and open form."""
        self.ensure_one()
        self.outcome = 'inpatient'
        self.state = 'inpatient'

        # Create IP record directly
        ip = self.env['hospital.inpatient'].sudo().create({
            'patient_id': self.patient_id.id,
            'reason': self.reason or self.chief_complaint or '',
            'attending_doctor_id': self.doctor_id.id if self.doctor_id else False,
            'type_admission': 'routine',
        })

        return {
            'type': 'ir.actions.act_window',
            'name': 'IP Admission',
            'res_model': 'hospital.inpatient',
            'res_id': ip.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _create_followup(self):
        """Create a follow-up record after OP consultation."""
        self.ensure_one()
        followup = self.env['hospital.followup'].create({
            'patient_id': self.patient_id.id,
            'followup_date': self.followup_date,
            'reason': f'Post OP follow-up ({self.op_reference})',
            'advised_by': self.env.user.employee_id.id if hasattr(self.env.user, 'employee_id') else False,
            'source_op_id': self.id,
        })
        self.followup_id = followup.id

    # ── Auto-log intern observation ────────────────────────────────────────────
    def write(self, vals):
        res = super().write(vals)
        if vals.get('observer_intern_ids'):
            for rec in self:
                for intern in rec.observer_intern_ids:
                    self.env['hospital.case.log'].create({
                        'intern_id': intern.id,
                        'date': rec.op_date or fields.Date.today(),
                        'source': 'op_observation',
                        'case_type': 'general',
                        'exposure_type': 'observed',
                        'summary': f'OP observation: {rec.op_reference} — {rec.provisional_diagnosis or rec.reason or ""}',
                    })
        return res