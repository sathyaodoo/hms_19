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
    
    
 
class LabTestCategory(models.Model):
    _name = 'lab.test.category'
    _description = 'Lab Test Category'
    _order = 'sequence, name'
 
    name = fields.Char(string='Category Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    description = fields.Text(string='Description')
    color = fields.Integer(string='Color')
    active = fields.Boolean(string='Active', default=True)
    test_ids = fields.One2many('lab.test', 'category_id', string='Tests')
    test_count = fields.Integer(string='Test Count', compute='_compute_test_count')
 
    def _compute_test_count(self):
        for rec in self:
            rec.test_count = len(rec.test_ids)
 
    def action_view_tests(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Lab Tests — ' + self.name,
            'res_model': 'lab.test',
            'view_mode': 'list,form',
            'domain': [('category_id', '=', self.id)],
            'context': {'default_category_id': self.id},
        }
 
 
class LabTestExtension(models.Model):
    """Add category_id to existing lab.test model."""
    _inherit = 'lab.test'
 
    category_id = fields.Many2one(
        'lab.test.category',
        string='Category',
        help='Group this test under a category (e.g. Haematology, Biochemistry, etc.)',
    )
 
