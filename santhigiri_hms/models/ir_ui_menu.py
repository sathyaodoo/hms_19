# -*- coding: utf-8 -*-
from odoo import api, fields, models


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def _visible_menu_ids(self, debug=False):
        # Fast path: users without the restriction Extra Right are
        # completely unaffected by this feature, so we don't pay the
        # (expensive) cache-clearing cost for them at all.
        if not self.env.user.has_group(
                'santhigiri_hms.group_hide_menu_for_specific_company'):
            return super()._visible_menu_ids(debug=debug)

        # Odoo's base _visible_menu_ids() is cached per (user, debug) only
        # - it does NOT take the active company into account. That means
        # a user who switches company can get a stale menu list back from
        # cache. We force a fresh computation here so our company-based
        # filtering below is always applied to up-to-date data.
        self.env.registry.clear_all_caches()
        menu_ids = super()._visible_menu_ids(debug=debug)

        company = self.env.company
        restrictions = self.env['res.company.restrict.menu'].sudo().search([
            ('company_id', '=', company.id),
        ]).filtered(
            lambda r: not r.user_ids or self.env.user in r.user_ids
        )
        blocked_root_ids = set(restrictions.mapped('menu_id').ids)
        if not blocked_root_ids:
            return menu_ids

        all_menus = self.sudo().search_read([], ['parent_id'])
        parent_map = {
            m['id']: (m['parent_id'][0] if m['parent_id'] else False)
            for m in all_menus
        }

        def is_blocked(menu_id):
            current = menu_id
            visited = set()
            while current and current not in visited:
                if current in blocked_root_ids:
                    return True
                visited.add(current)
                current = parent_map.get(current)
            return False

        return {mid for mid in menu_ids if not is_blocked(mid)}


class ResCompanyRestrictMenu(models.Model):
    _name = 'res.company.restrict.menu'
    _description = 'Company-wise Menu Restriction'
    _rec_name = 'menu_id'

    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company, ondelete='cascade')
    menu_id = fields.Many2one(
        'ir.ui.menu', string='Menu Name', required=True, ondelete='cascade',
        help="Pick the app/menu to hide (its full path is shown so you "
             "can tell which module it belongs to).")
    user_ids = fields.Many2many(
        'res.users', string='Users',
        help="Users for whom this menu will be hidden. Leave empty to "
             "hide it for every user who has the 'Hide Menu for Specific "
             "Company' Extra Right.")

    _sql_constraints = [
        ('company_menu_uniq', 'unique(company_id, menu_id)',
         'This menu is already restricted for this company. '
         'Edit the existing row instead of creating a new one.'),
    ]


class ResCompany(models.Model):
    _inherit = 'res.company'

    restrict_menu_ids = fields.One2many(
        'res.company.restrict.menu', 'company_id', string='Restrict Menu')
    
class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        group = self.env.ref(
            'santhigiri_hms.group_hide_menu_for_specific_company',
            raise_if_not_found=False)
        if group:
            users.sudo().write({
                'group_ids': [(4, group.id)],
            })
        return users