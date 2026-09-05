# -*- coding: utf-8 -*-
from odoo import api, fields, models


class CanteenMessMenu(models.Model):
    _name = 'canteen.mess.menu'
    _description = 'Hostel Mess Menu / Meal Plan'

    name = fields.Char(string='Plan Name', required=True)
    hostel_id = fields.Many2one('res.partner', string='Hostel/Block')
    meal_plan_type = fields.Selection([
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ], string='Meal Plan Type', default='monthly', required=True)

    price = fields.Float(string='Plan Price')
    meal_line_ids = fields.One2many(
        'canteen.mess.menu.line', 'mess_menu_id', string='Meal Lines')
    student_ids = fields.Many2many(
        'res.partner', string='Subscribed Students',
        help='Students subscribed to this mess meal plan. '
             'If using OpenEduCat, consider changing this field to a '
             'Many2many to op.student instead of res.partner.')
    active = fields.Boolean(default=True)


class CanteenMessMenuLine(models.Model):
    _name = 'canteen.mess.menu.line'
    _description = 'Hostel Mess Menu Line'

    mess_menu_id = fields.Many2one('canteen.mess.menu', ondelete='cascade')
    day = fields.Selection([
        ('mon', 'Monday'), ('tue', 'Tuesday'), ('wed', 'Wednesday'),
        ('thu', 'Thursday'), ('fri', 'Friday'), ('sat', 'Saturday'),
        ('sun', 'Sunday'),
    ], string='Day', required=True)
    meal_type = fields.Selection([
        ('breakfast', 'Breakfast'),
        ('lunch', 'Lunch'),
        ('snacks', 'Snacks'),
        ('dinner', 'Dinner'),
    ], string='Meal', required=True)
    menu_item_ids = fields.Many2many('canteen.menu.item', string='Items')