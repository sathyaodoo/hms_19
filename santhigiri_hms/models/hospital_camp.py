# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HospitalCamp(models.Model):
    _name = 'hospital.camp'
    _description = 'Medical Camp'
    _inherit = ['mail.thread']
    _order = 'camp_date desc'

    name = fields.Char(string='Camp Name', required=True)
    camp_date = fields.Date(string='Camp Date', required=True)
    location = fields.Char(string='Location / Venue')
    speciality = fields.Char(string='Speciality',
                              help='e.g. General Medicine, Ayurveda, Ophthalmology, Orthopaedics')
    organiser_dept_id = fields.Many2one('hr.department', string='Organising Department')
    sponsor = fields.Char(string='Sponsoring Organisation')

    discount_type = fields.Selection([
        ('free', 'Free (100% Waiver)'),
        ('percent', 'Percentage Discount (%)'),
        ('fixed', 'Fixed Discount (₹)'),
    ], string='Discount Type', default='free', required=True)
    discount_value = fields.Float(string='Discount Value',
                                   help='% for percentage type; ₹ amount for fixed type')

    outpatient_ids = fields.One2many('hospital.outpatient', 'camp_id', string='Camp Patients')
    patient_count = fields.Integer(string='Patients Registered',
                                    compute='_compute_patient_count', store=True)

    state = fields.Selection([('planned', 'Planned'), ('active', 'Active'),
                               ('done', 'Completed'), ('cancelled', 'Cancelled')],
                              default='planned', tracking=True)
    notes = fields.Text(string='Notes / Remarks')

    @api.depends('outpatient_ids')
    def _compute_patient_count(self):
        for rec in self:
            rec.patient_count = len(rec.outpatient_ids)

    # ── Camp Report Computed Fields ───────────────────────────────────────────
    total_patients = fields.Integer(
        string='Total Patients Seen',
        compute='_compute_camp_report', store=True)
    total_value = fields.Monetary(
        string='Total Value of Services (Before Discount)',
        compute='_compute_camp_report', store=True,
        currency_field='currency_id')
    actual_revenue = fields.Monetary(
        string='Actual Revenue (After Discount)',
        compute='_compute_camp_report', store=True,
        currency_field='currency_id')
    total_discount = fields.Monetary(
        string='Total Discount Given',
        compute='_compute_camp_report', store=True,
        currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda s: s.env.company.currency_id)

    @api.depends('outpatient_ids', 'outpatient_ids.state',
                 'outpatient_ids.category_fee', 'outpatient_ids.invoice_id',
                 'discount_type', 'discount_value')
    def _compute_camp_report(self):
        for rec in self:
            ops = rec.outpatient_ids
            rec.total_patients = len(ops)
            total_val = sum(op.category_fee or 0.0 for op in ops)
            rec.total_value = total_val
            if rec.discount_type == 'free':
                rec.actual_revenue = 0.0
                rec.total_discount = total_val
            elif rec.discount_type == 'percent':
                discount = total_val * (rec.discount_value / 100)
                rec.actual_revenue = total_val - discount
                rec.total_discount = discount
            else:  # fixed
                discount = rec.discount_value * len(ops)
                rec.actual_revenue = max(0.0, total_val - discount)
                rec.total_discount = min(discount, total_val)

    def action_print_camp_report(self):
        return self.env.ref(
            'santhigiri_hms.action_report_camp').report_action(self)

    def action_activate_camp(self):
        self.state = 'active'
        self.message_post(
            body=f'Camp activated on {fields.Date.today()}',
            message_type='comment',
            subtype_xmlid='mail.mt_note',
        )

    def action_close_camp(self):
        self.state = 'done'
        self.message_post(
            body=f'Camp closed on {fields.Date.today()} — {self.patient_count} patients attended.',
            message_type='comment',
            subtype_xmlid='mail.mt_note',
        )


class HospitalOutpatientCamp(models.Model):
    """Extend hospital.outpatient with camp linkage and auto-discount billing."""
    _inherit = 'hospital.outpatient'

    camp_id = fields.Many2one('hospital.camp', string='Medical Camp',
                               help='If this OP visit is part of a medical camp')

    def create_invoice(self):
        """Override to apply camp discount if applicable."""
        if not self.camp_id:
            return super().create_invoice()
        camp = self.camp_id
        base_fee = self.category_fee or 0.0
        if camp.discount_type == 'free':
            final_fee = 0.0
        elif camp.discount_type == 'percent':
            final_fee = base_fee * (1 - (camp.discount_value / 100))
        else:
            final_fee = max(0.0, base_fee - camp.discount_value)
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.patient_id.id,
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': [(0, 0, {
                'name': (f'Consultation Fee — {self.op_reference} '
                         f'[Camp: {camp.name}]'),
                'quantity': 1,
                'price_unit': final_fee,
            })],
        })
        self.invoice_id = move.id
        self.state = 'invoice'
        return True