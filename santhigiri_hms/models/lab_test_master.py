# -*- coding: utf-8 -*-
"""
lab.test master extension — adds default normal range and unit.

Normal ranges can differ by patient gender (e.g. Haemoglobin, Total
WBC count, Creatinine, etc. have different reference ranges for Male
and Female patients), so this stores separate Male and Female ranges
directly — no single shared "Default Normal Range" field anymore.
Instead, _get_default_normal_range() below picks the range matching
the patient's gender, falling back to whichever of Male/Female IS
configured if the gender-specific one is blank or gender couldn't be
resolved — the same reliability the old single field had, just
sourced from two fields instead of one.

When a patient lab test result is created, these defaults auto-fill
onto the result line — using the range that matches the patient's
gender (or the fallback above).
"""
from odoo import api, fields, models


class LabTest(models.Model):
    """Extend lab.test master to store default normal range and unit."""
    _inherit = 'lab.test'

    default_normal_range_male = fields.Char(
        string='Normal Range (Male)',
        help='Default normal range for male patients. Accepts a '
             'numeric range, a qualitative result, or a one-sided '
             'threshold — e.g. 13.5 - 17.5 or Negative or <5.0 or >40',
        placeholder='e.g. 13.5 - 17.5 or Negative or <5.0',
    )
    default_normal_range_female = fields.Char(
        string='Normal Range (Female)',
        help='Default normal range for female patients. Accepts a '
             'numeric range, a qualitative result, or a one-sided '
             'threshold — e.g. 12.0 - 15.5 or Negative or <5.0 or >40',
        placeholder='e.g. 12.0 - 15.5 or Negative or <5.0',
    )
    default_uom_id = fields.Many2one(
        'uom.uom',
        string='Default Unit',
        help='Default unit of measurement for this test',
    )

    def _get_default_normal_range(self, gender=False):
        
        self.ensure_one()
        if gender == 'male' and self.default_normal_range_male:
            return self.default_normal_range_male
        if gender == 'female' and self.default_normal_range_female:
            return self.default_normal_range_female
        # Fallback: gender unresolved, gender is 'other', or the
        # matching field was left blank for this specific test — use
        # whichever range IS configured instead of leaving it blank.
        return self.default_normal_range_male or self.default_normal_range_female


class LabTestResult(models.Model):
    
    _inherit = 'lab.test.result'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('test_id'):
                continue
            lab_test = self.env['lab.test'].browse(vals['test_id'])
            # Auto-fill normal range from lab.test master if not
            # already set, using the range for the patient's gender.
            if not vals.get('normal'):
                gender = self._get_patient_gender(vals)
                normal_range = lab_test._get_default_normal_range(gender)
                if normal_range:
                    vals['normal'] = normal_range
            # Auto-fill uom from lab.test master if not already set
            if not vals.get('uom_id') and lab_test.default_uom_id:
                vals['uom_id'] = lab_test.default_uom_id.id
        records = super().create(vals_list)
        # Check abnormal after create
        for rec in records:
            if rec.is_abnormal:
                rec._notify_doctor_abnormal()
        return records

    def _get_patient_gender(self, vals):
        
        patient = self.env['res.partner']
        patient_id = (vals.get('patient_id')
                      or self.env.context.get('default_patient_id'))
        parent_id = (vals.get('parent_id')
                     or self.env.context.get('default_parent_id'))
        if patient_id:
            patient = patient.browse(patient_id)
        elif parent_id:
            parent = self.env['patient.lab.test'].browse(parent_id)
            patient = parent.patient_id
        return patient.gender if patient else False

    @api.onchange('test_id', 'patient_id')
    def _onchange_test_id_normal_range(self):
        
        for rec in self:
            if not rec.test_id:
                continue
            patient = rec.patient_id or rec.parent_id.patient_id
            gender = patient.gender if patient else False
            if not rec.normal:
                normal_range = rec.test_id._get_default_normal_range(
                    gender)
                if normal_range:
                    rec.normal = normal_range
            if not rec.uom_id and rec.test_id.default_uom_id:
                rec.uom_id = rec.test_id.default_uom_id


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