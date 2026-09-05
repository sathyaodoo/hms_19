# -*- coding: utf-8 -*-
from odoo import fields, models


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    is_student_wallet = fields.Boolean(
        string='Is Student Wallet Payment',
        help='Enable this payment method to deduct amount directly '
             'from the student prepaid wallet.')
