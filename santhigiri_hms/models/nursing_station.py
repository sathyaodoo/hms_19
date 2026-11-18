# -*- coding: utf-8 -*-
"""
Nursing Station Extensions & Enhancements:
- Adds patient, room, bed, vitals, nurse to nursing.plan.
- Adds patient, UHID, room to hospital.medication.plan.
"""
from odoo import api, fields, models


class NursingPlan(models.Model):
    _inherit = 'nursing.plan'

    patient_id = fields.Many2one(
        'res.partner',
        string='Patient',
        related='admission_id.patient_id',
        store=True,
    )
    uhid_no = fields.Char(
        string='UHID No.',
        related='patient_id.uhid_no',
        store=True,
    )
    room_id = fields.Many2one(
        'patient.room',
        string='Room',
        related='admission_id.room_id',
        store=True,
    )
    bed_id = fields.Many2one(
        'hospital.bed',
        string='Bed',
        related='admission_id.bed_id',
        store=True,
    )
    pulse = fields.Char(string='Pulse (bpm)')
    bp_sys = fields.Integer(string='BP Systolic')
    bp_dia = fields.Integer(string='BP Diastolic')
    temp_f = fields.Float(string='Temp (°F)')
    spo2 = fields.Integer(string='SpO2 (%)')
    nurse_id = fields.Many2one(
        'hr.employee',
        string='Attending Nurse',
        default=lambda self: self.env.user.employee_id,
    )


class HospitalMedicationPlan(models.Model):
    _inherit = 'hospital.medication.plan'

    patient_id = fields.Many2one(
        'res.partner',
        string='Patient',
        compute='_compute_nursing_patient_id',
        store=True,
    )
    uhid_no = fields.Char(
        string='UHID No.',
        related='patient_id.uhid_no',
        store=True,
    )
    room_id = fields.Many2one(
        'patient.room',
        string='Room',
        related='inpatient_id.room_id',
        store=True,
    )

    @api.depends('inpatient_id.patient_id', 'assessment_id.patient_id')
    def _compute_nursing_patient_id(self):
        for rec in self:
            rec.patient_id = rec.inpatient_id.patient_id or rec.assessment_id.patient_id or False
