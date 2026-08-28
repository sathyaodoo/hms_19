# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HospitalTreatmentPlan(models.Model):
    """IP Treatment Plan — for procedures and therapies (billed to accounting heads)."""
    _name = 'hospital.treatment.plan'
    _description = 'IP Treatment Plan (Procedures / Therapies)'
    _order = 'sequence'

    inpatient_id = fields.Many2one('hospital.inpatient', string='IP Admission',
                                    required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    procedure_id = fields.Many2one('product.template', string='Procedure / Therapy',
                                    domain=[('is_procedure', '=', True)], required=True)
    frequency = fields.Selection([
        ('daily', 'Daily'),
        ('alternate', 'Alternate Day'),
        ('weekly', 'Weekly'),
        ('twice_daily', 'Twice Daily'),
    ], string='Frequency', default='daily')
    no_of_sessions = fields.Integer(string='Total Sessions', default=7)
    start_date = fields.Date(string='Start Date')
    therapist_ids = fields.Many2many('hr.employee', 'tp_therapist_rel', 'plan_id', 'therapist_id',
                                      string='Therapist(s)', domain=[('is_therapist', '=', True)])
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

    @api.depends('procedure_id', 'completed_sessions')
    def _compute_charge(self):
        for rec in self:
            rate = rec.procedure_id.list_price if rec.procedure_id else 0.0
            rec.procedure_charge = rate * rec.completed_sessions


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
    """IP Medication Plan — for medicines billed directly to patient account."""
    _name = 'hospital.medication.plan'
    _description = 'IP Medication Plan (Patient Medicines)'

    inpatient_id = fields.Many2one('hospital.inpatient', string='IP Admission',
                                    required=True, ondelete='cascade', index=True)
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
    therapist_id = fields.Many2one('hr.employee', string='Therapist',
                                    domain=[('is_therapist', '=', True)], required=True)
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
