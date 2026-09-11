# -*- coding: utf-8 -*-
"""
hospital.registration.fee

Same idea as hospital.fee.master (the existing Consultation Fee
Master): a small, standalone config model, editable under
Configuration, holding the amount to charge. Kept as its own model —
NOT a field on res.company — because a brand-new model gets its own
table created cleanly on install, whereas this environment has
repeatedly failed to apply new fields onto EXISTING models
(res.partner, res.company). A new model sidesteps that failure mode
entirely.
"""
from odoo import api, fields, models


class HospitalRegistrationFee(models.Model):
    _name = 'hospital.registration.fee'
    _description = 'Patient Registration Fee (Configuration)'
    _order = 'id desc'

    name = fields.Char(default='Standard Registration Fee', required=True)
    amount = fields.Monetary(string='Registration Fee', required=True)
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