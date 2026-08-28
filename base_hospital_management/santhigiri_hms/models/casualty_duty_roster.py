# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class CasualtyDutyRoster(models.Model):
    _name = 'casualty.duty.roster'
    _description = 'Intern Casualty Duty Roster'
    _inherit = ['mail.thread']
    _order = 'duty_date desc, session'

    duty_date = fields.Date(string='Duty Date', required=True)
    session = fields.Selection([
        ('morning', 'Morning (6 AM – 2 PM)'),
        ('evening', 'Evening (2 PM – 10 PM)'),
        ('night', 'Night (10 PM – 6 AM)'),
    ], string='Session', required=True)
    intern_ids = fields.Many2many(
        'hospital.intern',
        'roster_intern_rel',
        'roster_id',
        'intern_id',
        string='Assigned Interns',
        required=True,
    )
    assigned_by = fields.Many2one(
        'hr.employee',
        string='Assigned By',
        default=lambda s: s.env.user.employee_id if hasattr(s.env.user, 'employee_id') else False,
    )
    notes = fields.Text(string='Instructions / Notes')
    state = fields.Selection([('draft', 'Draft'), ('published', 'Published')],
                              default='draft', tracking=True)

    @api.constrains('intern_ids', 'duty_date', 'session')
    def _check_duplicate_duty(self):
        for rec in self:
            for intern in rec.intern_ids:
                dup = self.search([
                    ('duty_date', '=', rec.duty_date),
                    ('session', '=', rec.session),
                    ('intern_ids', 'in', intern.id),
                    ('id', '!=', rec.id),
                ])
                if dup:
                    raise ValidationError(
                        f'Intern {intern.partner_id.name} is already assigned to '
                        f'{rec.duty_date} {rec.session} session.'
                    )

    def action_publish(self):
        for rec in self:
            rec.state = 'published'
            # Notify assigned interns
            for intern in rec.intern_ids:
                if intern.partner_id.email:
                    self.env['mail.mail'].create({
                        'subject': f'Casualty Duty Assigned — {rec.duty_date}',
                        'body_html': (
                            f'<p>Dear {intern.partner_id.name},</p>'
                            f'<p>You have been assigned to Casualty Duty on '
                            f'<b>{rec.duty_date}</b> — <b>{rec.session}</b> session.</p>'
                            f'<p>Please report on time.</p>'
                        ),
                        'email_to': intern.partner_id.email,
                    }).send()
