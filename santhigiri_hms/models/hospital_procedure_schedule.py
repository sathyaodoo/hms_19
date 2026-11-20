# -*- coding: utf-8 -*-
"""
Case Sheet (Procedure Schedule) — Parity with Santhigiri Legacy Software.
Covers:
- Patient Header Strip (Visit Date, ID No., IP No., Category, Patient Name, Gender, Age, Department, Doctor, Bed No., Room No., Discharge Date, Review Date)
- Quick Entry Row (Date, Start Time, End Time, Procedure, 3 Medicines with Dosage & Unit, Duration, Location/Site, Notes, Treatment Room, Staff, Add Button)
- Schedule Table (Date, Start Time, End Time, Procedure, Medicine, Duration, Location/Site, Notes, Treatment Room, Staff, Status, Repeat, Delete)
- Navigation Buttons (TREATMENT, MEDICINE SCHEDULE, Case Sheet View)
"""
from datetime import timedelta
from odoo import api, fields, models
from odoo.exceptions import UserError

TIME_SLOTS = [
    ('06:00:00 AM', '06:00:00 AM'),
    ('06:30:00 AM', '06:30:00 AM'),
    ('07:00:00 AM', '07:00:00 AM'),
    ('07:30:00 AM', '07:30:00 AM'),
    ('08:00:00 AM', '08:00:00 AM'),
    ('08:30:00 AM', '08:30:00 AM'),
    ('09:00:00 AM', '09:00:00 AM'),
    ('09:30:00 AM', '09:30:00 AM'),
    ('10:00:00 AM', '10:00:00 AM'),
    ('10:30:00 AM', '10:30:00 AM'),
    ('11:00:00 AM', '11:00:00 AM'),
    ('11:30:00 AM', '11:30:00 AM'),
    ('12:00:00 PM', '12:00:00 PM'),
    ('12:30:00 PM', '12:30:00 PM'),
    ('01:00:00 PM', '01:00:00 PM'),
    ('01:30:00 PM', '01:30:00 PM'),
    ('02:00:00 PM', '02:00:00 PM'),
    ('02:30:00 PM', '02:30:00 PM'),
    ('03:00:00 PM', '03:00:00 PM'),
    ('03:30:00 PM', '03:30:00 PM'),
    ('04:00:00 PM', '04:00:00 PM'),
    ('04:30:00 PM', '04:30:00 PM'),
    ('05:00:00 PM', '05:00:00 PM'),
    ('05:30:00 PM', '05:30:00 PM'),
    ('06:00:00 PM', '06:00:00 PM'),
    ('06:30:00 PM', '06:30:00 PM'),
    ('07:00:00 PM', '07:00:00 PM'),
    ('07:30:00 PM', '07:30:00 PM'),
    ('08:00:00 PM', '08:00:00 PM'),
    ('08:30:00 PM', '08:30:00 PM'),
    ('09:00:00 PM', '09:00:00 PM'),
]


class HospitalProcedureSchedule(models.Model):
    _name = 'hospital.procedure.schedule'
    _description = 'Case Sheet (Procedure Schedule)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'visit_date desc, id desc'

    name = fields.Char(string='Schedule Ref', default='New', readonly=True, copy=False)
    schedule_type = fields.Selection([
        ('inpatient', 'Inpatient (IP)'),
        ('outpatient', 'Outpatient (OP)'),
    ], string='Schedule Type', default='inpatient', required=True)

    inpatient_id = fields.Many2one('hospital.inpatient', string='IP Admission', ondelete='cascade', index=True)
    outpatient_id = fields.Many2one('hospital.outpatient', string='OP Visit', ondelete='cascade', index=True)
    patient_id = fields.Many2one('res.partner', string='Patient', required=True, index=True)

    # ── Patient Header Details (Legacy Screen Parity) ─────────────────────────
    visit_date = fields.Date(string='Visit Date', default=fields.Date.today, required=True)
    uhid_no = fields.Char(string='ID. No.', readonly=True)
    ip_no = fields.Char(string='IP No.', readonly=True)
    patient_category = fields.Char(string='Category')
    patient_name = fields.Char(string='Patient Name', readonly=True)
    patient_gender = fields.Char(string='Gender', readonly=True)
    patient_age = fields.Char(string='Age', readonly=True)
    department_id = fields.Many2one('hospital.department', string='Department', ondelete='set null')
    doctor_id = fields.Many2one('hr.employee', string='Doctor', domain=[('doctor', '=', True)])
    bed_id = fields.Many2one('hospital.bed', string='Bed')
    bed_no = fields.Char(string='Bed No.')
    room_id = fields.Many2one('patient.room', string='Room')
    room_no = fields.Char(string='Room No.')
    discharge_date = fields.Date(string='Discharge Date')
    review_date = fields.Date(string='Review Date')

    # ── Quick Entry Row (Scheduling Controls) ─────────────────────────────────
    quick_date = fields.Date(string='Date', default=fields.Date.today)
    quick_start_time = fields.Selection(TIME_SLOTS, string='Start Time', default='09:00:00 AM')
    quick_end_time = fields.Selection(TIME_SLOTS, string='End Time', default='10:00:00 AM')
    quick_procedure_id = fields.Many2one('product.template', string='Procedure',
                                         domain=[('is_procedure', '=', True)])

    # Medicines (1), (2), (3)
    quick_medicine_1 = fields.Many2one('product.template', string='Medicine (1)',
                                       domain=[('medicine_ok', '=', True)])
    quick_dosage_1 = fields.Char(string='Dosage (1)')
    quick_unit_1 = fields.Char(string='Unit (1)')

    quick_medicine_2 = fields.Many2one('product.template', string='Medicine (2)',
                                       domain=[('medicine_ok', '=', True)])
    quick_dosage_2 = fields.Char(string='Dosage (2)')
    quick_unit_2 = fields.Char(string='Unit (2)')

    quick_medicine_3 = fields.Many2one('product.template', string='Medicine (3)',
                                       domain=[('medicine_ok', '=', True)])
    quick_dosage_3 = fields.Char(string='Dosage (3)')
    quick_unit_3 = fields.Char(string='Unit (3)')

    quick_duration = fields.Char(string='Duration')
    quick_location_site = fields.Char(string='Location / Site')
    quick_notes = fields.Text(string='Notes')
    quick_treatment_room_id = fields.Many2one('patient.room', string='Treatment Room')
    quick_staff_ids = fields.Many2many('hr.employee', 'proc_sched_quick_therapist_rel',
                                       'schedule_id', 'staff_id', string='Staff')

    # ── Schedule Lines Table ──────────────────────────────────────────────────
    line_ids = fields.One2many('hospital.procedure.schedule.line', 'schedule_id',
                               string='Procedure Schedule Lines')
    line_count = fields.Integer(string='Line Count', compute='_compute_line_count')

    @api.depends('line_ids')
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    # ── Onchanges to auto-populate header from patient / admission ─────────────
    @api.onchange('inpatient_id')
    def _onchange_inpatient_id(self):
        if self.inpatient_id:
            ip = self.inpatient_id
            self.patient_id = ip.patient_id.id
            self.uhid_no = ip.uhid_no or ip.patient_id.uhid_no or ''
            self.ip_no = ip.name or ''
            cat_label = dict(ip._fields['patient_category'].selection).get(
                ip.patient_category, ip.patient_category) if hasattr(ip, 'patient_category') and ip.patient_category else ''
            self.patient_category = cat_label
            self.patient_name = ip.patient_id.name or ''
            self.patient_gender = (ip.patient_id.gender or '').capitalize()
            self.patient_age = f"{ip.patient_id.age} yrs" if ip.patient_id.age else ''
            self.department_id = ip.department_id.id if ip.department_id else False
            self.doctor_id = ip.attending_doctor_id.id if ip.attending_doctor_id else False
            self.bed_id = ip.bed_id.id if ip.bed_id else False
            self.bed_no = ip.bed_id.name if ip.bed_id else ''
            self.room_id = ip.room_id.id if ip.room_id else False
            self.room_no = ip.room_id.name if ip.room_id else ''
            self.visit_date = ip.hosp_date or fields.Date.today()
            self.discharge_date = ip.discharge_date or False

    @api.onchange('outpatient_id')
    def _onchange_outpatient_id(self):
        if self.outpatient_id:
            op = self.outpatient_id
            self.patient_id = op.patient_id.id
            self.uhid_no = op.uhid_no or op.patient_id.uhid_no or ''
            self.ip_no = op.op_reference or ''
            self.patient_category = getattr(op, 'patient_category', '')
            self.patient_name = op.patient_id.name or ''
            self.patient_gender = (op.patient_id.gender or '').capitalize()
            self.patient_age = f"{op.patient_id.age} yrs" if op.patient_id.age else ''
            self.department_id = op.department_id.id if op.department_id else False
            if hasattr(op, 'doctor_id') and op.doctor_id:
                doc = getattr(op.doctor_id, 'doctor_id', op.doctor_id)
                self.doctor_id = doc.id if doc else False
            self.visit_date = op.op_date or fields.Date.today()

    @api.onchange('patient_id')
    def _onchange_patient_id(self):
        if self.patient_id:
            p = self.patient_id
            self.patient_name = p.name or ''
            self.uhid_no = p.uhid_no or ''
            self.patient_gender = (p.gender or '').capitalize()
            self.patient_age = f"{p.age} yrs" if p.age else ''
            if not self.inpatient_id and self.schedule_type == 'inpatient':
                ip = self.env['hospital.inpatient'].search([
                    ('patient_id', '=', p.id),
                    ('state', 'not in', ['dis', 'cancel'])
                ], order='id desc', limit=1)
                if ip:
                    self.inpatient_id = ip.id
                    self._onchange_inpatient_id()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                seq = self.env['ir.sequence'].next_by_code('hospital.procedure.schedule') or 'PSCHED/001'
                vals['name'] = seq
            # Auto-fill patient header data if inpatient_id provided
            if vals.get('inpatient_id') and not vals.get('patient_name'):
                ip = self.env['hospital.inpatient'].browse(vals['inpatient_id'])
                vals['patient_id'] = ip.patient_id.id
                vals['uhid_no'] = ip.uhid_no or ip.patient_id.uhid_no or ''
                vals['ip_no'] = ip.name or ''
                vals['patient_category'] = dict(ip._fields['patient_category'].selection).get(
                    ip.patient_category, ip.patient_category) if ip.patient_category else ''
                vals['patient_name'] = ip.patient_id.name or ''
                vals['patient_gender'] = (ip.patient_id.gender or '').capitalize()
                vals['patient_age'] = f"{ip.patient_id.age} yrs" if ip.patient_id.age else ''
                vals['department_id'] = ip.department_id.id if ip.department_id else False
                vals['doctor_id'] = ip.attending_doctor_id.id if ip.attending_doctor_id else False
                vals['bed_id'] = ip.bed_id.id if ip.bed_id else False
                vals['bed_no'] = ip.bed_id.name if ip.bed_id else ''
                vals['room_id'] = ip.room_id.id if ip.room_id else False
                vals['room_no'] = ip.room_id.name if ip.room_id else ''
                vals['visit_date'] = ip.hosp_date or fields.Date.today()
                vals['discharge_date'] = ip.discharge_date or False
            # Auto-fill patient header data if outpatient_id provided
            elif vals.get('outpatient_id') and not vals.get('patient_name'):
                op = self.env['hospital.outpatient'].browse(vals['outpatient_id'])
                vals['patient_id'] = op.patient_id.id
                vals['uhid_no'] = op.uhid_no or op.patient_id.uhid_no or ''
                vals['ip_no'] = op.op_reference or ''
                vals['patient_category'] = getattr(op, 'patient_category', '')
                vals['patient_name'] = op.patient_id.name or ''
                vals['patient_gender'] = (op.patient_id.gender or '').capitalize()
                vals['patient_age'] = f"{op.patient_id.age} yrs" if op.patient_id.age else ''
                vals['department_id'] = op.department_id.id if op.department_id else False
                if hasattr(op, 'doctor_id') and op.doctor_id:
                    doc = getattr(op.doctor_id, 'doctor_id', op.doctor_id)
                    vals['doctor_id'] = doc.id if doc else False
                vals['visit_date'] = op.op_date or fields.Date.today()
        return super().create(vals_list)

    # ── Quick Add Line Action ─────────────────────────────────────────────────
    def action_quick_add_line(self):
        """Creates a schedule line from the quick entry controls and resets them."""
        self.ensure_one()
        if not self.quick_procedure_id:
            raise UserError("Please select a Procedure before adding.")

        # Ensure procedure is tagged properly in product.template
        if not self.quick_procedure_id.is_procedure:
            self.quick_procedure_id.write({'is_procedure': True, 'type': 'service'})

        # Ensure medicines are tagged properly in product.template
        for med in [self.quick_medicine_1, self.quick_medicine_2, self.quick_medicine_3]:
            if med and not med.medicine_ok:
                med.write({'medicine_ok': True, 'type': 'consu'})

        line_vals = {
            'schedule_id': self.id,
            'date': self.quick_date or fields.Date.today(),
            'start_time': self.quick_start_time or '',
            'end_time': self.quick_end_time or '',
            'procedure_id': self.quick_procedure_id.id,
            'medicine_id_1': self.quick_medicine_1.id if self.quick_medicine_1 else False,
            'dosage_1': self.quick_dosage_1 or '',
            'unit_1': self.quick_unit_1 or '',
            'medicine_id_2': self.quick_medicine_2.id if self.quick_medicine_2 else False,
            'dosage_2': self.quick_dosage_2 or '',
            'unit_2': self.quick_unit_2 or '',
            'medicine_id_3': self.quick_medicine_3.id if self.quick_medicine_3 else False,
            'dosage_3': self.quick_dosage_3 or '',
            'unit_3': self.quick_unit_3 or '',
            'duration': self.quick_duration or '',
            'location_site': self.quick_location_site or '',
            'notes': self.quick_notes or '',
            'treatment_room_id': self.quick_treatment_room_id.id if self.quick_treatment_room_id else False,
            'staff_ids': [(6, 0, self.quick_staff_ids.ids)],
            'status': 'scheduled',
        }
        self.env['hospital.procedure.schedule.line'].create(line_vals)

        # Reset quick input fields
        self.write({
            'quick_procedure_id': False,
            'quick_medicine_1': False,
            'quick_dosage_1': '',
            'quick_unit_1': '',
            'quick_medicine_2': False,
            'quick_dosage_2': '',
            'quick_unit_2': '',
            'quick_medicine_3': False,
            'quick_dosage_3': '',
            'quick_unit_3': '',
            'quick_duration': '',
            'quick_location_site': '',
            'quick_notes': '',
            'quick_treatment_room_id': False,
            'quick_staff_ids': [(5, 0, 0)],
        })
        return True

    # ── Top-Right & Bottom Navigation Actions ──────────────────────────────────
    def action_open_case_sheet(self):
        """Top-Right button: Case Sheet View (opens Inpatient Admission Case Sheet)."""
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
            if not ip:
                ip = self.env['hospital.inpatient'].search([
                    ('patient_id', '=', self.patient_id.id),
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
            op = self.env['hospital.outpatient'].search([
                ('patient_id', '=', self.patient_id.id),
            ], order='id desc', limit=1)
            if op:
                return {
                    'type': 'ir.actions.act_window',
                    'name': 'Outpatient',
                    'res_model': 'hospital.outpatient',
                    'res_id': op.id,
                    'view_mode': 'form',
                    'target': 'current',
                }
            raise UserError("No Inpatient or Outpatient admission record found for this patient.")

    def action_open_treatment(self):
        """Bottom button: TREATMENT (opens Treatment Plan)."""
        self.ensure_one()
        domain = []
        context = {}
        if self.inpatient_id:
            domain = [('inpatient_id', '=', self.inpatient_id.id)]
            context = {'default_inpatient_id': self.inpatient_id.id}
        return {
            'type': 'ir.actions.act_window',
            'name': 'Treatment Plans',
            'res_model': 'hospital.treatment.plan',
            'view_mode': 'list,form',
            'domain': domain,
            'context': context,
            'target': 'current',
        }

    def action_open_medicine_schedule(self):
        """Bottom button: MEDICINE SHEDULE (opens Medication Plan / Prescriptions)."""
        self.ensure_one()
        if self.inpatient_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Medication Plans (Medicine Schedule)',
                'res_model': 'hospital.medication.plan',
                'view_mode': 'list,form',
                'domain': [('inpatient_id', '=', self.inpatient_id.id)],
                'context': {'default_inpatient_id': self.inpatient_id.id},
                'target': 'current',
            }
        else:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Prescriptions (Medicine Schedule)',
                'res_model': 'hospital.prescription',
                'view_mode': 'list,form',
                'domain': [('patient_id', '=', self.patient_id.id)],
                'context': {'default_patient_id': self.patient_id.id},
                'target': 'current',
            }


class HospitalProcedureScheduleLine(models.Model):
    _name = 'hospital.procedure.schedule.line'
    _description = 'Procedure Schedule Line'
    _order = 'date desc, start_time asc, id desc'

    schedule_id = fields.Many2one('hospital.procedure.schedule', string='Schedule',
                                  required=True, ondelete='cascade', index=True)
    patient_id = fields.Many2one(related='schedule_id.patient_id', store=True, readonly=True)
    inpatient_id = fields.Many2one(related='schedule_id.inpatient_id', store=True, readonly=True)

    date = fields.Date(string='Date', required=True, default=fields.Date.today)
    start_time = fields.Selection(TIME_SLOTS, string='Start Time')
    end_time = fields.Selection(TIME_SLOTS, string='End Time')
    procedure_id = fields.Many2one('product.template', string='Procedure',
                                   domain=[('is_procedure', '=', True)], required=True)

    # 3 Medicines
    medicine_id_1 = fields.Many2one('product.template', string='Medicine 1',
                                    domain=[('medicine_ok', '=', True)])
    dosage_1 = fields.Char(string='Dosage 1')
    unit_1 = fields.Char(string='Unit 1')

    medicine_id_2 = fields.Many2one('product.template', string='Medicine 2',
                                    domain=[('medicine_ok', '=', True)])
    dosage_2 = fields.Char(string='Dosage 2')
    unit_2 = fields.Char(string='Unit 2')

    medicine_id_3 = fields.Many2one('product.template', string='Medicine 3',
                                    domain=[('medicine_ok', '=', True)])
    dosage_3 = fields.Char(string='Dosage 3')
    unit_3 = fields.Char(string='Unit 3')

    medicine_display = fields.Char(string='Medicine', compute='_compute_medicine_display', store=True)

    duration = fields.Char(string='Duration')
    location_site = fields.Char(string='Location/Site')
    notes = fields.Text(string='Notes')
    treatment_room_id = fields.Many2one('patient.room', string='Treatment Room')
    staff_ids = fields.Many2many('hr.employee', 'proc_sched_line_therapist_rel',
                                 'line_id', 'staff_id', string='Staff')
    staff_display = fields.Char(string='Staff', compute='_compute_staff_display', store=True)

    status = fields.Selection([
        ('scheduled', 'Scheduled'),
        ('updated', 'Updated'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='scheduled')

    treatment_plan_id = fields.Many2one('hospital.treatment.plan', string='Treatment Plan Ref', ondelete='set null')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self.env.context.get('skip_tp_sync'):
            for line in records:
                if line.schedule_id and line.schedule_id.inpatient_id and not line.treatment_plan_id:
                    ip = line.schedule_id.inpatient_id
                    staff_ids = line.staff_ids.ids
                    plan = self.env['hospital.treatment.plan'].with_context(skip_proc_sched_sync=True).create({
                        'inpatient_id': ip.id,
                        'procedure_id': line.procedure_id.id,
                        'date': line.date or fields.Date.today(),
                        'start_date': line.date or fields.Date.today(),
                        'start_time': line.start_time or '09:00:00 AM',
                        'end_time': line.end_time or '10:00:00 AM',
                        'duration': line.duration or '45m',
                        'location_site': line.location_site or '',
                        'notes': line.notes or '',
                        'instructions': line.notes or '',
                        'treatment_room_id': line.treatment_room_id.id if line.treatment_room_id else False,
                        'medicine_id_1': line.medicine_id_1.id if line.medicine_id_1 else False,
                        'dosage_1': line.dosage_1 or '',
                        'unit_1': line.unit_1 or '',
                        'medicine_id_2': line.medicine_id_2.id if line.medicine_id_2 else False,
                        'dosage_2': line.dosage_2 or '',
                        'unit_2': line.unit_2 or '',
                        'medicine_id_3': line.medicine_id_3.id if line.medicine_id_3 else False,
                        'dosage_3': line.dosage_3 or '',
                        'unit_3': line.unit_3 or '',
                        'staff_ids': [(6, 0, staff_ids)],
                        'therapist_ids': [(6, 0, staff_ids)],
                        'status': line.status or 'scheduled',
                        'state': 'done' if line.status == 'done' else ('cancelled' if line.status == 'cancelled' else 'active'),
                        'schedule_line_id': line.id,
                    })
                    line.with_context(skip_tp_sync=True).write({'treatment_plan_id': plan.id})
        return records

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('skip_tp_sync'):
            for line in self:
                if line.treatment_plan_id:
                    sync_vals = {}
                    for f in ['date', 'start_time', 'end_time', 'procedure_id',
                              'medicine_id_1', 'dosage_1', 'unit_1',
                              'medicine_id_2', 'dosage_2', 'unit_2',
                              'medicine_id_3', 'dosage_3', 'unit_3',
                              'duration', 'location_site', 'notes', 'treatment_room_id', 'status']:
                        if f in vals:
                            sync_vals[f] = getattr(line, f).id if hasattr(getattr(line, f), 'id') else getattr(line, f)
                    if 'staff_ids' in vals:
                        sync_vals['staff_ids'] = [(6, 0, line.staff_ids.ids)]
                        sync_vals['therapist_ids'] = [(6, 0, line.staff_ids.ids)]
                    if 'status' in vals:
                        sync_vals['state'] = 'done' if line.status == 'done' else ('cancelled' if line.status == 'cancelled' else 'active')
                    if 'notes' in vals:
                        sync_vals['instructions'] = line.notes
                    if 'date' in vals:
                        sync_vals['start_date'] = line.date
                    if sync_vals:
                        line.treatment_plan_id.with_context(skip_proc_sched_sync=True).write(sync_vals)
        return res

    def action_delete(self):
        """Deletes this line and linked treatment plan if any."""
        self.ensure_one()
        if self.treatment_plan_id:
            tp = self.treatment_plan_id
            self.treatment_plan_id = False
            tp.sudo().unlink()
        self.unlink()
        return True

    @api.depends('medicine_id_1', 'dosage_1', 'unit_1', 'medicine_id_2', 'dosage_2', 'unit_2', 'medicine_id_3', 'dosage_3', 'unit_3')
    def _compute_medicine_display(self):
        for rec in self:
            parts = []
            if rec.medicine_id_1:
                detail = f"{rec.medicine_id_1.name}"
                sub = []
                if rec.dosage_1:
                    sub.append(rec.dosage_1)
                if rec.unit_1:
                    sub.append(rec.unit_1)
                if sub:
                    detail += f" ({' '.join(sub)})"
                parts.append(detail)
            if rec.medicine_id_2:
                detail = f"{rec.medicine_id_2.name}"
                sub = []
                if rec.dosage_2:
                    sub.append(rec.dosage_2)
                if rec.unit_2:
                    sub.append(rec.unit_2)
                if sub:
                    detail += f" ({' '.join(sub)})"
                parts.append(detail)
            if rec.medicine_id_3:
                detail = f"{rec.medicine_id_3.name}"
                sub = []
                if rec.dosage_3:
                    sub.append(rec.dosage_3)
                if rec.unit_3:
                    sub.append(rec.unit_3)
                if sub:
                    detail += f" ({' '.join(sub)})"
                parts.append(detail)
            rec.medicine_display = ", ".join(parts)

    @api.depends('staff_ids', 'staff_ids.name')
    def _compute_staff_display(self):
        for rec in self:
            rec.staff_display = ", ".join(rec.staff_ids.mapped('name'))

    def action_repeat(self):
        """Duplicates this session line for the next day."""
        self.ensure_one()
        next_date = (self.date or fields.Date.today()) + timedelta(days=1)
        self.copy({
            'date': next_date,
            'status': 'scheduled',
            'staff_ids': [(6, 0, self.staff_ids.ids)],
        })
        return True


