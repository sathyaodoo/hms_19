# -*- coding: utf-8 -*-
"""
product.template extension — adds is_procedure field.
BASE MODULE already has: medicine_ok, vaccine_ok, pharmacy_id, medicine_brand_id.
THIS FILE ADDS: is_procedure (for OP/IP procedure/therapy products).
"""
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_procedure = fields.Boolean(
        string='Is Procedure / Therapy',
        help='Mark this product as a Panchakarma or therapy procedure. '
             'Used in Procedure Prescriptions and IP Treatment Plans.',
        default=False,
    )