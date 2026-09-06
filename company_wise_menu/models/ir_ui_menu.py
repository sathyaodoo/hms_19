# -*- coding: utf-8 -*-
from odoo import fields, models


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    company_ids = fields.Many2many(
        'res.company',
        'ir_ui_menu_res_company_rel',
        'menu_id',
        'company_id',
        string='Companies',
        help="Restrict this menu (and its sub-menus) to the selected "
             "companies. It will only be visible when one of these "
             "companies is the currently active company. "
             "Leave empty to show for all companies (default behaviour).",
    )
