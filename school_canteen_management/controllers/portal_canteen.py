# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class CanteenPortal(http.Controller):

    @http.route(['/canteen/menu'], type='http', auth='user', website=True)
    def canteen_menu(self, **kw):
        """Display today's available menu items to the logged in student/staff."""
        items = request.env['canteen.menu.item'].sudo().search([
            ('active', '=', True),
            ('is_mess_item', '=', False),
        ])
        error = kw.get('error')
        return request.render(
            'school_canteen_management.portal_canteen_menu_template',
            {'items': items, 'error': error})

    @http.route(['/canteen/order/new'], type='http', auth='user',
                website=True, methods=['POST'], csrf=True)
    def canteen_order_new(self, **post):
        """Create a pre-order (token) from selected menu items.
        Expects post data like: item_<id> = qty
        """
        partner = request.env.user.partner_id
        order_lines = []
        for key, val in post.items():
            if key.startswith('item_') and val:
                try:
                    qty = float(val)
                except (ValueError, TypeError):
                    continue
                if qty > 0:
                    item_id = int(key.split('_')[1])
                    order_lines.append((0, 0, {
                        'menu_item_id': item_id,
                        'qty': qty,
                    }))

        if not order_lines:
            # Nothing selected - redirect back with an error flag so the
            # page can show a clear message instead of doing nothing.
            return request.redirect('/canteen/menu?error=no_items')

        order = request.env['canteen.order'].sudo().create({
            'partner_id': partner.id,
            'order_line_ids': order_lines,
        })
        order.action_confirm()
        return request.redirect('/canteen/order/%s' % order.id)

    @http.route(['/canteen/order/<int:order_id>'], type='http',
                auth='user', website=True)
    def canteen_order_detail(self, order_id, **kw):
        order = request.env['canteen.order'].sudo().browse(order_id)
        return request.render(
            'school_canteen_management.portal_canteen_order_template',
            {'order': order})