# -*- coding: utf-8 -*-
"""
Category-based consultation fee master.
BASE MODULE uses doctor.consultancy_charge (flat fee per doctor).
THIS FILE adds a category → amount fee matrix so fees vary by patient category.
"""
from odoo import fields, models


class HospitalFeeMaster(models.Model):
    _name = 'hospital.fee.master'
    _description = 'Category-wise Consultation Fee'
    _order = 'patient_category'

    patient_category = fields.Selection([
        ('general', 'General'),
        ('vip', 'VIP'),
        ('senior_citizen', 'Senior Citizen'),
        ('bpl', 'BPL / Karunyam'),
        ('payward', 'Pay Ward'),
        ('ardram', 'Ardram'),
        ('jeevanam', 'Jeevanam'),
    ], string='Patient Category', required=True)
    amount = fields.Monetary(string='Consultation Fee', required=True)
    currency_id = fields.Many2one('res.currency', default=lambda s: s.env.company.currency_id)
    department_id = fields.Many2one('hr.department', string='Department (optional)',
                                    help='Leave blank to apply to all departments')
    active = fields.Boolean(default=True)
