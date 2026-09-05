# -*- coding: utf-8 -*-
import base64
from io import BytesIO

from odoo import api, fields, models

try:
    import qrcode
except ImportError:
    qrcode = None


class CanteenOrder(models.Model):
    _name = 'canteen.order'
    _description = 'Canteen Pre-Order / Token'
    _order = 'create_date desc'

    token_number = fields.Char(
        string='Token No.', copy=False, readonly=True,
        default=lambda self: self.env['ir.sequence'].next_by_code(
            'canteen.order.token') or 'New')

    partner_id = fields.Many2one(
        'res.partner', string='Student / Staff', required=True)
    order_date = fields.Date(default=fields.Date.context_today)
    pickup_time_slot = fields.Char(string='Pickup Slot')

    order_line_ids = fields.One2many(
        'canteen.order.line', 'order_id', string='Order Lines')
    amount_total = fields.Float(
        string='Total', compute='_compute_amount_total', store=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('ready', 'Ready for Pickup'),
        ('collected', 'Collected'),
        ('cancelled', 'Cancelled'),
    ], default='draft', string='Status', tracking=True)

    qr_code = fields.Binary(string='QR Code', compute='_compute_qr_code', store=True)
    pos_order_id = fields.Many2one(
        'pos.order', string='Linked POS Order', copy=False, readonly=True)

    @api.depends('order_line_ids.price_subtotal')
    def _compute_amount_total(self):
        for order in self:
            order.amount_total = sum(order.order_line_ids.mapped('price_subtotal'))

    @api.depends('token_number')
    def _compute_qr_code(self):
        for order in self:
            if order.token_number and order.token_number != 'New' and qrcode:
                qr = qrcode.QRCode(box_size=6, border=2)
                qr.add_data(order.token_number)
                qr.make(fit=True)
                img = qr.make_image(fill_color='black', back_color='white')
                buffer = BytesIO()
                img.save(buffer, format='PNG')
                order.qr_code = base64.b64encode(buffer.getvalue())
            else:
                order.qr_code = False

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_mark_ready(self):
        self.write({'state': 'ready'})

    def action_collect(self):
        """Called from counter (portal/QR scan) when order is billed & collected."""
        self.write({'state': 'collected'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})


class CanteenOrderLine(models.Model):
    _name = 'canteen.order.line'
    _description = 'Canteen Pre-Order Line'

    order_id = fields.Many2one('canteen.order', ondelete='cascade')
    menu_item_id = fields.Many2one('canteen.menu.item', required=True)
    qty = fields.Float(string='Qty', default=1.0)
    price_unit = fields.Float(
        string='Unit Price', related='menu_item_id.price', store=True)
    price_subtotal = fields.Float(
        string='Subtotal', compute='_compute_subtotal', store=True)
    order_date = fields.Date(
        related='order_id.order_date', string='Order Date', store=True)

    @api.depends('qty', 'price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.price_subtotal = line.qty * line.price_unit