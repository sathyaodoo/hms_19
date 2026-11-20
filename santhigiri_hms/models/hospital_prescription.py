# -*- coding: utf-8 -*-
"""
Prescription Master: hospital.prescription extension.
Provides a central repository for all patient prescriptions, linking OP visits,
IP admissions, prescribing doctors, medicines, dosage, and dietary guidelines.
"""
from odoo import api, fields, models


class HospitalPrescription(models.Model):
    _name = 'hospital.prescription'
    _inherit = ['hospital.prescription', 'mail.thread', 'mail.activity.mixin']
    _order = 'prescription_date desc, id desc'
    _description = 'Prescription Master'

    patient_id = fields.Many2one(
        'res.partner',
        string='Patient',
        required=True,
        domain=[('patient_seq', 'not in', ['Employee', 'User', 'New', False])],
        tracking=True,
    )
    patient_seq = fields.Char(related='patient_id.patient_seq', store=True, string='Patient No.')
    uhid_no = fields.Char(related='patient_id.uhid_no', store=True, string='UHID No.')
    doctor_id = fields.Many2one(
        'hr.employee',
        string='Doctor / Prescribed By',
        tracking=True,
    )
    department_id = fields.Many2one(
        'hospital.department',
        string='Department',
    )
    outpatient_id = fields.Many2one(
        'hospital.outpatient',
        string='OP Visit',
        ondelete='set null',
    )
    inpatient_id = fields.Many2one(
        'hospital.inpatient',
        string='IP Admission',
        ondelete='set null',
    )
    prescription_date = fields.Date(
        string='Date',
        default=fields.Date.today,
        required=True,
        tracking=True,
    )
    prescription_line_ids = fields.One2many(
        'prescription.line',
        'prescription_id',
        string='Medicines Prescribed',
    )
    medicine_count = fields.Integer(
        string='Total Medicines',
        compute='_compute_medicine_count',
        store=True,
    )
    notes = fields.Text(string='General Advice / Dietary Guidelines (Pathya-Apathya)')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('dispensed', 'Dispensed'),
        ('cancelled', 'Cancelled'),
    ], default='active', string='Status', tracking=True)

    @api.depends('prescription_line_ids')
    def _compute_medicine_count(self):
        for rec in self:
            rec.medicine_count = len(rec.prescription_line_ids)

    @api.onchange('patient_id')
    def _onchange_patient_id_fetch(self):
        if self.patient_id:
            # If patient has active OP or IP, auto-populate
            active_op = self.env['hospital.outpatient'].search([
                ('patient_id', '=', self.patient_id.id),
                ('state', 'in', ('draft', 'op')),
            ], order='create_date desc', limit=1)
            if active_op:
                self.outpatient_id = active_op.id
                if not self.doctor_id and active_op.doctor_id:
                    self.doctor_id = active_op.doctor_id.id
                if not self.department_id and active_op.department_id:
                    self.department_id = active_op.department_id.id

            active_ip = self.env['hospital.inpatient'].search([
                ('patient_id', '=', self.patient_id.id),
                ('state', 'in', ('reserve', 'admit')),
            ], order='create_date desc', limit=1)
            if active_ip:
                self.inpatient_id = active_ip.id
                if not self.doctor_id and active_ip.attending_doctor_id:
                    self.doctor_id = active_ip.attending_doctor_id.id

    def action_confirm(self):
        for rec in self:
            rec.state = 'active'

    def action_dispense(self):
        for rec in self:
            rec.state = 'dispensed'

    def action_cancel(self):
        for rec in self:
            rec.state = 'cancelled'
