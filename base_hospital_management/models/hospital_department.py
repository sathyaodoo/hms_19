# -*- coding: utf-8 -*-
from odoo import fields, models, api
from odoo.exceptions import ValidationError


class HospitalDepartment(models.Model):
    """Class holding hospital medical/clinical departments"""
    _name = 'hospital.department'
    _description = 'Hospital Clinical / Medical Department'
    _order = 'sequence, name'

    name = fields.Char(string='Department Name', required=True, translate=True)
    code = fields.Char(
        string='Department Code',
        required=True,
        size=10,
        help='Department short code, e.g., KC, PK, PR, ST, SL, SW, KB, AG, CAS, GEN'
    )
    active = fields.Boolean(string='Active', default=True)
    sequence = fields.Integer(string='Sequence', default=10)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company
    )
    head_doctor_id = fields.Many2one(
        'hr.employee',
        string='Department Head / In-Charge Doctor',
        help='Head of Department / Senior Consultant'
    )
    description = fields.Text(string='Description / Specialities')
    member_ids = fields.Many2many(
        'hr.employee',
        'hospital_dept_member_rel',
        'dept_id',
        'emp_id',
        string='Staff / Members',
        help='Doctors or hospital staff assigned to this medical department'
    )

    @api.constrains('code', 'company_id')
    def _check_unique_code(self):
        for rec in self:
            if rec.code:
                domain = [('id', '!=', rec.id), ('code', '=ilike', rec.code)]
                if rec.company_id:
                    domain.append(('company_id', '=', rec.company_id.id))
                if self.search_count(domain):
                    raise ValidationError('Department code must be unique per hospital company!')
