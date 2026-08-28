# -*- coding: utf-8 -*-
"""
OP Daily Procedures — completely new module.
BASE MODULE has no procedure/therapy workflow.
Covers FRD 15.1–15.4: Procedure prescription by doctor, therapist assignment by RMO,
daily session tracking, per-visit billing.
"""
from odoo import api, fields, models
from odoo.exceptions import UserError


class HospitalProcedurePrescription(models.Model):
    _name = 'hospital.procedure.prescription'
    _description = 'OP Daily Procedure Prescription'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc'
    _rec_name = 'reference'

    reference = fields.Char(string='Reference', readonly=True, default='New', copy=False)
    outpatient_id = fields.Many2one('hospital.outpatient', string='OP Visit', ondelete='set null')
    patient_id = fields.Many2one('res.partner', string='Patient', required=True,
                                  domain=[('patient_seq', '!=', False)])
    patient_seq = fields.Char(related='patient_id.patient_seq', store=True, string='Patient No.')
    op_reference = fields.Char(related='outpatient_id.op_reference', store=True, string='OP Reference')

    doctor_id = fields.Many2one('hr.employee', string='Prescribed By (Doctor)',
                                 domain=[('doctor', '=', True)], required=True)
    procedure_id = fields.Many2one('product.template', string='Procedure / Therapy',
                                    domain=[('is_procedure', '=', True)], required=True)
    no_of_sessions = fields.Integer(string='Total Sessions', required=True, default=7)
    start_date = fields.Date(string='Start Date', required=True, default=fields.Date.today)
    instructions = fields.Text(string='Special Instructions')
    site_location = fields.Char(string='Site / Location',
                                 help='e.g. Lower back, Left knee, Full body')
    precautions = fields.Text(string='Precautions if any')

    # Medicines/materials required for this procedure
    procedure_medicine_ids = fields.One2many(
        'hospital.procedure.medicine',
        'prescription_id',
        string='Medicines / Materials Required',
        help='Medicines the doctor has specified for this procedure',
    )

    # Therapist assignment (done by RMO)
    therapist_ids = fields.Many2many(
        'hr.employee',
        'procedure_therapist_rel',
        'prescription_id',
        'therapist_id',
        string='Assigned Therapist(s)',
        domain=[('is_therapist', '=', True)],
    )
    rmo_id = fields.Many2one('hr.employee', string='Assigned By (RMO)',
                              domain=[('is_rmo', '=', True)])

    # Session tracking
    session_ids = fields.One2many('hospital.procedure.session', 'prescription_id', string='Sessions')
    completed_sessions = fields.Integer(string='Completed Sessions', compute='_compute_sessions', store=True)
    pending_sessions = fields.Integer(string='Pending Sessions', compute='_compute_sessions', store=True)
    progress_pct = fields.Float(string='Progress %', compute='_compute_sessions', store=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed / Therapist Assigned'),
        ('in_progress', 'In Progress'),
        ('done', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], default='draft', tracking=True)

    billing_mode = fields.Selection([
        ('per_visit', 'Per Visit (Default — immediate after session)'),
        ('weekly', 'Weekly'),
        ('end_of_course', 'End of Course'),
    ], string='Billing Mode', default='per_visit')
    session_rate = fields.Float(
        string='Rate per Session',
        related='procedure_id.list_price',
        store=True,
        digits=(10, 2),
    )
    currency_id = fields.Many2one('res.currency', default=lambda s: s.env.company.currency_id)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'New') == 'New':
                vals['reference'] = self.env['ir.sequence'].next_by_code(
                    'hospital.procedure.prescription'
                ) or 'PROC/001'
        return super().create(vals_list)

    @api.depends('session_ids', 'session_ids.state', 'no_of_sessions')
    def _compute_sessions(self):
        for rec in self:
            done = len(rec.session_ids.filtered(lambda s: s.state == 'done'))
            rec.completed_sessions = done
            rec.pending_sessions = rec.no_of_sessions - done
            rec.progress_pct = (done / rec.no_of_sessions * 100) if rec.no_of_sessions else 0.0

    def action_assign_therapist(self):
        """RMO confirms and notifies therapists."""
        self.ensure_one()
        if not self.therapist_ids:
            raise UserError('Please assign at least one therapist before confirming.')
        self.state = 'confirmed'
        # Notify therapists
        for therapist in self.therapist_ids:
            if therapist.work_email:
                self.env['mail.mail'].create({
                    'subject': f'Procedure Assigned — {self.reference}',
                    'body_html': (
                        f'<p>Dear {therapist.name},</p>'
                        f'<p>You have been assigned the procedure <b>{self.procedure_id.name}</b> '
                        f'for patient <b>{self.patient_id.name}</b> starting {self.start_date}.</p>'
                        f'<p>Total sessions: {self.no_of_sessions}</p>'
                    ),
                    'email_to': therapist.work_email,
                }).send()

    def _create_end_of_course_invoice(self):
        """
        End of Course billing: single invoice for ALL sessions after course completes.
        Checks if invoice already exists to avoid duplicates.
        """
        # Check if end-of-course invoice already created
        if self.session_ids.filtered(lambda s: s.invoice_id):
            return  # Already invoiced

        rate = self.session_rate or 0.0
        if not rate or not self.patient_id:
            return

        total_sessions = len(self.session_ids.filtered(
            lambda s: s.state == 'done'))
        total_amount = rate * total_sessions

        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.patient_id.id,
            'invoice_date': fields.Date.today(),
            'invoice_origin': self.reference,
            'invoice_line_ids': [(0, 0, {
                'name': (f'{self.procedure_id.name} — '
                         f'Complete Course ({total_sessions} sessions)'),
                'quantity': total_sessions,
                'price_unit': rate,
            })],
        })
        # Link all sessions to this invoice
        self.session_ids.filtered(
            lambda s: s.state == 'done'
        ).write({'invoice_id': move.id})

        self.message_post(
            body=f'End of course invoice created: '
                 f'{total_sessions} sessions × ₹{rate} = ₹{total_amount}',
            message_type='comment',
            subtype_xmlid='mail.mt_note',
        )

    def action_create_today_session(self):
        """Quickly create today's session record."""
        self.ensure_one()
        self.env['hospital.procedure.session'].create({
            'prescription_id': self.id,
            'date': fields.Date.today(),
            'therapist_id': self.therapist_ids[0].id if self.therapist_ids else False,
        })
        if self.state == 'confirmed':
            self.state = 'in_progress'


class HospitalProcedureMedicine(models.Model):
    """Medicines / materials the doctor specifies are needed for a procedure."""
    _name = 'hospital.procedure.medicine'
    _description = 'Procedure Medicine Requirement'

    prescription_id = fields.Many2one('hospital.procedure.prescription', ondelete='cascade')
    medicine_id = fields.Many2one('product.template', string='Medicine / Material',
                                   domain=[('medicine_ok', '=', True)], required=True)
    quantity = fields.Float(string='Quantity', default=1.0, required=True)
    uom_id = fields.Many2one('uom.uom', string='Unit')
    notes = fields.Char(string='Notes')


class HospitalProcedureSession(models.Model):
    """Daily session record for OP procedures."""
    _name = 'hospital.procedure.session'
    _description = 'Daily Procedure Session'
    _order = 'date desc'

    prescription_id = fields.Many2one('hospital.procedure.prescription', string='Prescription',
                                       required=True, ondelete='cascade', index=True)
    patient_id = fields.Many2one(related='prescription_id.patient_id', store=True)
    date = fields.Date(string='Session Date', required=True, default=fields.Date.today)
    session_no = fields.Integer(string='Session No.', compute='_compute_session_no', store=True)
    total_sessions = fields.Integer(related='prescription_id.no_of_sessions', store=True)
    progress_display = fields.Char(string='Progress', compute='_compute_session_no', store=True)
    therapist_id = fields.Many2one('hr.employee', string='Therapist',
                                    domain=[('is_therapist', '=', True)])
    start_time = fields.Float(string='Start Time')
    end_time = fields.Float(string='End Time')
    duration = fields.Float(string='Duration (hrs)', compute='_compute_duration', store=True)
    patient_response = fields.Text(string='Patient Response / Notes')
    state = fields.Selection([
        ('pending', 'Pending'),
        ('done', 'Completed'),
        ('skipped', 'Skipped / Absent'),
    ], default='pending', tracking=True)
    skip_reason = fields.Char(string='Reason for Skip')
    invoice_id = fields.Many2one('account.move', string='Invoice', readonly=True)

    @api.depends('prescription_id', 'prescription_id.session_ids')
    def _compute_session_no(self):
        for rec in self:
            sessions = rec.prescription_id.session_ids.sorted('date')
            idx = list(sessions.ids).index(rec.id) + 1 if rec.id in sessions.ids else 1
            rec.session_no = idx
            rec.progress_display = f'Session {idx} of {rec.total_sessions}'

    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        for rec in self:
            rec.duration = rec.end_time - rec.start_time if rec.end_time > rec.start_time else 0.0

    def action_mark_done(self):
        """Mark session complete and create invoice if billing mode is per_visit."""
        self.ensure_one()
        self.write({'state': 'done'})

    def write(self, vals):
        res = super().write(vals)
        if vals.get('state') == 'done':
            for rec in self:
                billing = rec.prescription_id.billing_mode

                # ── Per Visit: invoice immediately after each session ──────────
                if billing == 'per_visit' and not rec.invoice_id:
                    rec._create_session_invoice()

                # ── Weekly: invoice for all sessions in the same week ──────────
                elif billing == 'weekly':
                    rec._create_weekly_invoice_if_needed()

                # ── End of Course: invoice only after ALL sessions done ────────
                elif billing == 'end_of_course':
                    if rec.prescription_id.pending_sessions <= 0:
                        rec.prescription_id._create_end_of_course_invoice()

                # Check if course is complete
                if rec.prescription_id.pending_sessions <= 0:
                    rec.prescription_id.state = 'done'
        return res

    def _create_weekly_invoice_if_needed(self):
        """
        Weekly billing: create ONE invoice per week covering all sessions done that week.
        If this week already has an invoice, just link this session to it.
        """
        from datetime import timedelta
        session_date = self.date or fields.Date.today()
        # Find Monday and Sunday of this session's week
        week_start = session_date - timedelta(days=session_date.weekday())
        week_end = week_start + timedelta(days=6)

        prescription = self.prescription_id
        # Get all done sessions in same week
        week_sessions = prescription.session_ids.filtered(
            lambda s: s.state == 'done'
            and s.date
            and week_start <= s.date <= week_end
        )

        # Check if any session in this week already has an invoice
        existing_invoice = week_sessions.filtered(
            lambda s: s.invoice_id
        ).mapped('invoice_id')[:1]

        if existing_invoice:
            # Link this session to the existing weekly invoice
            self.invoice_id = existing_invoice.id
            # Add a line to the existing invoice for this session
            existing_invoice.write({
                'invoice_line_ids': [(0, 0, {
                    'name': (f'{prescription.procedure_id.name} — '
                             f'{self.progress_display} ({self.date})'),
                    'quantity': 1,
                    'price_unit': prescription.session_rate or 0.0,
                })]
            })
        else:
            # First session done this week — create new weekly invoice
            rate = prescription.session_rate or 0.0
            if not rate:
                return
            move = self.env['account.move'].create({
                'move_type': 'out_invoice',
                'partner_id': self.patient_id.id,
                'invoice_date': week_end,  # invoice dated at end of week
                'invoice_origin': prescription.reference,
                'invoice_line_ids': [(0, 0, {
                    'name': (f'{prescription.procedure_id.name} — '
                             f'Week of {week_start} to {week_end}\n'
                             f'{self.progress_display} ({self.date})'),
                    'quantity': 1,
                    'price_unit': rate,
                })],
            })
            self.invoice_id = move.id

    def action_mark_skipped(self):
        self.ensure_one()
        self.state = 'skipped'

    def _create_session_invoice(self):
        rate = self.prescription_id.session_rate or 0.0
        if not rate:
            # Rate is 0 - log warning and return
            self.prescription_id.message_post(
                body=f'Note: Session invoice not created for {self.progress_display} '
                     f'because Rate per Session = 0. '
                     f'Please set the product Sales Price and re-run.',
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )
            return
        if not self.patient_id:
            return
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.patient_id.id,
            'invoice_date': self.date or fields.Date.today(),
            'invoice_origin': self.prescription_id.reference,
            'invoice_line_ids': [(0, 0, {
                'name': (f'{self.prescription_id.procedure_id.name} — '
                         f'{self.progress_display} ({self.date})'),
                'quantity': 1,
                'price_unit': rate,
            })],
        })
        self.invoice_id = move.id

    def action_create_missing_invoice(self):
        """Manually create invoice for completed session without invoice.
        Use this to fix sessions that completed before billing was configured."""
        self.ensure_one()
        if self.invoice_id:
            return {'type': 'ir.actions.act_window',
                    'res_model': 'account.move',
                    'res_id': self.invoice_id.id,
                    'view_mode': 'form'}
        self._create_session_invoice()
        if self.invoice_id:
            return {'type': 'ir.actions.act_window',
                    'res_model': 'account.move',
                    'res_id': self.invoice_id.id,
                    'view_mode': 'form'}