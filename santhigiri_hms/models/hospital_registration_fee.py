# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HospitalRegistrationFee(models.Model):
    _name = 'hospital.registration.fee'
    _description = 'Patient Registration Fee (Configuration)'
    _order = 'id desc'

    name = fields.Char(default='Standard Registration Fee', required=True)
    amount = fields.Monetary(string='Registration Fee', required=True)
    renewal_months = fields.Integer(
        string='Renewal Period (Months)', default=3, required=True,
        help='Registration fee becomes due again this many months '
             'after the last invoice. Configurable here — NOT '
             'hardcoded in Python — so changing how often patients '
             'are re-charged never needs a code deployment, only an '
             'edit to this record.')
    currency_id = fields.Many2one(
        'res.currency', default=lambda s: s.env.company.currency_id)
    active = fields.Boolean(default=True)

    @api.model
    def get_current_fee(self):
        """Returns the most recently created ACTIVE fee amount, or 0.0
        if none has been configured yet (in which case no automatic
        charge is raised — see res_partner.py)."""
        rec = self.search([('active', '=', True)], order='id desc', limit=1)
        return rec.amount if rec else 0.0

    @api.model
    def get_renewal_months(self):
        """Configurable renewal interval, in months. Used everywhere
        instead of a hardcoded relativedelta(months=3) — see
        res_partner.py's _compute_registration_fee_status() and
        _is_registration_fee_due(). Falls back to 3 only if no
        Registration Fee record has been configured yet at all
        (matches the original hardcoded default, so behavior is
        unchanged for anyone who hasn't touched this new field)."""
        rec = self.search([('active', '=', True)], order='id desc', limit=1)
        return rec.renewal_months if rec and rec.renewal_months else 3