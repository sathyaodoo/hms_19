# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class HospitalIPAssessment(models.Model):
    _name = 'hospital.ip.assessment'
    _description = 'Initial Assessment Sheet - IP'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'assessment_datetime desc'
    _rec_name = 'reference'

    # ---------------------------------------------------------
    # Reference and IP Admission
    # ---------------------------------------------------------

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

    medication_plan_ids = fields.One2many(
        related='inpatient_id.medication_plan_ids',
        string='Medication Order',
        readonly=False,
    )

    treatment_plan_ids = fields.One2many(
        related='inpatient_id.treatment_plan_ids',
        string='Treatment Order',
        readonly=False,
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

    department_id = fields.Many2one(
        'hr.department',
        string='Department',
    )

    # ---------------------------------------------------------
    # Assessment Date and Time
    # ---------------------------------------------------------

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

    # ---------------------------------------------------------
    # Vitals
    # ---------------------------------------------------------

    respiratory_rate = fields.Integer(
        string='Respiratory Rate (breaths/min)',
    )

    heart_rate = fields.Integer(
        string='Heart Rate (bpm)',
    )

    pulse_rate = fields.Integer(
        string='Pulse Rate (bpm)',
    )

    bp = fields.Char(
        string='Blood Pressure',
        help='Example: 120/80 mmHg',
    )

    temperature = fields.Float(
        string='Temperature (°F)',
    )

    height = fields.Float(
        string='Height (cm)',
    )

    weight = fields.Float(
        string='Weight (kg)',
    )

    bmi = fields.Float(
        string='BMI',
        compute='_compute_bmi',
        store=True,
    )

    grbs = fields.Float(
        string='GRBS (mg/dL)',
    )

    naadi = fields.Char(
        string='Naadi',
        help='Ayurvedic pulse examination findings',
    )

    # ---------------------------------------------------------
    # Nutritional Screening
    # ---------------------------------------------------------

    nutritional_screening = fields.Selection([
        ('poor', 'Poor'),
        ('moderate', 'Moderate'),
        ('well_nourished', 'Well Nourished'),
        ('obese', 'Obese'),
    ], string='Nutritional Screening')

    # ---------------------------------------------------------
    # Clinical Assessment
    # ---------------------------------------------------------

    complaint_duration = fields.Char(
        string='Duration of Complaints',
    )

    presenting_complaints = fields.Text(
        string='Presenting Complaints',
    )

    pain_score = fields.Selection([
        ('0', '0 - No Hurt'),
        ('2', '2 - Hurts Little Bit'),
        ('4', '4 - Hurts Little More'),
        ('6', '6 - Hurts Even More'),
        ('8', '8 - Hurts Whole Lot'),
        ('10', '10 - Hurts Worst'),
    ], string='Pain Assessment')

    current_medication = fields.Text(
        string='Current Medication',
    )

    treatment_history = fields.Text(
        string='Treatment History',
    )

    investigations_recommended = fields.Text(
        string='Investigations Recommended',
    )

    # ---------------------------------------------------------
    # Care Plan
    # ---------------------------------------------------------

    care_plan_curative = fields.Text(
        string='Curative Care',
    )

    care_plan_preventive = fields.Text(
        string='Preventive Care',
    )

    care_plan_rehabilitative = fields.Text(
        string='Rehabilitative Care',
    )

    care_plan_outcome = fields.Text(
        string='Care Plan with Desired Outcome',
    )

    # ---------------------------------------------------------
    # Consultant Sign-off
    # ---------------------------------------------------------

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

    # ---------------------------------------------------------
    # Display Date and Time
    # ---------------------------------------------------------

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

    # ---------------------------------------------------------
    # Calculate BMI
    # ---------------------------------------------------------

    @api.depends('height', 'weight')
    def _compute_bmi(self):
        for rec in self:
            if rec.height > 0 and rec.weight > 0:
                height_m = rec.height / 100.0
                rec.bmi = round(rec.weight / (height_m * height_m), 2)
            else:
                rec.bmi = 0.0

    # ---------------------------------------------------------
    # One Initial Assessment per IP Admission
    # ---------------------------------------------------------

    _sql_constraints = [
        (
            'unique_inpatient_initial_assessment',
            'UNIQUE(inpatient_id)',
            'Only one Initial Assessment is allowed per IP Admission.',
        ),
    ]

    # ---------------------------------------------------------
    # Create Reference
    # ---------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'New') == 'New':
                vals['reference'] = (
                    self.env['ir.sequence'].next_by_code(
                        'hospital.ip.assessment'
                    ) or 'IPIAS/001'
                )

        return super().create(vals_list)

    # ---------------------------------------------------------
    # Print IP Initial Assessment
    # ---------------------------------------------------------

    def action_print(self):
        self.ensure_one()
        return self.env.ref(
            'santhigiri_hms.action_report_ip_assessment'
        ).report_action(self)

    # ---------------------------------------------------------
    # Confirm Assessment
    # ---------------------------------------------------------

    def action_confirm(self):
        for rec in self:
            if rec.state == 'confirmed':
                continue

            if not rec.care_plan_outcome:
                raise UserError(_(
                    'Please enter the Care Plan with Desired Outcome '
                    'before confirming the assessment.'
                ))

            if not rec.doctor_id:
                raise UserError(_(
                    'Please assign an attending doctor to the IP Admission '
                    'before confirming the assessment.'
                ))

            rec.write({
                'state': 'confirmed',
                'consultant_signoff_id': rec.doctor_id.id,
                'signoff_date': fields.Date.today(),
                'signoff_time': fields.Datetime.context_timestamp(
                    rec, fields.Datetime.now()
                ).strftime('%I:%M %p'),
            })

    # ---------------------------------------------------------
    # Return to Draft
    # ---------------------------------------------------------

    def action_reset_to_draft(self):
        for rec in self:
            rec.write({
                'state': 'draft',
                'consultant_signoff_id': False,
                'signoff_date': False,
                'signoff_time': False,
            })


class HospitalInpatientAssessment(models.Model):
    _inherit = 'hospital.inpatient'

    assessment_ids = fields.One2many(
        'hospital.ip.assessment',
        'inpatient_id',
        string='Initial Assessment',
    )

    assessment_count = fields.Integer(
        string='Assessment Count',
        compute='_compute_assessment_count',
    )

    def _compute_assessment_count(self):
        for rec in self:
            rec.assessment_count = len(rec.assessment_ids)

    def action_open_initial_assessment(self):
        self.ensure_one()

        assessment = self.assessment_ids[:1]

        if not assessment:
            assessment = self.env['hospital.ip.assessment'].create({
                'inpatient_id': self.id,
            })

        return {
            'type': 'ir.actions.act_window',
            'name': 'Initial Assessment - IP',
            'res_model': 'hospital.ip.assessment',
            'res_id': assessment.id,
            'view_mode': 'form',
            'target': 'current',
        }
