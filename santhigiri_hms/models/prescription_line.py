# -*- coding: utf-8 -*-
"""
prescription.line extensions.
BASE MODULE provides: medicine_id, quantity, no_intakes, time, note,
                      inpatient_id, outpatient_id, res_partner_id.
THIS FILE ADDS: anupanam, route, duration_days.
"""
from odoo import fields, models


class PrescriptionLine(models.Model):
    _inherit = 'prescription.line'

    anupanam = fields.Char(
        string='Anupanam (Adjuvant)',
        help='Adjuvant substance — e.g. Honey, Warm Water, Milk, Ghee, Buttermilk',
    )
    route = fields.Selection([
        ('oral', 'Oral'),
        ('external', 'External Application'),
        ('nasal', 'Nasal (Nasya)'),
        ('rectal', 'Rectal (Vasthi)'),
        ('ophthalmic', 'Ophthalmic'),
        ('ear', 'Ear (Karnapurana)'),
    ], string='Route of Administration', default='oral')
    duration_days = fields.Integer(
        string='Duration (Days)',
        help='Number of days for which medicine is prescribed',
    )
    # Links to casualty
    casualty_id = fields.Many2one(
        'hospital.casualty',
        string='Casualty Reference',
        ondelete='cascade',
    )
    # Links to medication plan
    medication_plan_id = fields.Many2one(
        'hospital.medication.plan',
        string='Medication Plan',
        ondelete='cascade',
    )
    # Links to OP reassessment (Form SAMC/CS/14)
    reassessment_id = fields.Many2one(
        'hospital.op.reassessment',
        string='OP Reassessment',
        ondelete='cascade',
    )
    pathya_apathya = fields.Char(
        string='Pathya-Apathya',
        help='Dietary do\'s (Pathya) and don\'ts (Apathya) for this medicine/course',
    )