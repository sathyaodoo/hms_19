# -*- coding: utf-8 -*-
"""
product.template extension.
BASE MODULE already has: medicine_ok, vaccine_ok, pharmacy_id, medicine_brand_id.
THIS FILE ADDS:
  - is_procedure   : for OP/IP procedure/therapy products
  - prakarana      : free-text field, shown only in the Hospital company
  - show_prakarana : technical helper used to hide/show Prakarana
                     (on the product form and in the Medicine Brand master)
"""
from odoo import api, fields, models


def _is_hospital_company(env):

    hospital = env.ref('base.main_company', raise_if_not_found=False)
    return bool(hospital) and env.company == hospital


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_procedure = fields.Boolean(
        string='Is Procedure / Therapy',
        help='Mark this product as a Panchakarma or therapy procedure. '
             'Used in Procedure Prescriptions and IP Treatment Plans.',
        default=False,
    )

    prakarana = fields.Char(
        string='Prakarana',
        tracking=True,
        help='Prakarana of the product (visible only in the Hospital company).',
    )

    dose = fields.Char(string='Dose')
    indication = fields.Char(string='Indication')

    show_prakarana = fields.Boolean(
        string='Show Prakarana',
        compute='_compute_show_prakarana',
        help='Technical field: True only when the currently selected '
             'company is Santhigiri Ayurveda Medical Hospital.',
    )

    @api.depends_context('company')
    def _compute_show_prakarana(self):
        is_hospital = _is_hospital_company(self.env)
        for product in self:
            product.show_prakarana = is_hospital


class MedicineBrand(models.Model):
    _inherit = 'medicine.brand'

    show_prakarana = fields.Boolean(
        string='Show Prakarana',
        compute='_compute_show_prakarana',
        help='Technical field: used to show the Prakarana column in the '
             'medicine list only in the Hospital company.',
    )

    @api.depends_context('company')
    def _compute_show_prakarana(self):
        is_hospital = _is_hospital_company(self.env)
        for brand in self:
            brand.show_prakarana = is_hospital