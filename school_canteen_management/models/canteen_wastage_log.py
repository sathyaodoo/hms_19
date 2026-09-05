# -*- coding: utf-8 -*-
from odoo import api, fields, models


class CanteenWastageLog(models.Model):
    _name = 'canteen.wastage.log'
    _description = 'Canteen Wastage / Spoilage Log'
    _order = 'date desc'

    menu_item_id = fields.Many2one('canteen.menu.item', string='Item', required=True)
    qty_wasted = fields.Float(string='Quantity Wasted', required=True)
    reason = fields.Selection([
        ('spoilage', 'Spoilage'),
        ('overproduction', 'Overproduction'),
        ('return', 'Customer Return'),
        ('other', 'Other'),
    ], default='spoilage', required=True)
    date = fields.Date(default=fields.Date.context_today)
    cost_impact = fields.Float(
        string='Cost Impact', compute='_compute_cost_impact', store=True)
    notes = fields.Text()

    @api.depends('qty_wasted', 'menu_item_id.price')
    def _compute_cost_impact(self):
        for rec in self:
            rec.cost_impact = rec.qty_wasted * (rec.menu_item_id.price or 0.0)
