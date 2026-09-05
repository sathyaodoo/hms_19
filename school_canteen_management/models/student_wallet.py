# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StudentWallet(models.Model):
    _name = 'student.wallet'
    _description = 'Student Prepaid Wallet'
    _rec_name = 'partner_id'

    partner_id = fields.Many2one(
        'res.partner', string='Student/Staff', required=True, unique=True)
    balance = fields.Monetary(string='Balance', default=0.0)
    low_balance_threshold = fields.Monetary(default=50.0)
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id)
    transaction_ids = fields.One2many(
        'student.wallet.transaction', 'wallet_id', string='Transactions')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('partner_uniq', 'unique(partner_id)',
         'Each student/staff can have only one wallet.'),
    ]

    def action_topup(self, amount, note='Top-up'):
        self.ensure_one()
        self._create_transaction(amount, 'credit', note)

    def action_deduct(self, amount, note='Canteen purchase', pos_order_id=None):
        self.ensure_one()
        if self.balance < amount:
            raise UserError(_(
                'Insufficient wallet balance for %s. Available: %s, Required: %s'
            ) % (self.partner_id.name, self.balance, amount))
        self._create_transaction(-amount, 'debit', note, pos_order_id)
        if self.balance <= self.low_balance_threshold:
            self._send_low_balance_alert()

    def _create_transaction(self, amount, ttype, note, pos_order_id=None):
        self.ensure_one()
        self.env['student.wallet.transaction'].create({
            'wallet_id': self.id,
            'amount': amount,
            'transaction_type': ttype,
            'source': 'canteen',
            'note': note,
            'pos_order_id': pos_order_id,
        })
        self.balance += amount

    def _send_low_balance_alert(self):
        self.ensure_one()
        template = self.env.ref(
            'school_canteen_management.mail_template_low_balance',
            raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)


class StudentWalletTransaction(models.Model):
    _name = 'student.wallet.transaction'
    _description = 'Student Wallet Transaction'
    _order = 'create_date desc'

    wallet_id = fields.Many2one(
        'student.wallet', required=True, ondelete='cascade')
    amount = fields.Monetary()
    currency_id = fields.Many2one(
        related='wallet_id.currency_id', store=True)
    transaction_type = fields.Selection([
        ('credit', 'Credit (Top-up)'),
        ('debit', 'Debit (Purchase)'),
    ], required=True)
    source = fields.Selection([
        ('canteen', 'Canteen'),
        ('hostel_mess', 'Hostel Mess'),
        ('other', 'Other'),
    ], default='canteen')
    note = fields.Char()
    pos_order_id = fields.Many2one('pos.order', string='POS Order')
    date = fields.Datetime(default=fields.Datetime.now)
    
