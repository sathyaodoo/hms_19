# -*- coding: utf-8 -*-
"""
santhigiri.registration.fee.wizard

Deliberately a TransientModel (a popup form), NOT new fields on
res.partner. Everything needed to raise the invoice — the amount, the
date, an optional note — is entered at the moment the popup is opened
and used once to create the account.move; nothing is stored back onto
the (large, frequently-touched) res.partner table. This keeps the
"Registration Fee" feature fully self-contained in its own small,
throwaway table, independent of any res.partner schema state.

To check whether a patient's registration fee has already been
invoiced, use the existing "Invoice" smart button on the patient form
(base module, action_view_invoice) — the registration invoice is a
normal account.move like any other, easy to spot by its ref
("Registration Fee - <patient code>").
"""
from odoo import api, fields, models
from odoo.exceptions import UserError


class RegistrationFeeWizard(models.TransientModel):
    _name = 'santhigiri.registration.fee.wizard'
    _description = 'Generate Patient Registration Fee Invoice'

    patient_id = fields.Many2one(
        'res.partner', string='Patient', required=True, readonly=True)
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id.id,
        required=True)
    fee_amount = fields.Monetary(
        string='Registration Fee', currency_field='currency_id',
        required=True,
        default=lambda self: self.env['hospital.registration.fee'].sudo().get_current_fee(),
        help='Pre-filled from Configuration > Registration Fee; change '
             'it here if this patient needs a different amount')
    note = fields.Char(
        string='Invoice Reference',
        help='Optional — leave blank to use a default '
             '"Registration Fee - <patient code>" reference')

    def action_generate_invoice(self):
        self.ensure_one()
        if not self.fee_amount or self.fee_amount <= 0:
            raise UserError('Please enter a Registration Fee amount '
                             'greater than zero.')
        if not self.note and not self.patient_id._is_registration_fee_due():
            raise UserError(
                'This patient\'s registration fee is not due yet. '
                'Next due date: %s. Enter a custom Invoice Reference '
                'above if you deliberately want to raise an extra '
                'charge before then.'
                % (self.patient_id.next_registration_due_date or 'N/A')
            )
        ref = self.note or self.patient_id._build_registration_fee_ref()
        move = self.env['account.move'].sudo().create({
            'move_type': 'out_invoice',
            'partner_id': self.patient_id.id,
            'invoice_date': fields.Date.today(),
            'ref': ref,
            'invoice_line_ids': [(0, 0, {
                'name': 'Patient Registration Fee',
                'quantity': 1,
                'price_unit': self.fee_amount,
            })],
        })
        return {
            'name': 'Registration Invoice',
            'res_model': 'account.move',
            'view_mode': 'form',
            'type': 'ir.actions.act_window',
            'res_id': move.id,
        }