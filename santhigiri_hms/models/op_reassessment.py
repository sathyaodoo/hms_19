# -*- coding: utf-8 -*-
"""
OP Reassessment Chart  (Form No: SAMC/CS/14)
Completely new model — used for repeat/follow-up visits during an OP's
treatment course (unlike hospital.op.assessment, which is filled only ONCE
at the first consultation). One OP visit can have MANY reassessment records
over time (e.g. every few days during a Daily Procedures course).
"""
from odoo import api, fields, models
from odoo.exceptions import UserError


class HospitalOPReassessment(models.Model):
    _name = 'hospital.op.reassessment'
    _description = 'OP Reassessment Chart'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'assessment_datetime desc'
    _rec_name = 'reference'

    # ── Reference & linkage ───────────────────────────────────────────────────
    reference = fields.Char(string='Reference', readonly=True, default='New', copy=False)
    outpatient_id = fields.Many2one('hospital.outpatient', string='OP Visit',
                                     required=True, ondelete='cascade', index=True)
    patient_id = fields.Many2one(related='outpatient_id.patient_id', store=True,
                                  string='Patient')
    patient_seq = fields.Char(related='patient_id.patient_seq', store=True, string='Patient No.')
    doctor_id = fields.Many2one(related='outpatient_id.doctor_id', store=True,
                                 string='Consultant')
    # Optional — set when this reassessment was prompted by a scheduled follow-up
    followup_id = fields.Many2one('hospital.followup', string='Related Follow-Up')

    # ── Header (Form No: SAMC/CS/14) ──────────────────────────────────────────
    assessment_datetime = fields.Datetime(string='Date & Time', default=fields.Datetime.now,
                                           required=True)
    assessment_date_display = fields.Char(string='Date (Display)',
                                           compute='_compute_datetime_display')
    assessment_time_display = fields.Char(string='Time (Display)',
                                           compute='_compute_datetime_display')
    uhid_no = fields.Char(string='UHID No.')
    cop_no = fields.Char(string='COP No.')
    dop_no = fields.Char(string='DOP No.')

    # ── Observations ──────────────────────────────────────────────────────────
    bp = fields.Char(string='BP', help='e.g. 120/80 mmHg')
    pr = fields.Integer(string='PR (Pulse Rate, bpm)')
    naadi = fields.Char(string='Naadi', help='Ayurvedic pulse (Naadi Pariksha) findings')

    # ── Medication with Route/Dose/Time/Duration/Anupana/Pathya-Apathya ───────
    prescription_ids = fields.One2many('prescription.line', 'reassessment_id',
                                        string='Medication')

    # ── Sign-off ──────────────────────────────────────────────────────────────
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed by Consultant'),
    ], default='draft', string='Status', tracking=True)
    consultant_signoff_id = fields.Many2one('hr.employee', string='Consultant (Signature)')
    signoff_date = fields.Date(string='Date')
    signoff_time = fields.Char(string='Time')

    @api.depends('assessment_datetime')
    def _compute_datetime_display(self):
        for rec in self:
            if rec.assessment_datetime:
                local_dt = fields.Datetime.context_timestamp(rec, rec.assessment_datetime)
                rec.assessment_date_display = local_dt.strftime('%d-%m-%Y')
                rec.assessment_time_display = local_dt.strftime('%I:%M %p')
            else:
                rec.assessment_date_display = ''
                rec.assessment_time_display = ''

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'New') == 'New':
                vals['reference'] = self.env['ir.sequence'].next_by_code(
                    'hospital.op.reassessment'
                ) or 'REASS/001'
        return super().create(vals_list)

    def action_confirm(self):
        for rec in self:
            rec.state = 'confirmed'
            rec.consultant_signoff_id = rec.doctor_id.employee_id.id \
                if rec.doctor_id and rec.doctor_id.employee_id else rec.consultant_signoff_id
            rec.signoff_date = fields.Date.today()
            if rec.followup_id:
                rec.followup_id.action_mark_attended()

    def action_print(self):
        self.ensure_one()
        return self.env.ref('santhigiri_hms.action_report_op_reassessment').report_action(self)


class HospitalOutpatientReassessment(models.Model):
    """Link + smart button on hospital.outpatient."""
    _inherit = 'hospital.outpatient'

    reassessment_ids = fields.One2many('hospital.op.reassessment', 'outpatient_id',
                                        string='Reassessments')
    reassessment_count = fields.Integer(string='Reassessment Count',
                                         compute='_compute_reassessment_count')

    def _compute_reassessment_count(self):
        for rec in self:
            rec.reassessment_count = len(rec.reassessment_ids)

    def action_open_reassessment(self):
        """Open the list of reassessments; create a new one via the '+' in the list."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'OP Reassessment Chart',
            'res_model': 'hospital.op.reassessment',
            'view_mode': 'list,form',
            'domain': [('outpatient_id', '=', self.id)],
            'context': {'default_outpatient_id': self.id},
        }