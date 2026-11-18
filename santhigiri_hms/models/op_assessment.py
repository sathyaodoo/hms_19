# -*- coding: utf-8 -*-
"""
Initial Assessment Sheet - OP & IP (Form No: SAMC/CS/11 & SAMC/CS/IP/11)
NABH & NCISM standard Initial Assessment capturing vitals, nutritional screening,
pain assessment, care plan strategy, consultant digital signature, and orders
for both Outpatient (OP) visits and Inpatient (IP) admissions.
"""
from odoo import api, fields, models
from odoo.exceptions import UserError


class HospitalOPAssessment(models.Model):
    _name = 'hospital.op.assessment'
    _description = 'Initial Assessment Sheet (OP / IP)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'assessment_datetime desc, id desc'
    _rec_name = 'reference'

    # ── Reference & Linkage ───────────────────────────────────────────────────
    reference = fields.Char(string='Reference', readonly=True, default='New', copy=False)
    assessment_type = fields.Selection([
        ('outpatient', 'Outpatient (OP)'),
        ('inpatient', 'Inpatient (IP)'),
    ], string='Assessment Type', default='outpatient', required=True, tracking=True)

    outpatient_id = fields.Many2one(
        'hospital.outpatient',
        string='OP Visit',
        ondelete='cascade',
        index=True,
    )
    inpatient_id = fields.Many2one(
        'hospital.inpatient',
        string='IP Admission',
        ondelete='cascade',
        index=True,
    )

    patient_id = fields.Many2one(
        'res.partner',
        string='Patient',
        compute='_compute_patient_info',
        store=True,
        readonly=False,
        required=True,
        domain=[('patient_seq', 'not in', ['Employee', 'User', 'New', False])],
    )
    patient_seq = fields.Char(related='patient_id.patient_seq', store=True, string='Patient No.')
    doctor_id = fields.Many2one(
        'hr.employee',
        string='Consultant',
        compute='_compute_patient_info',
        store=True,
        readonly=False,
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        compute='_compute_patient_info',
        store=True,
        readonly=False,
    )

    # ── Header Numbers & Details ──────────────────────────────────────────────
    uhid_no = fields.Char(string='UHID No.', compute='_compute_patient_info', store=True, readonly=False)
    cop_no = fields.Char(string='COP No.', compute='_compute_patient_info', store=True, readonly=False)
    dop_no = fields.Char(string='DOP No.', compute='_compute_patient_info', store=True, readonly=False)
    ip_no = fields.Char(string='IP No.', compute='_compute_patient_info', store=True, readonly=False)

    ward_id = fields.Many2one('hospital.ward', string='Ward', compute='_compute_patient_info', store=True, readonly=False)
    room_id = fields.Many2one('patient.room', string='Room', compute='_compute_patient_info', store=True, readonly=False)
    bed_id = fields.Many2one('hospital.bed', string='Bed', compute='_compute_patient_info', store=True, readonly=False)

    registration_datetime = fields.Datetime(
        string='Date & Time of Registration',
        compute='_compute_patient_info',
        store=True,
        readonly=False,
        help='Date and time when the patient was registered at reception',
    )
    admission_datetime = fields.Datetime(
        string='Date & Time of Admission',
        compute='_compute_patient_info',
        store=True,
        readonly=False,
        help='Date and time when the patient was admitted to IP',
    )

    registration_date_display = fields.Char(
        string='Registration Date (Display)',
        compute='_compute_datetime_display',
    )
    registration_time_display = fields.Char(
        string='Registration Time (Display)',
        compute='_compute_datetime_display',
    )
    admission_date_display = fields.Char(
        string='Admission Date (Display)',
        compute='_compute_datetime_display',
    )
    admission_time_display = fields.Char(
        string='Admission Time (Display)',
        compute='_compute_datetime_display',
    )

    assessment_datetime = fields.Datetime(
        string='Date & Time of Assessment',
        default=fields.Datetime.now,
        required=True,
    )
    assessment_date_display = fields.Char(
        string='Assessment Date (Display)',
        compute='_compute_datetime_display',
    )
    assessment_time_display = fields.Char(
        string='Assessment Time (Display)',
        compute='_compute_datetime_display',
    )

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

    # ── Screening / Clinical Assessment ───────────────────────────────────────
    nutritional_screening = fields.Selection([
        ('poor', 'Poor'),
        ('moderate', 'Moderate'),
        ('well_nourished', 'Well Nourished'),
        ('obese', 'Obese'),
    ], string='Nutritional Screening')

    complaint_duration = fields.Char(
        string='Duration of Complaints',
        help='e.g. "3 days", "2 weeks"',
    )
    presenting_complaints = fields.Text(
        string='Presenting Complaints and Duration',
        help='Free text detail of presenting complaints',
    )

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
    consultant_signoff_id = fields.Many2one('hr.employee', string='Consultant')
    consultant_signature = fields.Binary(
        string='Consultant Signature',
        attachment=True,
        help='Digital signature of the consultant',
    )
    signoff_date = fields.Date(string='Date')
    signoff_time = fields.Char(string='Time')

    # ── Order Lines (Editable in Assessment and synchronized with OP / IP) ─────
    prescription_ids = fields.One2many(
        'prescription.line',
        'assessment_id',
        string='Medication Order',
    )
    procedure_prescription_ids = fields.One2many(
        'hospital.procedure.prescription',
        'assessment_id',
        string='Treatment Order (OP)',
    )
    treatment_plan_ids = fields.One2many(
        'hospital.treatment.plan',
        'assessment_id',
        string='Treatment Plan (IP)',
    )

    # ── Computes & Onchanges ──────────────────────────────────────────────────
    @api.depends('assessment_type', 'outpatient_id', 'inpatient_id')
    def _compute_patient_info(self):
        for rec in self:
            if rec.inpatient_id:
                ip = rec.inpatient_id
                rec.patient_id = ip.patient_id
                rec.doctor_id = ip.attending_doctor_id or ip.operating_doctor_id
                rec.department_id = getattr(ip, 'department_id', False) or (ip.attending_doctor_id.department_id if ip.attending_doctor_id else False)
                rec.uhid_no = ip.patient_id.uhid_no or False
                rec.cop_no = getattr(ip, 'cop_no', False) or False
                rec.dop_no = getattr(ip, 'dop_no', False) or False
                rec.ip_no = ip.name
                rec.ward_id = ip.ward_id
                rec.room_id = ip.room_id
                rec.bed_id = ip.bed_id
                rec.admission_datetime = fields.Datetime.to_datetime(ip.hosp_date) if ip.hosp_date else False
                rec.registration_datetime = ip.patient_id.registration_datetime or rec.admission_datetime
            elif rec.outpatient_id:
                op = rec.outpatient_id
                rec.patient_id = op.patient_id
                # In base_hospital_management, op.doctor_id is doctor.allocation which wraps hr.employee
                doc = False
                if op.doctor_id and hasattr(op.doctor_id, 'doctor_id') and op.doctor_id.doctor_id:
                    doc = op.doctor_id.doctor_id
                elif op.doctor_id and getattr(op.doctor_id, '_name', '') == 'hr.employee':
                    doc = op.doctor_id
                rec.doctor_id = doc
                rec.department_id = op.department_id or (doc.department_id if doc else False)
                rec.uhid_no = op.uhid_no
                rec.cop_no = op.cop_no
                rec.dop_no = op.dop_no
                rec.ip_no = False
                rec.ward_id = False
                rec.room_id = False
                rec.bed_id = False
                rec.admission_datetime = False
                rec.registration_datetime = op.registration_datetime
            elif rec.patient_id:
                p = rec.patient_id
                rec.uhid_no = p.uhid_no or False
                rec.cop_no = getattr(p, 'cop_no', False) or False
                rec.dop_no = getattr(p, 'dop_no', False) or False
                rec.registration_datetime = p.registration_datetime or False

    @api.onchange('inpatient_id')
    def _onchange_inpatient_id(self):
        if self.inpatient_id:
            self.assessment_type = 'inpatient'
            self._compute_patient_info()

    @api.onchange('outpatient_id')
    def _onchange_outpatient_id(self):
        if self.outpatient_id:
            self.assessment_type = 'outpatient'
            self._compute_patient_info()

    def _sync_linked_orders(self):
        """Link unlinked prescriptions and procedures from linked OP or IP to this assessment."""
        for rec in self:
            if not rec.id:
                continue
            if rec.outpatient_id:
                unlinked_presc = self.env['prescription.line'].sudo().search([
                    ('outpatient_id', '=', rec.outpatient_id.id),
                    ('assessment_id', '=', False),
                ])
                if unlinked_presc:
                    unlinked_presc.write({'assessment_id': rec.id})

                unlinked_proc = self.env['hospital.procedure.prescription'].sudo().search([
                    ('outpatient_id', '=', rec.outpatient_id.id),
                    ('assessment_id', '=', False),
                ])
                if unlinked_proc:
                    unlinked_proc.write({'assessment_id': rec.id})

            if rec.inpatient_id:
                unlinked_ip_presc = self.env['prescription.line'].sudo().search([
                    ('inpatient_id', '=', rec.inpatient_id.id),
                    ('assessment_id', '=', False),
                ])
                if unlinked_ip_presc:
                    unlinked_ip_presc.write({'assessment_id': rec.id})

                unlinked_plans = self.env['hospital.treatment.plan'].sudo().search([
                    ('inpatient_id', '=', rec.inpatient_id.id),
                    ('assessment_id', '=', False),
                ])
                if unlinked_plans:
                    unlinked_plans.write({'assessment_id': rec.id})

    def _sync_child_record_links(self):
        """Ensure lines added inside assessment inherit outpatient_id, inpatient_id, and patient_id."""
        for rec in self:
            if not rec.id:
                continue
            if rec.outpatient_id:
                rec.prescription_ids.filtered(lambda l: not l.outpatient_id).sudo().write({
                    'outpatient_id': rec.outpatient_id.id,
                })
                rec.procedure_prescription_ids.filtered(lambda p: not p.outpatient_id).sudo().write({
                    'outpatient_id': rec.outpatient_id.id,
                })
            if rec.inpatient_id:
                rec.prescription_ids.filtered(lambda l: not l.inpatient_id).sudo().write({
                    'inpatient_id': rec.inpatient_id.id,
                })
                rec.treatment_plan_ids.filtered(lambda t: not t.inpatient_id).sudo().write({
                    'inpatient_id': rec.inpatient_id.id,
                })
            if rec.patient_id:
                rec.prescription_ids.filtered(lambda l: not l.res_partner_id).sudo().write({
                    'res_partner_id': rec.patient_id.id,
                })
                rec.procedure_prescription_ids.filtered(lambda p: not p.patient_id).sudo().write({
                    'patient_id': rec.patient_id.id,
                })

    @api.depends('assessment_datetime', 'registration_datetime', 'admission_datetime')
    def _compute_datetime_display(self):
        for rec in self:
            if rec.assessment_datetime:
                local_dt = fields.Datetime.context_timestamp(rec, rec.assessment_datetime)
                rec.assessment_date_display = local_dt.strftime('%d-%m-%Y')
                rec.assessment_time_display = local_dt.strftime('%I:%M %p')
            else:
                rec.assessment_date_display = ''
                rec.assessment_time_display = ''

            if rec.registration_datetime:
                reg_dt = fields.Datetime.context_timestamp(rec, rec.registration_datetime)
                rec.registration_date_display = reg_dt.strftime('%d-%m-%Y')
                rec.registration_time_display = reg_dt.strftime('%I:%M %p')
            else:
                rec.registration_date_display = ''
                rec.registration_time_display = ''

            if rec.admission_datetime:
                adm_dt = fields.Datetime.context_timestamp(rec, rec.admission_datetime)
                rec.admission_date_display = adm_dt.strftime('%d-%m-%Y')
                rec.admission_time_display = adm_dt.strftime('%I:%M %p')
            else:
                rec.admission_date_display = ''
                rec.admission_time_display = ''

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
                prefix = 'hospital.op.assessment'
                vals['reference'] = self.env['ir.sequence'].next_by_code(prefix) or 'IAS/001'
        records = super().create(vals_list)
        for rec in records:
            rec._sync_linked_orders()
            rec._sync_child_record_links()
        return records

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            rec._sync_child_record_links()
        return res

    def read(self, fields=None, load='_classic_read'):
        self._sync_linked_orders()
        return super().read(fields=fields, load=load)

    def action_confirm(self):
        """Consultant confirms and signs off the assessment."""
        for rec in self:
            if not rec.care_plan_outcome:
                raise UserError('Please fill the Care Plan with Desired Outcome before confirming.')
            rec.state = 'confirmed'
            consultant = False
            if rec.doctor_id and hasattr(rec.doctor_id, 'doctor_id') and rec.doctor_id.doctor_id:
                consultant = rec.doctor_id.doctor_id
            elif rec.doctor_id:
                consultant = rec.doctor_id
            elif self.env.user.employee_id:
                consultant = self.env.user.employee_id
            if consultant:
                rec.consultant_signoff_id = consultant.id
            rec.signoff_date = fields.Date.today()
            local_now = fields.Datetime.context_timestamp(rec, fields.Datetime.now())
            rec.signoff_time = local_now.strftime('%I:%M %p')

    def action_print(self):
        self.ensure_one()
        return self.env.ref('santhigiri_hms.action_report_op_assessment').report_action(self)

    def action_open_inpatient(self):
        """Open related Inpatient / Outpatient Case Sheet."""
        self.ensure_one()
        if self.inpatient_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Inpatient',
                'res_model': 'hospital.inpatient',
                'res_id': self.inpatient_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        elif self.outpatient_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Outpatient',
                'res_model': 'hospital.outpatient',
                'res_id': self.outpatient_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        else:
            ip = self.env['hospital.inpatient'].search([
                ('patient_id', '=', self.patient_id.id),
                ('state', 'not in', ['dis', 'cancel']),
            ], order='id desc', limit=1)
            if ip:
                return {
                    'type': 'ir.actions.act_window',
                    'name': 'Inpatient',
                    'res_model': 'hospital.inpatient',
                    'res_id': ip.id,
                    'view_mode': 'form',
                    'target': 'current',
                }
            raise UserError("No Inpatient admission record found.")


class HospitalOutpatientAssessment(models.Model):
    """Link + smart button on hospital.outpatient."""
    _inherit = 'hospital.outpatient'

    assessment_ids = fields.One2many(
        'hospital.op.assessment',
        'outpatient_id',
        string='Initial Assessments',
    )
    assessment_count = fields.Integer(
        string='Assessment Count',
        compute='_compute_assessment_count',
    )

    def _compute_assessment_count(self):
        for rec in self:
            rec.assessment_count = len(rec.assessment_ids)

    def action_open_assessment(self):
        """Open existing assessment, or create+open a new one for this OP."""
        self.ensure_one()
        assessment = self.assessment_ids[:1]
        if not assessment:
            assessment = self.env['hospital.op.assessment'].create({
                'assessment_type': 'outpatient',
                'outpatient_id': self.id,
                'patient_id': self.patient_id.id,
            })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Initial Assessment Sheet - OP',
            'res_model': 'hospital.op.assessment',
            'res_id': assessment.id,
            'view_mode': 'form',
            'target': 'current',
        }
