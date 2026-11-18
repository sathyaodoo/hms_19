# -*- coding: utf-8 -*-
"""
patient.previous.prescription

Captures medicines a patient was already taking BEFORE joining
Santhigiri Ayurveda Medical College, entered once during onboarding.

Kept separate from the base module's prescription.line (which is
system-generated per OP/IP visit and tied to a product.template in
this hospital's catalog) because onboarding data may reference
medicines/formulations this system has never heard of — hence
medicine_name is a free-text field, with an optional link to a
matching product if one exists.
"""
from odoo import fields, models


class PatientPreviousPrescription(models.Model):
    _name = 'patient.previous.prescription'
    _description = 'Patient Previous Prescription (Onboarding)'
    _order = 'date desc, id desc'

    patient_id = fields.Many2one(
        'res.partner', string='Patient', required=True, ondelete='cascade',
        index=True, help='Patient this previous prescription belongs to')
    date = fields.Date(string='Prescribed On', default=fields.Date.context_today)
    medicine_name = fields.Char(
        string='Medicine', required=True,
        help='Name of the medicine as it was prescribed earlier; free '
             'text so it can be entered even if it is not registered '
             'as a product in this system')
    medicine_id = fields.Many2one(
        'product.template', string='Matching Medicine (Optional)',
        domain=['|', ('medicine_ok', '=', True), ('vaccine_ok', '=', True)],
        help='Link this to the equivalent product in this system, if '
             'one exists')
    dosage = fields.Char(string='Dosage', help='E.g. 500mg')
    frequency = fields.Char(string='Frequency', help='E.g. Twice a day')
    duration = fields.Char(string='Duration', help='E.g. 5 days')
    prescribed_by = fields.Char(
        string='Prescribed By', help='Doctor who prescribed this earlier')
    note = fields.Text(string='Notes')