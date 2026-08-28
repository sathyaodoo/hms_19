# -*- coding: utf-8 -*-
"""
lab.test master extension — adds default normal range and unit.
When a patient lab test result is created, these defaults auto-fill.
"""
from odoo import api, fields, models


class LabTest(models.Model):
    """Extend lab.test master to store default normal range and unit."""
    _inherit = 'lab.test'

    default_normal_range = fields.Char(
        string='Default Normal Range',
        help='e.g. 12.0 - 17.0 or Negative or <5.0',
        placeholder='e.g. 12.0 - 17.0',
    )
    default_uom_id = fields.Many2one(
        'uom.uom',
        string='Default Unit',
        help='Default unit of measurement for this test',
    )


class LabTestResult(models.Model):
    """
    Override create to auto-fill normal range and unit
    from lab.test master defaults.
    """
    _inherit = 'lab.test.result'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Auto-fill normal range from lab.test master if not already set
            if not vals.get('normal') and vals.get('test_id'):
                lab_test = self.env['lab.test'].browse(vals['test_id'])
                if lab_test.default_normal_range:
                    vals['normal'] = lab_test.default_normal_range
            # Auto-fill uom from lab.test master if not already set
            if not vals.get('uom_id') and vals.get('test_id'):
                lab_test = self.env['lab.test'].browse(
                    vals['test_id'])
                if lab_test.default_uom_id:
                    vals['uom_id'] = lab_test.default_uom_id.id
        records = super().create(vals_list)
        # Check abnormal after create
        for rec in records:
            if rec.is_abnormal:
                rec._notify_doctor_abnormal()
        return records