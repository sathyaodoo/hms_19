from odoo import fields, models


class HospitalBed(models.Model):
    _inherit = 'hospital.bed'

    state = fields.Selection(
        [('avail', 'Available'),
         ('reserve', 'Reserve'),
         ('not', 'Unavailable'),
         ('cleaning', 'Under Cleaning')],
        string='State', readonly=True, default='avail',
        help='State of the bed')

    housekeeping_notes = fields.Text(string='Housekeeping Notes')
    last_cleaned_by = fields.Many2one('hr.employee', string='Last Cleaned By')
    last_cleaned_date = fields.Datetime(string='Last Cleaned On')

    def action_mark_clean_ready(self):
        """Housekeeping staff marks bed as clean and available. Mirrors
        PatientRoom.action_mark_clean_ready() exactly."""
        for rec in self:
            rec.state = 'avail'
            rec.last_cleaned_by = self.env.user.employee_id.id \
                if hasattr(self.env.user, 'employee_id') else False
            rec.last_cleaned_date = fields.Datetime.now()