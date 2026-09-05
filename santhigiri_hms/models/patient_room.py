# -*- coding: utf-8 -*-
"""
patient.room extensions.
BASE MODULE provides: name, building_id, floor_no, bed_type, rent, state (avail/not),
                      nurse_ids, room_facilities_ids.
THIS FILE ADDS: room_sub_type (AC/Non-AC/Suite), rent_non_ac, rent_ac, rent_suite,
               cleaning state, housekeeping methods.
"""
from odoo import fields, models, api


class PatientRoom(models.Model):
    _inherit = 'patient.room'

    room_type = fields.Selection([
        ('general', 'General Ward'),
        ('payward', 'Pay Ward'),
    ], string='Room Type', default='general')

    room_sub_type = fields.Selection([
        ('non_ac', 'Non-AC Room'),
        ('ac', 'AC Room'),
        ('suite', 'Suite Room'),
    ], string='Room Sub-Type',
       help='Applicable for Pay Ward rooms only')

    rent_non_ac = fields.Monetary(string='Rent — Non-AC (per day)',
                                   currency_field='currency_id')
    rent_ac = fields.Monetary(string='Rent — AC (per day)',
                               currency_field='currency_id')
    rent_suite = fields.Monetary(string='Rent — Suite (per day)',
                                  currency_field='currency_id')
    currency_id = fields.Many2one('res.currency',
                                   default=lambda s: s.env.company.currency_id)

    # Extend state to include cleaning
    state = fields.Selection(
        selection_add=[('cleaning', 'Under Cleaning')],
        ondelete={'cleaning': 'set default'},
    )

    housekeeping_notes = fields.Text(string='Housekeeping Notes')
    last_cleaned_by = fields.Many2one('hr.employee', string='Last Cleaned By')
    last_cleaned_date = fields.Datetime(string='Last Cleaned On')

    def action_mark_clean_ready(self):
        """Housekeeping staff marks room as clean and available."""
        for rec in self:
            rec.state = 'avail'
            rec.last_cleaned_by = self.env.user.employee_id.id if hasattr(self.env.user, 'employee_id') else False
            rec.last_cleaned_date = fields.Datetime.now()

    def effective_rent(self):
        """Return the effective daily rent based on sub-type."""
        self.ensure_one()
        if self.room_sub_type == 'ac':
            return self.rent_ac or self.rent
        elif self.room_sub_type == 'suite':
            return self.rent_suite or self.rent
        elif self.room_sub_type == 'non_ac':
            return self.rent_non_ac or self.rent
        return self.rent
    
    from odoo import api, models


class HospitalBuilding(models.Model):
    _inherit = 'hospital.building'

    def _compute_display_name(self):
        """Show the building's email instead of its code/name in every
        Many2one dropdown, list, and report that references this model."""
        for building in self:
            building.display_name = building.email or building.name or ''

    @api.model
    def _search_display_name(self, operator, value):
        """Optional: so typing in the dropdown also matches on email,
        not just the underlying 'name'/code field. Remove this method
        if you don't need search-by-email."""
        domain = super()._search_display_name(operator, value)
        if operator in ('like', 'ilike', '=', '=like', '=ilike'):
            domain = ['|', ('email', operator, value)] + domain
        return domain
