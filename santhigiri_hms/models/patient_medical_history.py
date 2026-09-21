# -*- coding: utf-8 -*-
"""
patient.medical.history

Captures a patient's medical history from BEFORE they joined Santhigiri
Ayurveda Medical College — entered once, typically during registration
of a NEW patient (see PAT018-style patient form).

Kept as its own model instead of reusing the base module's
prescription_ids/lab_test_ids on res.partner, because those lists are
system-generated (create="0" in the base "Medical" tab) from actual
OP/IP encounters that happen inside this system. There is no way to
log a patient's pre-existing history there. This model exists purely
for that onboarding data-entry need.
"""
from odoo import fields, models


class PatientMedicalHistory(models.Model):
    _name = 'patient.medical.history'
    _description = 'Patient Previous Medical History (Onboarding)'
    _order = 'date desc, id desc'

    patient_id = fields.Many2one(
        'res.partner', string='Patient', required=True, ondelete='cascade',
        index=True, help='Patient this history entry belongs to')
    date = fields.Date(
        string='Date', default=fields.Date.context_today,
        help='Date the condition was diagnosed or treated, if known')
    condition = fields.Char(
        string='Condition / Diagnosis', required=True,
        help='Name of the illness, surgery or condition being recorded')
    is_chronic = fields.Boolean(
        string='Chronic / Ongoing',
        help='Check if this is an ongoing condition rather than a '
             'resolved one')
    treated_at = fields.Char(
        string='Hospital / Clinic',
        help='Where the patient was previously treated')
    treating_doctor = fields.Char(
        string='Doctor',
        help='Doctor who treated the patient previously')
    description = fields.Text(
        string='Details',
        help='Additional notes about the condition or treatment')
    attachment = fields.Binary(
        string='Medical Report', attachment=True,
        help='Scanned copy of previous medical records, if available')
    attachment_name = fields.Char(string='File Name')