# -*- coding: utf-8 -*-
"""
product.template extension.
BASE MODULE already has: medicine_ok, vaccine_ok, pharmacy_id, medicine_brand_id.
THIS FILE ADDS:
  - is_procedure   : for OP/IP procedure/therapy products
  - prakarana      : free-text field, shown only in the Hospital company
  - show_prakarana : technical helper used to hide/show Prakarana in the form
"""
from odoo import api, fields, models


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

    show_prakarana = fields.Boolean(
        string='Show Prakarana',
        compute='_compute_show_prakarana',
        help='Technical field: True only when the currently selected '
             'company is Santhigiri Ayurveda Medical Hospital.',
    )

    @api.depends_context('company')
    def _compute_show_prakarana(self):
        # Santhigiri Ayurveda Medical Hospital is the main company (ID 1),
        # which Odoo always registers with the XML ID 'base.main_company'.
        hospital = self.env.ref('base.main_company', raise_if_not_found=False)
        is_hospital = bool(hospital) and self.env.company == hospital
        for product in self:
            product.show_prakarana = is_hospital