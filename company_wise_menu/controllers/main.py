# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class CompanyWiseMenuController(http.Controller):

    @http.route('/company_wise_menu/get_restrictions', type='json', auth='user', readonly=True)
    def get_restrictions(self):
        """ Returns a mapping of {menu_id: [company_id, company_id, ...]}
        for every root/app menu that has an explicit company restriction.
        Deliberately NOT cached (no ormcache) - always computed fresh so
        it can never go stale, and it's a tiny amount of data. """
        menus = request.env['ir.ui.menu'].sudo().search([
            ('company_ids', '!=', False),
        ])
        return {
            str(menu.id): menu.company_ids.ids
            for menu in menus
        }
