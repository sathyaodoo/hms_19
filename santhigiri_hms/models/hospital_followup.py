# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HospitalFollowup(models.Model):
    _name = 'hospital.followup'
    _description = 'Patient Follow-Up'
    _order = 'followup_date'
    _inherit = ['mail.thread']

    patient_id = fields.Many2one('res.partner', string='Patient', required=True,
                                  domain=[('patient_seq', '!=', False)], index=True)
    followup_date = fields.Date(string='Follow-Up Date', required=True)
    reason = fields.Text(string='Reason / Instructions')
    advised_by = fields.Many2one('hr.employee', string='Advised By')
    source_op_id = fields.Many2one('hospital.outpatient', string='Source OP Visit')
    source_ip_id = fields.Many2one('hospital.inpatient', string='Source IP Admission')
    status = fields.Selection([
        ('pending', 'Pending'),
        ('attended', 'Attended'),
        ('missed', 'Missed / Not Attended'),
        ('rescheduled', 'Rescheduled'),
    ], default='pending', tracking=True)
    rescheduled_to = fields.Date(string='Rescheduled To')
    notes = fields.Text(string='Notes on Visit')

    # ── Auto-fill patient_id from source records ───────────────────────────────
    @api.onchange('source_ip_id')
    def _onchange_source_ip(self):
        if self.source_ip_id and self.source_ip_id.patient_id:
            self.patient_id = self.source_ip_id.patient_id

    @api.onchange('source_op_id')
    def _onchange_source_op(self):
        if self.source_op_id and self.source_op_id.patient_id:
            self.patient_id = self.source_op_id.patient_id

    @api.model_create_multi
    def create(self, vals_list):
        """Auto-fill patient_id from source if not set."""
        for vals in vals_list:
            if not vals.get('patient_id'):
                if vals.get('source_ip_id'):
                    ip = self.env['hospital.inpatient'].browse(vals['source_ip_id'])
                    if ip.patient_id:
                        vals['patient_id'] = ip.patient_id.id
                elif vals.get('source_op_id'):
                    op = self.env['hospital.outpatient'].browse(vals['source_op_id'])
                    if op.patient_id:
                        vals['patient_id'] = op.patient_id.id
        return super().create(vals_list)

    def action_mark_attended(self):
        self.status = 'attended'

    def action_mark_missed(self):
        self.status = 'missed'

    @api.model
    def _cron_send_followup_reminders(self):
        from datetime import timedelta
        today = fields.Date.today()
        reminder_date = today + timedelta(days=2)
        due = self.search([('followup_date', '=', reminder_date), ('status', '=', 'pending')])
        for rec in due:
            if rec.patient_id.email:
                self.env['mail.mail'].create({
                    'subject': 'Follow-Up Appointment Reminder',
                    'body_html': (
                        '<p>Dear ' + rec.patient_id.name + ',</p>'
                        '<p>This is a reminder for your follow-up on '
                        '<b>' + str(rec.followup_date) + '</b>.</p>'
                        '<p>Instructions: ' + (rec.reason or 'Please visit the hospital.') + '</p>'
                    ),
                    'email_to': rec.patient_id.email,
                }).send()

    @api.model
    def _cron_mark_missed_followups(self):
        today = fields.Date.today()
        past = self.search([('followup_date', '<', today), ('status', '=', 'pending')])
        past.write({'status': 'missed'})