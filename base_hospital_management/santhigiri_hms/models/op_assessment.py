# -*- coding: utf-8 -*-
"""
Initial Assessment Sheet - OP  (Form No: SAMC/CS/11)
Completely new model — base module and existing santhigiri models had no
vitals / nutritional screening / pain assessment / care plan capture for OP.

One record per OP visit (1-to-1 with hospital.outpatient), created by the
nurse/RMO at the time of consultation and completed by the consultant.
"""
from odoo import api, fields, models
from odoo.exceptions import UserError


class HospitalOPAssessment(models.Model):
    _name = 'hospital.op.assessment'
    _description = 'Initial Assessment Sheet - OP'
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

    # ── Header (Form No: SAMC/CS/11) ──────────────────────────────────────────
    assessment_datetime = fields.Datetime(string='Date & Time', default=fields.Datetime.now,
                                           required=True)
    assessment_date_display = fields.Char(string='Date (Display)',
                                           compute='_compute_datetime_display')
    assessment_time_display = fields.Char(string='Time (Display)',
                                           compute='_compute_datetime_display')
    uhid_no = fields.Char(string='UHID No.')
    cop_no = fields.Char(string='COP No.')
    dop_no = fields.Char(string='DOP No.')
    department_id = fields.Many2one('hr.department', string='Department')

    # ── Vitals ────────────────────────────────────────────────────────────────
    respiratory_rate = fields.Integer(string='Respiratory Rate (breaths/min)')
    heart_rate = fields.Integer(string='Heart Rate (bpm)')
    pulse_rate = fields.Integer(string='Pulse Rate (bpm)')
    height = fields.Float(string='Height (cm)')
    weight = fields.Float(string='Weight (kg)')
    bmi = fields.Float(string='BMI', compute='_compute_bmi', store=True)
    bp = fields.Char(string='BP', help='e.g. 120/80 mmHg')
    temperature = fields.Float(string='Temp. (°F)')
    grbs = fields.Float(string='GRBS (mg/dL)')

    # ── Screening / Assessment ───────────────────────────────────────────────
    nutritional_screening = fields.Selection([
        ('poor', 'Poor'),
        ('moderate', 'Moderate'),
        ('well_nourished', 'Well Nourished'),
        ('obese', 'Obese'),
    ], string='Nutritional Screening')

    complaint_duration = fields.Char(string='Duration of Complaints',
                                      help='e.g. "3 days", "2 weeks"')
    # chief_complaint text already lives on hospital.outpatient — related for convenience
    presenting_complaints = fields.Text(string='Presenting Complaints and Duration',
                                         help='Free text if more detail is needed than the '
                                              'OP Chief Complaint field')

    pain_score = fields.Selection([
        ('0', '0 - No Hurt'),
        ('2', '2 - Hurts Little Bit'),
        ('4', '4 - Hurts Little More'),
        ('6', '6 - Hurts Even More'),
        ('8', '8 - Hurts Whole Lot'),
        ('10', '10 - Hurts Worst'),
    ], string='Pain Assessment')

    current_medication = fields.Text(string='Current Medication')
    treatment_history = fields.Text(string='Treatment History')
    investigations_recommended = fields.Text(string='Investigations Recommended')

    # ── Care Plan Strategy ────────────────────────────────────────────────────
    care_plan_curative = fields.Text(string='Curative')
    care_plan_preventive = fields.Text(string='Preventive')
    care_plan_rehabilitative = fields.Text(string='Rehabilitative')
    care_plan_outcome = fields.Text(string='Care Plan with Desired Outcome')

    # ── Sign-off ──────────────────────────────────────────────────────────────
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed by Consultant'),
    ], default='draft', string='Status', tracking=True)
    consultant_signoff_id = fields.Many2one('hr.employee', string='Consultant (Signature)')
    signoff_date = fields.Date(string='Date')
    signoff_time = fields.Char(string='Time')

    # ── Related read-only views of the linked OP's order lines ────────────────
    prescription_ids = fields.One2many(
        related='outpatient_id.prescription_ids',
        string='Medication Order',
        readonly=True,
    )
    procedure_prescription_ids = fields.One2many(
        related='outpatient_id.procedure_prescription_ids',
        string='Treatment Order',
        readonly=True,
    )

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

    @api.depends('height', 'weight')
    def _compute_bmi(self):
        for rec in self:
            if rec.height and rec.weight:
                h_m = rec.height / 100
                rec.bmi = round(rec.weight / (h_m * h_m), 2)
            else:
                rec.bmi = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'New') == 'New':
                vals['reference'] = self.env['ir.sequence'].next_by_code(
                    'hospital.op.assessment'
                ) or 'IAS/001'
        return super().create(vals_list)

    def action_confirm(self):
        """Consultant confirms/signs off the assessment."""
        for rec in self:
            if not rec.care_plan_outcome:
                raise UserError('Please fill the Care Plan with Desired Outcome '
                                 'before confirming.')
            rec.state = 'confirmed'
            rec.consultant_signoff_id = rec.doctor_id.employee_id.id \
                if rec.doctor_id and rec.doctor_id.employee_id else rec.consultant_signoff_id
            rec.signoff_date = fields.Date.today()

    def action_print(self):
        self.ensure_one()
        return self.env.ref('santhigiri_hms.action_report_op_assessment').report_action(self)


class HospitalOutpatientAssessment(models.Model):
    """Link + smart button + Medication/Treatment order tables on hospital.outpatient."""
    _inherit = 'hospital.outpatient'

    assessment_ids = fields.One2many('hospital.op.assessment', 'outpatient_id',
                                      string='Initial Assessments')
    assessment_count = fields.Integer(string='Assessment Count',
                                       compute='_compute_assessment_count')

    def _compute_assessment_count(self):
        for rec in self:
            rec.assessment_count = len(rec.assessment_ids)

    def action_open_assessment(self):
        """Open existing assessment, or create+open a new one for this OP."""
        self.ensure_one()
        assessment = self.assessment_ids[:1]
        if not assessment:
            assessment = self.env['hospital.op.assessment'].create({
                'outpatient_id': self.id,
            })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Initial Assessment Sheet - OP',
            'res_model': 'hospital.op.assessment',
            'res_id': assessment.id,
            'view_mode': 'form',
            'target': 'current',
        }