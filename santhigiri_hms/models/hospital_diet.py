# -*- coding: utf-8 -*-
from odoo import fields, models


class HospitalDietPlan(models.Model):
    _name = 'hospital.diet.plan'
    _description = 'IP Diet Plan'
    _order = 'name'

    name = fields.Char(string='Diet Plan Name', required=True)
    diet_type = fields.Selection([
        ('normal', 'Normal Diet'),
        ('special', 'Special Diet'),
        ('diabetic', 'Diabetic Diet'),
        ('therapeutic', 'Therapeutic Diet'),
    ], string='Diet Type', required=True)
    ayurvedic_context = fields.Selection([
        ('none', 'None / General'),
        ('snehapanam', 'Snehapanam'),
        ('vasthi', 'Vasthi'),
        ('virechanam', 'Virechanam'),
        ('vamanam', 'Vamanam'),
        ('nasyam', 'Nasyam'),
        ('other', 'Other Panchakarma'),
    ], string='Ayurvedic Context', default='none',
       help='Specific Panchakarma procedure this diet supports')
    meal_schedule = fields.Text(string='Meal Schedule',
                                 help='Breakfast, Lunch, Dinner, Snack details')
    dietary_restrictions = fields.Text(string='Dietary Restrictions')
    special_instructions = fields.Text(string='Special Instructions')
    dietitian_id = fields.Many2one('hr.employee', string='Assigned Dietitian',
                                    domain=[('is_dietitian', '=', True)])
    active = fields.Boolean(default=True)


class HospitalFoodSupply(models.Model):
    _name = 'hospital.food.supply'
    _description = 'IP Daily Food Supply Record'
    _order = 'supply_date desc, meal_type'

    inpatient_id = fields.Many2one('hospital.inpatient', string='IP Admission',
                                    required=True, ondelete='cascade', index=True)
    patient_id = fields.Many2one(related='inpatient_id.patient_id', store=True)
    supply_date = fields.Date(string='Date', required=True, default=fields.Date.today)
    meal_type = fields.Selection([
        ('breakfast', 'Breakfast'),
        ('lunch', 'Lunch'),
        ('evening_snack', 'Evening Snack'),
        ('dinner', 'Dinner'),
    ], string='Meal Type', required=True)
    diet_plan_id = fields.Many2one('hospital.diet.plan', string='Diet Plan')
    additional_items = fields.Text(string='Additional Items Supplied')
    charge = fields.Monetary(string='Charge', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda s: s.env.company.currency_id)
    bystander_meal = fields.Boolean(string='Bystander Meal Included')
    bystander_charge = fields.Monetary(string='Bystander Meal Charge', currency_field='currency_id')
    served_by = fields.Many2one('hr.employee', string='Served By')
    notes = fields.Text(string='Notes')
