# -*- coding: utf-8 -*-
"""
hospital.pharmacy extensions.
BASE MODULE provides: pharmacist_id, medicine_ids, sales_team_id, create_sale_order().
THIS FILE ADDS: pharmacy_type (op/ip), dispensing_category on sale.order.
"""
from odoo import api, fields, models


class HospitalPharmacy(models.Model):
    _inherit = 'hospital.pharmacy'

    pharmacy_type = fields.Selection([
        ('op', 'OP Pharmacy (Outpatient)'),
        ('ip', 'IP Pharmacy (Inpatient)'),
    ], string='Pharmacy Type', default='op', required=True,
       help='OP: walk-in/casualty patients. IP: admitted patients.')

    location_id = fields.Many2one(
        'stock.location',
        string='Pharmacy Store Location',
        domain=[('usage', '=', 'internal')],
        help='The inventory location for this pharmacy store. '
             'OP Pharmacy → OP Pharmacy Store. '
             'IP Pharmacy → IP Pharmacy Store.'
    )

    @api.model
    def create_sale_order(self, kwargs):
        """Override to tag sale orders from pharmacy dashboard as op_dispensing."""
        result = super().create_sale_order(kwargs)
        # Set dispensing_category on created sale order
        if result and result.get('invoice_id'):
            so = self.env['sale.order'].sudo().browse(
                int(result['invoice_id']))
            if so.exists() and not so.dispensing_category:
                so.sudo().write({'dispensing_category': 'op_dispensing'})
        return result


class SaleOrder(models.Model):
    """Extend sale.order to track dispensing category for IP/OP billing."""
    _inherit = 'sale.order'

    dispensing_category = fields.Selection([
        ('patient_medication', 'IP Patient Medication'),
        ('procedure_treatment', 'IP Procedure Treatment'),
        ('op_dispensing', 'OP Dispensing'),
    ], string='Dispensing Category', default=False,
       help='Tracks how medicines are billed.')

    inpatient_id = fields.Many2one(
        'hospital.inpatient', string='IP Admission',
        help='Set for IP dispensing orders')