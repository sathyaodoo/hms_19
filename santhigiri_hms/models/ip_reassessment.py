# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HospitalIPReassessment(models.Model):
    _name = 'hospital.ip.reassessment'
    _description = 'IP Reassessment Chart'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'assessment_datetime desc'
    _rec_name = 'reference'

    reference = fields.Char(
        string='Reference',
        readonly=True,
        copy=False,
        default='New',
        tracking=True,
    )

    inpatient_id = fields.Many2one(
        'hospital.inpatient',
        string='IP Admission',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True,
    )

    patient_id = fields.Many2one(
        related='inpatient_id.patient_id',
        string='Patient',
        store=True,
        readonly=True,
    )

    patient_seq = fields.Char(
        related='patient_id.patient_seq',
        string='Patient No.',
        store=True,
        readonly=True,
    )

    doctor_id = fields.Many2one(
        related='inpatient_id.attending_doctor_id',
        string='Consultant',
        store=True,
        readonly=True,
    )

    assessment_datetime = fields.Datetime(
        string='Assessment Date & Time',
        default=fields.Datetime.now,
        required=True,
        tracking=True,
    )

    assessment_date_display = fields.Char(
        string='Date',
        compute='_compute_datetime_display',
    )

    assessment_time_display = fields.Char(
        string='Time',
        compute='_compute_datetime_display',
    )

    uhid_no = fields.Char(string='UHID No.')
    cop_no = fields.Char(string='COP No.')
    dop_no = fields.Char(string='DOP No.')

    bp = fields.Char(string='Blood Pressure')
    pulse_rate = fields.Integer(string='Pulse Rate (bpm)')
    respiratory_rate = fields.Integer(string='Respiratory Rate (breaths/min)')
    heart_rate = fields.Integer(string='Heart Rate (bpm)')
    temperature = fields.Float(string='Temperature (°F)')
    grbs = fields.Float(string='GRBS (mg/dL)')
    naadi = fields.Char(string='Naadi')

    prescription_ids = fields.One2many(
        'prescription.line',
        'ip_reassessment_id',
        string='Medication',
    )

    patient_condition = fields.Text(string='Patient Condition')
    clinical_findings = fields.Text(string='Clinical Findings')
    complaints = fields.Text(string='Current Complaints')
    treatment_given = fields.Text(string='Treatment / Advice')
    care_plan = fields.Text(string='Further Care Plan')
    remarks = fields.Text(string='Remarks')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed by Consultant'),
    ], string='Status', default='draft', required=True, tracking=True)

    consultant_signoff_id = fields.Many2one(
        'hr.employee',
        string='Consultant Signature',
        readonly=True,
    )

    signoff_date = fields.Date(
        string='Sign-off Date',
        readonly=True,
    )

    signoff_time = fields.Char(
        string='Sign-off Time',
        readonly=True,
    )

    @api.depends('assessment_datetime')
    def _compute_datetime_display(self):
        for rec in self:
            if rec.assessment_datetime:
                local_dt = fields.Datetime.context_timestamp(
                    rec, rec.assessment_datetime
                )
                rec.assessment_date_display = local_dt.strftime('%d-%m-%Y')
                rec.assessment_time_display = local_dt.strftime('%I:%M %p')
            else:
                rec.assessment_date_display = ''
                rec.assessment_time_display = ''

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'New') == 'New':
                vals['reference'] = (
                    self.env['ir.sequence'].next_by_code(
                        'hospital.ip.reassessment'
                    ) or 'IPREASS/001'
                )
        return super().create(vals_list)

    def action_confirm(self):
        for rec in self:
            if rec.state == 'confirmed':
                continue

            if not rec.doctor_id:
                raise UserError(_(
                    'Please assign an attending doctor to the IP Admission '
                    'before confirming the reassessment.'
                ))

            rec.write({
                'state': 'confirmed',
                'consultant_signoff_id': rec.doctor_id.id,
                'signoff_date': fields.Date.today(),
                'signoff_time': fields.Datetime.context_timestamp(
                    rec, fields.Datetime.now()
                ).strftime('%I:%M %p'),
            })

    def action_reset_to_draft(self):
        for rec in self:
            rec.write({
                'state': 'draft',
                'consultant_signoff_id': False,
                'signoff_date': False,
                'signoff_time': False,
            })

    def action_print(self):
        self.ensure_one()
        return self.env.ref(
            'santhigiri_hms.action_report_ip_reassessment'
        ).report_action(self)


class HospitalInpatientReassessment(models.Model):
    _inherit = 'hospital.inpatient'

    ip_reassessment_ids = fields.One2many(
        'hospital.ip.reassessment',
        'inpatient_id',
        string='IP Reassessments',
    )

    ip_reassessment_count = fields.Integer(
        string='IP Reassessment Count',
        compute='_compute_ip_reassessment_count',
    )

    def _compute_ip_reassessment_count(self):
        for rec in self:
            rec.ip_reassessment_count = len(rec.ip_reassessment_ids)

    def action_open_ip_reassessment(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'IP Reassessment',
            'res_model': 'hospital.ip.reassessment',
            'view_mode': 'list,form',
            'domain': [('inpatient_id', '=', self.id)],
            'context': {
                'default_inpatient_id': self.id,
            },
        }
