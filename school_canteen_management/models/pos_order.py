# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class PosOrder(models.Model):
    _inherit = 'pos.order'

    canteen_order_id = fields.Many2one(
        'canteen.order', string='Canteen Token Order', copy=False)

    def _process_saved_order(self, draft):
        """Extend POS order finalisation to:
        1. Deduct from student wallet if wallet payment method used.
        2. Mark linked canteen token order as collected.
        NOTE: Since the Odoo 17/18 POS rewrite (OWL frontend), this
        server-side hook (_process_saved_order) is what runs when an order
        is synced from the frontend to the backend, and it remains the
        entry point in Odoo 19 as well - a safe place for backend-side
        wallet/token logic.
        """
        order = super()._process_saved_order(draft)
        if order and not draft:
            self.browse(order)._apply_wallet_deduction()
            self.browse(order)._mark_token_collected()
        return order

    def _apply_wallet_deduction(self):
        for pos_order in self:
            wallet_payments = pos_order.payment_ids.filtered(
                lambda p: p.payment_method_id.is_student_wallet)
            if not wallet_payments:
                continue
            wallet = self.env['student.wallet'].search(
                [('partner_id', '=', pos_order.partner_id.id)], limit=1)
            if not wallet:
                raise UserError(
                    'No wallet found for %s.' % pos_order.partner_id.name)
            total_wallet_amount = sum(wallet_payments.mapped('amount'))
            wallet.action_deduct(
                total_wallet_amount,
                note='POS Order %s' % pos_order.name,
                pos_order_id=pos_order.id,
            )

    def _mark_token_collected(self):
        for pos_order in self:
            if pos_order.canteen_order_id:
                pos_order.canteen_order_id.action_collect()
