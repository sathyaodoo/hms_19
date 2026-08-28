# -*- coding: utf-8 -*-
"""
hr.employee extensions.
BASE MODULE already adds: doctor, consultancy_charge, specialization_ids, degree_ids.
THIS FILE ADDS: is_therapist, is_rmo, is_dietitian, is_intern flags.
"""
from odoo import fields, models, api


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    @api.onchange('job_id', 'job_title')
    def _onchange_job_set_doctor(self):
        """Auto-set doctor=True when Job Position or Job Title is Doctor."""
        if (self.job_id and 'doctor' in (self.job_id.name or '').lower()) or            'doctor' in (self.job_title or '').lower():
            self.doctor = True
        # Note: we don't auto-unset doctor=False to avoid accidental removal

    is_therapist = fields.Boolean(
        string='Is Therapist',
        help='Mark this employee as a therapy/Panchakarma therapist',
    )
    is_rmo = fields.Boolean(
        string='Is RMO',
        help='Resident Medical Officer — can manage casualty and IP monitoring',
    )
    is_dietitian = fields.Boolean(
        string='Is Dietitian',
        help='Mark this employee as a dietitian for IP food management',
    )
    is_intern = fields.Boolean(
        string='Is Intern / Student',
        help='Medical intern from affiliated college',
    )
    # Used by internship module
    intern_id = fields.Many2one(
        'hospital.intern',
        string='Intern Profile',
        help='Links this employee account to the intern profile',
    )