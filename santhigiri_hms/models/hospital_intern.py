# -*- coding: utf-8 -*-
"""
Internship Management — completely new module.
BASE MODULE has no internship/student tracking.
Covers FRD 21.1–21.9: Intern master, rotation, attendance, ward round,
OP observation, casualty attendance, case log, HOD/DMS review, completion report.
"""
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HospitalIntern(models.Model):
    _name = 'hospital.intern'
    _description = 'Medical Intern / Student'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'
    _rec_name = 'name'

    name = fields.Char(string='Intern Name', required=True)
    intern_seq = fields.Char(string='Intern ID', readonly=True, default='New', copy=False)
    partner_id = fields.Many2one('res.partner', string='Partner / Contact',
                                  help='Link to Odoo contact for email and login')
    user_id = fields.Many2one('res.users', string='Odoo User Account',
                               help='Link intern profile to their Odoo login account')
    aadhaar_no = fields.Char(string='Aadhaar Number')
    college_id = fields.Char(string='College / Institution', required=True)
    college_register_no = fields.Char(string='College Register No.', required=True)
    university_reg_no = fields.Char(string='University Registration No.', required=True)
    medical_council_reg_no = fields.Char(string='Medical Council Reg. No.')
    batch = fields.Char(string='Batch / Year of Study')
    course = fields.Selection([
        ('bams', 'BAMS (Bachelor of Ayurvedic Medicine & Surgery)'),
        ('md_ayurveda', 'MD Ayurveda'),
        ('ms_ayurveda', 'MS Ayurveda'),
        ('phd', 'PhD'),
        ('other', 'Other'),
    ], string='Course', default='bams')
    phone = fields.Char(string='Mobile')
    email = fields.Char(string='Email')

    # Rotation & Supervisor
    current_dept_id = fields.Many2one('hr.department', string='Current Department')
    rotation_start = fields.Date(string='Rotation Start Date')
    rotation_end = fields.Date(string='Rotation End Date')
    supervisor_hod_id = fields.Many2one('hr.employee', string='Supervisor / HOD')
    approved_by = fields.Many2one('hr.employee', string='Approved By (DMS/Superintendent)')

    # Related records
    rotation_ids = fields.One2many('hospital.intern.rotation', 'intern_id', string='Rotation Schedule')
    attendance_ids = fields.One2many('hospital.intern.attendance', 'intern_id', string='Attendance')
    case_log_ids = fields.One2many('hospital.case.log', 'intern_id', string='Case Log')
    review_ids = fields.One2many('hospital.intern.review', 'intern_id', string='Monthly Reviews')
    ward_round_ids = fields.One2many('hospital.intern.ward.round', 'intern_id', string='Ward Round Logs')

    # Computed stats
    total_attendance = fields.Integer(string='Days Present', compute='_compute_attendance_stats', store=True)
    attendance_pct = fields.Float(string='Attendance %', compute='_compute_attendance_stats', store=True)
    total_cases = fields.Integer(string='Total Cases', compute='_compute_case_stats', store=True)

    state = fields.Selection([
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('withdrawn', 'Withdrawn'),
    ], default='active', tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('intern_seq', 'New') == 'New':
                vals['intern_seq'] = self.env['ir.sequence'].next_by_code('hospital.intern') or 'INT/001'
        return super().create(vals_list)

    @api.depends('attendance_ids', 'attendance_ids.status')
    def _compute_attendance_stats(self):
        for rec in self:
            present = rec.attendance_ids.filtered(lambda a: a.status == 'present')
            total = len(rec.attendance_ids)
            rec.total_attendance = len(present)
            rec.attendance_pct = (len(present) / total * 100) if total else 0.0

    @api.depends('case_log_ids')
    def _compute_case_stats(self):
        for rec in self:
            rec.total_cases = len(rec.case_log_ids)

    @api.model
    def action_my_attendance(self):
        """Opens current user's intern profile for Check In/Out."""
        user = self.env.user
        intern = None

        # Try 1: via user_id field (most reliable)
        intern = self.search([('user_id', '=', user.id)], limit=1)

        # Try 2: via partner_id
        if not intern and user.partner_id:
            intern = self.search([
                ('partner_id', '=', user.partner_id.id)
            ], limit=1)

        # Try 3: via exact name
        if not intern:
            intern = self.search([('name', '=', user.name)], limit=1)

        # Try 4: via partial name
        if not intern:
            intern = self.search([('name', 'ilike', user.name)], limit=1)

        if not intern:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Profile Not Found',
                    'message': f'No intern profile linked to "{user.name}". '
                               f'Ask admin: Internship → Intern Profiles → '
                               f'[Your Profile] → set "Odoo User Account" field.',
                    'type': 'danger',
                    'sticky': True,
                }
            }
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hospital.intern',
            'res_id': intern.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_check_in(self):
        """Intern clicks Check In on arrival."""
        self.ensure_one()
        today = fields.Date.today()
        now = fields.Datetime.now()
        existing = self.attendance_ids.filtered(lambda a: a.date == today)
        if existing:
            if existing[0].check_in:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Already Checked In',
                        'message': f'Check-in already recorded at {existing[0].check_in}',
                        'type': 'warning',
                    }
                }
            existing[0].write({'check_in': now, 'status': 'present'})
        else:
            self.env['hospital.intern.attendance'].create({
                'intern_id': self.id,
                'date': today,
                'check_in': now,
                'status': 'present',
            })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Checked In ✓',
                'message': f'Check-in recorded at {now.strftime("%H:%M")}',
                'type': 'success',
            }
        }

    def action_check_out(self):
        """Intern clicks Check Out on departure."""
        self.ensure_one()
        today = fields.Date.today()
        now = fields.Datetime.now()
        existing = self.attendance_ids.filtered(lambda a: a.date == today)
        if not existing or not existing[0].check_in:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Not Checked In',
                    'message': 'Please check in first before checking out.',
                    'type': 'danger',
                }
            }
        existing[0].write({'check_out': now})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Checked Out ✓',
                'message': f'Check-out recorded at {now.strftime("%H:%M")}',
                'type': 'success',
            }
        }

    def action_mark_today_present(self):
        """Quick button — intern clicks to mark today as Present."""
        self.ensure_one()
        today = fields.Date.today()
        existing = self.attendance_ids.filtered(lambda a: a.date == today)
        if existing:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Already Marked',
                    'message': f'Attendance already recorded for today ({today})',
                    'type': 'warning',
                }
            }
        self.env['hospital.intern.attendance'].create({
            'intern_id': self.id,
            'date': today,
            'check_in': fields.Datetime.now(),
            'status': 'present',
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Attendance Marked',
                'message': f'Present marked for {today}',
                'type': 'success',
            }
        }

    def action_mark_today_absent(self):
        """HOD/Supervisor marks intern absent for today."""
        self.ensure_one()
        today = fields.Date.today()
        existing = self.attendance_ids.filtered(lambda a: a.date == today)
        if existing:
            existing.write({'status': 'absent'})
        else:
            self.env['hospital.intern.attendance'].create({
                'intern_id': self.id,
                'date': today,
                'status': 'absent',
            })

    def action_print_completion_report(self):
        return self.env.ref('santhigiri_hms.action_report_intern_completion').report_action(self)


class HospitalInternRotation(models.Model):
    _name = 'hospital.intern.rotation'
    _description = 'Intern Department Rotation Schedule'
    _order = 'start_date'

    intern_id = fields.Many2one('hospital.intern', required=True, ondelete='cascade', index=True)
    dept_id = fields.Many2one('hr.department', string='Department', required=True)
    start_date = fields.Date(string='Start Date', required=True)
    end_date = fields.Date(string='End Date', required=True)
    supervisor_id = fields.Many2one('hr.employee', string='Supervisor / HOD')
    approved_by = fields.Many2one('hr.employee', string='Approved By (DMS)')
    status = fields.Selection([
        ('upcoming', 'Upcoming'),
        ('active', 'Active'),
        ('completed', 'Completed'),
    ], compute='_compute_status', store=True)
    notes = fields.Text(string='Notes')

    @api.depends('start_date', 'end_date')
    def _compute_status(self):
        today = fields.Date.today()
        for rec in self:
            if rec.end_date and rec.end_date < today:
                rec.status = 'completed'
            elif rec.start_date and rec.start_date <= today:
                rec.status = 'active'
            else:
                rec.status = 'upcoming'

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for rec in self:
            if rec.start_date and rec.end_date and rec.end_date < rec.start_date:
                raise ValidationError('End date must be after start date.')


class HospitalInternAttendance(models.Model):
    _name = 'hospital.intern.attendance'
    _description = 'Intern Daily Attendance'
    _order = 'date desc'

    intern_id = fields.Many2one('hospital.intern', required=True, ondelete='cascade', index=True)
    date = fields.Date(string='Date', required=True, default=fields.Date.today)
    check_in = fields.Datetime(string='Check In')
    check_out = fields.Datetime(string='Check Out')
    status = fields.Selection([
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('leave', 'On Leave'),
        ('half_day', 'Half Day'),
    ], string='Status', required=True, default='present')
    confirmed_by = fields.Many2one('hr.employee', string='Confirmed By (HOD/Supervisor)')
    notes = fields.Char(string='Notes')

    _sql_constraints = [
        ('unique_intern_date', 'UNIQUE(intern_id, date)',
         'Attendance already recorded for this intern on this date.'),
    ]


class HospitalCaseLog(models.Model):
    _name = 'hospital.case.log'
    _description = 'Intern Clinical Case Log'
    _order = 'date desc'

    intern_id = fields.Many2one('hospital.intern', string='Intern', required=True,
                                 ondelete='cascade', index=True)
    date = fields.Date(string='Date', required=True, default=fields.Date.today)
    source = fields.Selection([
        ('ward_round', 'Ward Round (IP Patient)'),
        ('op_observation', 'OP Observation'),
        ('casualty', 'Casualty Attendance'),
        ('procedure', 'Procedure / Therapy'),
        ('other', 'Other'),
    ], string='Case Source', required=True)
    case_type = fields.Selection([
        ('general', 'General Medicine'),
        ('surgical', 'Surgical'),
        ('paediatrics', 'Paediatrics'),
        ('gynaecology', 'Gynaecology / Obstetrics'),
        ('panchakarma', 'Panchakarma'),
        ('yoga', 'Yoga / Sujok'),
        ('orthopaedic', 'Orthopaedic'),
        ('other', 'Other'),
    ], string='Case Type', required=True, default='general')
    exposure_type = fields.Selection([
        ('observed', 'Observed'),
        ('assisted', 'Assisted'),
        ('performed', 'Performed under Supervision'),
    ], string='Exposure Type', required=True, default='observed')
    summary = fields.Char(string='Case Summary')
    supervisor_id = fields.Many2one('hr.employee', string='Supervisor')
    supervisor_remarks = fields.Text(string='Supervisor Remarks')
    intern_notes = fields.Text(string='Intern Notes')
    is_signed_off = fields.Boolean(string='Supervisor Sign-Off', default=False)
    signed_off_date = fields.Date(string='Signed Off On')

    # Source references
    inpatient_id = fields.Many2one('hospital.inpatient', string='IP Admission Ref')
    casualty_id = fields.Many2one('hospital.casualty', string='Casualty Ref')

    def action_supervisor_signoff(self):
        for rec in self:
            rec.is_signed_off = True
            rec.signed_off_date = fields.Date.today()
            rec.supervisor_id = self.env.user.employee_id if hasattr(self.env.user, 'employee_id') else False


class HospitalInternReview(models.Model):
    _name = 'hospital.intern.review'
    _description = 'Intern Monthly HOD/DMS Review'
    _order = 'review_month desc'

    intern_id = fields.Many2one('hospital.intern', required=True, ondelete='cascade', index=True)
    review_month = fields.Date(string='Review Month', required=True,
                                help='Select any date in the review month')
    attendance_pct = fields.Float(string='Attendance %', related='intern_id.attendance_pct', store=True)
    total_cases = fields.Integer(string='Cases Logged', related='intern_id.total_cases', store=True)

    performance_rating = fields.Selection([
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('satisfactory', 'Satisfactory'),
        ('needs_improvement', 'Needs Improvement'),
    ], string='Overall Performance')

    clinical_knowledge = fields.Selection([('1','1'),('2','2'),('3','3'),('4','4'),('5','5')],
                                           string='Clinical Knowledge (1-5)')
    practical_skills = fields.Selection([('1','1'),('2','2'),('3','3'),('4','4'),('5','5')],
                                         string='Practical Skills (1-5)')
    communication = fields.Selection([('1','1'),('2','2'),('3','3'),('4','4'),('5','5')],
                                      string='Communication (1-5)')
    professionalism = fields.Selection([('1','1'),('2','2'),('3','3'),('4','4'),('5','5')],
                                        string='Professionalism (1-5)')
    remarks = fields.Text(string='Remarks & Recommendations')
    signed_by = fields.Many2one('hr.employee', string='Reviewed & Signed By (HOD/DMS)')
    signed_date = fields.Date(string='Signed On')
    state = fields.Selection([('draft', 'Draft'), ('signed', 'Signed')],
                              default='draft', tracking=True)

    def action_sign(self):
        for rec in self:
            rec.state = 'signed'
            rec.signed_by = self.env.user.employee_id if hasattr(self.env.user, 'employee_id') else False
            rec.signed_date = fields.Date.today()

class HospitalInternWardRound(models.Model):
    """§21.4 Ward Round Attendance Log — vitals, clinical observations per IP patient."""
    _name = 'hospital.intern.ward.round'
    _description = 'Intern Ward Round Log'
    _order = 'date desc'

    intern_id = fields.Many2one('hospital.intern', required=True, ondelete='cascade')
    date = fields.Date(string='Date', required=True, default=fields.Date.today)
    inpatient_id = fields.Many2one('hospital.inpatient', string='IP Patient', required=True)
    supervising_doctor_id = fields.Many2one('hr.employee', string='Supervising Doctor / RMO')

    # Vitals
    height = fields.Float(string='Height (cm)')
    weight = fields.Float(string='Weight (kg)')
    bmi = fields.Float(string='BMI', compute='_compute_bmi', store=True)
    bp_systolic = fields.Integer(string='BP Systolic (mmHg)')
    bp_diastolic = fields.Integer(string='BP Diastolic (mmHg)')
    temperature = fields.Float(string='Body Temperature (°F)')
    pulse = fields.Integer(string='Pulse (bpm)')

    # Ayurveda
    nadee_pareeksha = fields.Text(string='Nadee Pareeksha Findings')
    chief_complaints = fields.Text(string='Chief Complaints (Observed)')
    clinical_observations = fields.Text(string='Clinical Observations by Intern')

    # Supervisor
    supervisor_confirmation = fields.Boolean(string='Supervisor Confirmed', default=False)
    supervisor_remarks = fields.Text(string='Supervisor Remarks')
    is_signed_off = fields.Boolean(string='Signed Off', default=False)

    @api.depends('height', 'weight')
    def _compute_bmi(self):
        for rec in self:
            if rec.height and rec.weight:
                h_m = rec.height / 100
                rec.bmi = round(rec.weight / (h_m * h_m), 2)
            else:
                rec.bmi = 0.0