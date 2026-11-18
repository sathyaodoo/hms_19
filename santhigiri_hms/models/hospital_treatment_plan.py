# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import api, fields, models
from .hospital_procedure_schedule import TIME_SLOTS


class HospitalTreatmentPlan(models.Model):
    """IP Treatment Plan — for procedures and therapies (billed to accounting heads)."""
    _name = 'hospital.treatment.plan'
    _description = 'IP Treatment Plan (Procedures / Therapies)'
    _order = 'date desc, start_time asc, sequence, id desc'

    inpatient_id = fields.Many2one('hospital.inpatient', string='IP Admission',
                                    ondelete='cascade', index=True)
    assessment_id = fields.Many2one('hospital.op.assessment', string='Initial Assessment',
                                     ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)

    # ── Parity with Procedure Schedule & Santhigiri Legacy ───────────────────
    date = fields.Date(string='Date', default=fields.Date.today, required=True)
    start_time = fields.Selection(TIME_SLOTS, string='Start Time', default='09:00:00 AM')
    end_time = fields.Selection(TIME_SLOTS, string='End Time', default='10:00:00 AM')
    duration = fields.Char(string='Duration', default='45m')
    location_site = fields.Char(string='Location / Site')
    notes = fields.Text(string='Notes')
    treatment_room_id = fields.Many2one('patient.room', string='Treatment Room')

    procedure_id = fields.Many2one('product.template', string='Procedure / Therapy',
                                    domain=[('is_procedure', '=', True)], required=True)

    # Medicines 1, 2, 3
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

    # Staff / Therapists
    staff_ids = fields.Many2many('hr.employee', 'treatment_plan_staff_rel',
                                 'plan_id', 'staff_id', string='Staff')
    therapist_ids = fields.Many2many('hr.employee', 'tp_therapist_rel',
                                     'plan_id', 'therapist_id', string='Therapist(s)')
    staff_display = fields.Char(string='Staff', compute='_compute_staff_display', store=True)

    status = fields.Selection([
        ('scheduled', 'Scheduled'),
        ('updated', 'Updated'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='scheduled')

    # Linked schedule line
    schedule_line_id = fields.Many2one('hospital.procedure.schedule.line',
                                       string='Schedule Line Ref', ondelete='set null')

    # ── Legacy compatibility fields ──────────────────────────────────────────
    frequency = fields.Selection([
        ('daily', 'Daily'),
        ('alternate', 'Alternate Day'),
        ('weekly', 'Weekly'),
        ('twice_daily', 'Twice Daily'),
    ], string='Frequency', default='daily')
    no_of_sessions = fields.Integer(string='Total Sessions', default=1)
    start_date = fields.Date(string='Start Date')
    procedure_medicine_ids = fields.One2many('hospital.tp.medicine', 'treatment_plan_id',
                                              string='Medicines for Procedure')
    instructions = fields.Text(string='Instructions')
    state = fields.Selection([('draft', 'Draft'), ('active', 'Active'),
                               ('done', 'Completed'), ('cancelled', 'Cancelled')],
                              default='draft', tracking=True)
    completed_sessions = fields.Integer(string='Completed', default=0)
    procedure_charge = fields.Monetary(string='Total Procedure Charge',
                                        compute='_compute_charge', store=True,
                                        currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda s: s.env.company.currency_id)
    rmo_approved = fields.Boolean(string='RMO Approved')
    therapist_log_ids = fields.One2many('hospital.therapist.log', 'treatment_plan_id',
                                         string='Therapist Daily Logs')

    @api.depends('medicine_id_1', 'dosage_1', 'unit_1',
                 'medicine_id_2', 'dosage_2', 'unit_2',
                 'medicine_id_3', 'dosage_3', 'unit_3',
                 'procedure_medicine_ids', 'procedure_medicine_ids.medicine_id')
    def _compute_medicine_display(self):
        for rec in self:
            parts = []
            if rec.medicine_id_1:
                detail = f"{rec.medicine_id_1.name}"
                sub = [x for x in [rec.dosage_1, rec.unit_1] if x]
                if sub:
                    detail += f" ({' '.join(sub)})"
                parts.append(detail)
            if rec.medicine_id_2:
                detail = f"{rec.medicine_id_2.name}"
                sub = [x for x in [rec.dosage_2, rec.unit_2] if x]
                if sub:
                    detail += f" ({' '.join(sub)})"
                parts.append(detail)
            if rec.medicine_id_3:
                detail = f"{rec.medicine_id_3.name}"
                sub = [x for x in [rec.dosage_3, rec.unit_3] if x]
                if sub:
                    detail += f" ({' '.join(sub)})"
                parts.append(detail)
            if not parts and rec.procedure_medicine_ids:
                for pm in rec.procedure_medicine_ids:
                    if pm.medicine_id:
                        parts.append(pm.medicine_id.name)
            rec.medicine_display = ", ".join(parts)

    @api.depends('staff_ids', 'staff_ids.name', 'therapist_ids', 'therapist_ids.name')
    def _compute_staff_display(self):
        for rec in self:
            staffs = rec.staff_ids or rec.therapist_ids
            rec.staff_display = ", ".join(staffs.mapped('name'))

    @api.depends('procedure_id', 'completed_sessions')
    def _compute_charge(self):
        for rec in self:
            rate = rec.procedure_id.list_price if rec.procedure_id else 0.0
            rec.procedure_charge = rate * rec.completed_sessions

    def action_repeat(self):
        """Duplicates this session line for the next day."""
        self.ensure_one()
        next_date = (self.date or fields.Date.today()) + timedelta(days=1)
        staff_ids = self.staff_ids.ids or self.therapist_ids.ids
        self.copy({
            'date': next_date,
            'start_date': next_date,
            'status': 'scheduled',
            'state': 'active',
            'schedule_line_id': False,
            'staff_ids': [(6, 0, staff_ids)],
            'therapist_ids': [(6, 0, staff_ids)],
        })
        return True

    def action_delete(self):
        """Deletes this treatment plan line."""
        self.ensure_one()
        if self.schedule_line_id:
            sched_line = self.schedule_line_id
            self.schedule_line_id = False
            sched_line.sudo().unlink()
        self.unlink()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('assessment_id'):
                ass = self.env['hospital.op.assessment'].browse(vals['assessment_id'])
                if not vals.get('inpatient_id') and ass.inpatient_id:
                    vals['inpatient_id'] = ass.inpatient_id.id
            elif vals.get('inpatient_id') and not vals.get('assessment_id'):
                ass = self.env['hospital.op.assessment'].search([
                    ('inpatient_id', '=', vals['inpatient_id']),
                ], limit=1)
                if ass:
                    vals['assessment_id'] = ass.id
            # Sync date and start_date
            if vals.get('date') and not vals.get('start_date'):
                vals['start_date'] = vals['date']
            elif vals.get('start_date') and not vals.get('date'):
                vals['date'] = vals['start_date']
            # Sync staff_ids and therapist_ids
            if vals.get('staff_ids') and not vals.get('therapist_ids'):
                vals['therapist_ids'] = vals['staff_ids']
            elif vals.get('therapist_ids') and not vals.get('staff_ids'):
                vals['staff_ids'] = vals['therapist_ids']
            # Sync notes and instructions
            if vals.get('notes') and not vals.get('instructions'):
                vals['instructions'] = vals['notes']
            elif vals.get('instructions') and not vals.get('notes'):
                vals['notes'] = vals['instructions']
            # Sync status and state
            if vals.get('status') and not vals.get('state'):
                status = vals['status']
                vals['state'] = 'done' if status == 'done' else ('cancelled' if status == 'cancelled' else 'active')

            proc_id = vals.get('procedure_id')
            if proc_id:
                proc = self.env['product.template'].sudo().browse(proc_id)
                if not proc.is_procedure:
                    proc.write({'is_procedure': True, 'type': 'service'})

        records = super().create(vals_list)

        # Sync with Procedure Schedule lines if applicable
        if not self.env.context.get('skip_proc_sched_sync'):
            for plan in records:
                if plan.inpatient_id and plan.procedure_id and not plan.schedule_line_id:
                    schedule = self.env['hospital.procedure.schedule'].search([
                        ('inpatient_id', '=', plan.inpatient_id.id),
                    ], limit=1)
                    if not schedule:
                        schedule = self.env['hospital.procedure.schedule'].create({
                            'schedule_type': 'inpatient',
                            'inpatient_id': plan.inpatient_id.id,
                            'patient_id': plan.inpatient_id.patient_id.id,
                            'visit_date': plan.date or plan.inpatient_id.hosp_date or fields.Date.today(),
                        })
                    staff_ids = plan.staff_ids.ids or plan.therapist_ids.ids
                    sched_line = self.env['hospital.procedure.schedule.line'].with_context(skip_tp_sync=True).create({
                        'schedule_id': schedule.id,
                        'date': plan.date or fields.Date.today(),
                        'start_time': plan.start_time or '09:00:00 AM',
                        'end_time': plan.end_time or '10:00:00 AM',
                        'procedure_id': plan.procedure_id.id,
                        'medicine_id_1': plan.medicine_id_1.id if plan.medicine_id_1 else False,
                        'dosage_1': plan.dosage_1 or '',
                        'unit_1': plan.unit_1 or '',
                        'medicine_id_2': plan.medicine_id_2.id if plan.medicine_id_2 else False,
                        'dosage_2': plan.dosage_2 or '',
                        'unit_2': plan.unit_2 or '',
                        'medicine_id_3': plan.medicine_id_3.id if plan.medicine_id_3 else False,
                        'dosage_3': plan.dosage_3 or '',
                        'unit_3': plan.unit_3 or '',
                        'duration': plan.duration or '',
                        'location_site': plan.location_site or '',
                        'notes': plan.notes or plan.instructions or '',
                        'treatment_room_id': plan.treatment_room_id.id if plan.treatment_room_id else False,
                        'staff_ids': [(6, 0, staff_ids)],
                        'status': plan.status or 'scheduled',
                        'treatment_plan_id': plan.id,
                    })
                    plan.with_context(skip_proc_sched_sync=True).write({'schedule_line_id': sched_line.id})
        return records

    def write(self, vals):
        if 'procedure_id' in vals and vals['procedure_id']:
            proc = self.env['product.template'].sudo().browse(vals['procedure_id'])
            if not proc.is_procedure:
                proc.write({'is_procedure': True, 'type': 'service'})
        if vals.get('date') and 'start_date' not in vals:
            vals['start_date'] = vals['date']
        if vals.get('notes') and 'instructions' not in vals:
            vals['instructions'] = vals['notes']
        if vals.get('staff_ids') and 'therapist_ids' not in vals:
            vals['therapist_ids'] = vals['staff_ids']
        if vals.get('status') and 'state' not in vals:
            vals['state'] = 'done' if vals['status'] == 'done' else ('cancelled' if vals['status'] == 'cancelled' else 'active')

        res = super().write(vals)

        # Sync changes to schedule_line_id
        if not self.env.context.get('skip_proc_sched_sync'):
            for plan in self:
                if plan.schedule_line_id:
                    sync_vals = {}
                    for f in ['date', 'start_time', 'end_time', 'procedure_id',
                              'medicine_id_1', 'dosage_1', 'unit_1',
                              'medicine_id_2', 'dosage_2', 'unit_2',
                              'medicine_id_3', 'dosage_3', 'unit_3',
                              'duration', 'location_site', 'notes', 'treatment_room_id', 'status']:
                        if f in vals:
                            sync_vals[f] = getattr(plan, f).id if hasattr(getattr(plan, f), 'id') else getattr(plan, f)
                    if 'staff_ids' in vals or 'therapist_ids' in vals:
                        sync_vals['staff_ids'] = [(6, 0, (plan.staff_ids.ids or plan.therapist_ids.ids))]
                    if sync_vals:
                        plan.schedule_line_id.with_context(skip_tp_sync=True).write(sync_vals)
        return res


class HospitalTPMedicine(models.Model):
    """Medicines required for a treatment plan procedure."""
    _name = 'hospital.tp.medicine'
    _description = 'Treatment Plan Medicine Requirement'

    treatment_plan_id = fields.Many2one('hospital.treatment.plan', ondelete='cascade')
    medicine_id = fields.Many2one('product.template', string='Medicine / Material',
                                   domain=[('medicine_ok', '=', True)], required=True)
    quantity = fields.Float(string='Quantity per Session', default=1.0)
    uom_id = fields.Many2one('uom.uom', string='Unit')


class HospitalMedicationPlan(models.Model):
    """Medication Plan — for medicines billed directly to patient
    account. Was IP-only; now also reachable from OP visits, same
    concept as hospital.procedure.prescription's outpatient_id/
    inpatient_id pair — both origin fields are optional, at least one
    is expected to be set, and nothing else about this model needs to
    change to support either origin."""
    _name = 'hospital.medication.plan'
    _description = 'Medication Plan (Patient Medicines)'

    inpatient_id = fields.Many2one('hospital.inpatient', string='IP Admission',
                                    ondelete='cascade', index=True)
    outpatient_id = fields.Many2one('hospital.outpatient', string='OP Visit',
                                     ondelete='cascade', index=True)
    assessment_id = fields.Many2one('hospital.op.assessment', string='Initial Assessment',
                                     ondelete='cascade', index=True)
    medicine_id = fields.Many2one('product.template', string='Medicine',
                                   domain=[('medicine_ok', '=', True)], required=True)
    dosage = fields.Char(string='Dosage', help='e.g. 1-0-1, 0-0-1')
    frequency = fields.Selection([
        ('once', 'Once Daily'),
        ('twice', 'Twice Daily'),
        ('thrice', 'Three Times Daily'),
        ('sos', 'SOS (as needed)'),
    ], string='Frequency', default='once')
    duration_days = fields.Integer(string='Duration (Days)', default=1)
    start_date = fields.Date(string='Start Date', default=fields.Date.today)
    anupanam = fields.Char(string='Anupanam')
    route = fields.Selection([
        ('oral', 'Oral'), ('external', 'External'), ('nasal', 'Nasal'),
        ('rectal', 'Rectal'),
    ], default='oral')
    instructions = fields.Text(string='Instructions')
    rmo_modified = fields.Boolean(string='Modified by RMO')
    total_charge = fields.Monetary(string='Total Charge', compute='_compute_total_charge',
                                    store=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda s: s.env.company.currency_id)
    prescription_line_ids = fields.One2many('prescription.line', 'medication_plan_id',
                                             string='Daily Prescription Lines')

    @api.depends('medicine_id', 'duration_days')
    def _compute_total_charge(self):
        for rec in self:
            price = rec.medicine_id.list_price if rec.medicine_id else 0.0
            rec.total_charge = price * (rec.duration_days or 1)


class HospitalTherapistLog(models.Model):
    """Daily therapist session log for IP treatment plans."""
    _name = 'hospital.therapist.log'
    _description = 'IP Therapist Daily Session Log'
    _order = 'date desc'

    treatment_plan_id = fields.Many2one('hospital.treatment.plan', string='Treatment Plan',
                                         required=True, ondelete='cascade', index=True)
    inpatient_id = fields.Many2one(related='treatment_plan_id.inpatient_id', store=True)
    patient_id = fields.Many2one(related='treatment_plan_id.inpatient_id.patient_id', store=True)
    date = fields.Date(string='Session Date', required=True, default=fields.Date.today)
    therapist_id = fields.Many2one('hr.employee', string='Therapist', required=True)
    start_time = fields.Float(string='Start Time (24hr)', help='e.g. 9.5 = 9:30 AM')
    end_time = fields.Float(string='End Time (24hr)')
    duration = fields.Float(string='Duration (hrs)', compute='_compute_duration', store=True)
    session_no = fields.Integer(string='Session No.', default=1)
    total_sessions = fields.Integer(related='treatment_plan_id.no_of_sessions', store=True)
    progress_display = fields.Char(string='Progress', compute='_compute_progress')
    patient_response = fields.Text(string='Patient Response / Notes')
    status = fields.Selection([
        ('pending', 'Pending'),
        ('done', 'Completed'),
        ('skipped', 'Skipped'),
    ], default='pending', tracking=True)
    skip_reason = fields.Char(string='Skip Reason')

    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        for rec in self:
            rec.duration = max(0.0, rec.end_time - rec.start_time)

    @api.depends('session_no', 'total_sessions')
    def _compute_progress(self):
        for rec in self:
            rec.progress_display = f'Session {rec.session_no} of {rec.total_sessions}'

    def action_mark_done(self):
        for rec in self:
            rec.status = 'done'
            rec.treatment_plan_id.completed_sessions = (
                rec.treatment_plan_id.completed_sessions + 1
            )
