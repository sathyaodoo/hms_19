# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from .hospital_procedure_schedule import TIME_SLOTS


class HospitalInpatient(models.Model):
    _inherit = 'hospital.inpatient'

    patient_category = fields.Selection([
        ('payward', 'Pay Ward (Full Charges)'),
        ('ardram', 'Ardram (Concessional / Subsidised)'),
        ('karunyam', 'Karunyam (Charity / Free)'),
    ], string='IP Patient Category', default='payward', required=True, tracking=True)

    assigned_nurse_id = fields.Many2one('hr.employee', string='Assigned Nurse',
                                         domain=[('job_id.name', 'ilike', 'nurse')])
    diet_plan_id = fields.Many2one('hospital.diet.plan', string='Diet Plan')

    advance_percent = fields.Float(string='Advance %', default=30.0)
    advance_amount = fields.Monetary(string='Advance Collected', currency_field='currency_id')
    advance_payment_id = fields.Many2one('account.payment', string='Advance Payment', readonly=True)

    bystander_name = fields.Char(string='Bystander Name')
    bystander_relation = fields.Char(string='Relationship to Patient')
    bystander_pass_no = fields.Char(string='Bystander Pass No.', readonly=True)

    treatment_plan_ids = fields.One2many('hospital.treatment.plan', 'inpatient_id',
                                          string='Treatment Plans')
    medication_plan_ids = fields.One2many('hospital.medication.plan', 'inpatient_id',
                                           string='Medication Plans')
    food_supply_ids = fields.One2many('hospital.food.supply', 'inpatient_id',
                                       string='Food Supply Records')
    food_charges_total = fields.Monetary(string='Total Food Charges',
                                          compute='_compute_food_charges_total',
                                          store=True, currency_field='currency_id')
    room_transfer_ids = fields.One2many('hospital.room.transfer', 'inpatient_id',
                                         string='Room Transfers')
    consent_form_ids = fields.Many2many('ir.attachment', 'inpatient_consent_rel',
                                         'inpatient_id', 'attachment_id',
                                         string='Signed Consent Forms')
    followup_ids = fields.One2many('hospital.followup', 'source_ip_id',
                                    string='Follow-Up Records')
    service_charge = fields.Monetary(string='Service Charges', currency_field='currency_id')
    ot_charge = fields.Monetary(string='OT / Surgical Charges', currency_field='currency_id')
    ward_round_ids = fields.One2many('hospital.intern.ward.round', 'inpatient_id',
                                      string='Ward Round Logs')
    observer_intern_ids = fields.Many2many(
        'hospital.intern',
        'inpatient_observer_intern_rel',
        'inpatient_id', 'intern_id',
        string='Observing Interns',
    )

    # ── Identifiers & Department ───────────────────────────────────────────────
    uhid_no = fields.Char(related='patient_id.uhid_no', store=True, readonly=True, string='UHID No.')
    cop_no = fields.Char(string='COP No.')
    dop_no = fields.Char(string='DOP No.')
    source_op_id = fields.Many2one(
        'hospital.outpatient',
        string='Source OP Record',
        readonly=True,
        copy=False,
        help='OP Consultation from which this patient was admitted',
    )
    department_id = fields.Many2one(
        'hospital.department',
        string='Department',
        compute='_compute_department_id',
        store=True,
        readonly=False,
    )

    @api.depends('attending_doctor_id', 'source_op_id.department_id')
    def _compute_department_id(self):
        for rec in self:
            if rec.source_op_id and rec.source_op_id.department_id:
                rec.department_id = rec.source_op_id.department_id
            elif rec.attending_doctor_id:
                dept = self.env['hospital.department'].search([('member_ids', 'in', rec.attending_doctor_id.id)], limit=1)
                rec.department_id = dept or False
            elif not rec.department_id:
                rec.department_id = False

    # ── Initial Assessment Link ───────────────────────────────────────────────
    assessment_ids = fields.One2many(
        'hospital.op.assessment',
        'inpatient_id',
        string='Initial Assessments',
    )
    assessment_count = fields.Integer(
        string='Assessment Count',
        compute='_compute_assessment_count',
    )
    review_date = fields.Date(string='Review Date')

    # ── Procedure Schedule Link ───────────────────────────────────────────────
    procedure_schedule_ids = fields.One2many(
        'hospital.procedure.schedule',
        'inpatient_id',
        string='Procedure Schedules',
    )
    procedure_schedule_count = fields.Integer(
        string='Procedure Schedules Count',
        compute='_compute_procedure_schedule_count',
    )

    def _compute_procedure_schedule_count(self):
        for rec in self:
            rec.procedure_schedule_count = len(rec.procedure_schedule_ids)

    def action_open_procedure_schedule(self):
        """Open existing Procedure Schedule, or create+open a new one for this IP admission."""
        self.ensure_one()
        schedule = self.procedure_schedule_ids[:1]
        if not schedule:
            schedule = self.env['hospital.procedure.schedule'].create({
                'schedule_type': 'inpatient',
                'inpatient_id': self.id,
                'patient_id': self.patient_id.id,
                'visit_date': self.hosp_date or fields.Date.today(),
            })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Case Sheet (Procedure Schedule)',
            'res_model': 'hospital.procedure.schedule',
            'res_id': schedule.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ── Quick Add Procedure / Treatment Plan Controls ─────────────────────────
    quick_proc_date = fields.Date(string='Date', default=fields.Date.today)
    quick_proc_start_time = fields.Selection(TIME_SLOTS, string='Start Time', default='09:00:00 AM')
    quick_proc_end_time = fields.Selection(TIME_SLOTS, string='End Time', default='10:00:00 AM')
    quick_proc_duration = fields.Char(string='Duration', default='45m')
    quick_proc_procedure_id = fields.Many2one('product.template', string='Procedure',
                                              domain=[('is_procedure', '=', True)])
    quick_proc_room_id = fields.Many2one('patient.room', string='Treatment Room')
    quick_proc_staff_ids = fields.Many2many('hr.employee', 'inpatient_quick_proc_staff_rel',
                                            'inpatient_id', 'staff_id', string='Staff / Therapists')
    quick_proc_location = fields.Char(string='Location / Site')
    quick_proc_notes = fields.Text(string='Clinical Notes / Instructions')

    # Quick Medicines 1, 2, 3
    quick_proc_med_1 = fields.Many2one('product.template', string='Medicine 1',
                                       domain=[('medicine_ok', '=', True)])
    quick_proc_dose_1 = fields.Char(string='Dosage 1')
    quick_proc_unit_1 = fields.Char(string='Unit 1')

    quick_proc_med_2 = fields.Many2one('product.template', string='Medicine 2',
                                       domain=[('medicine_ok', '=', True)])
    quick_proc_dose_2 = fields.Char(string='Dosage 2')
    quick_proc_unit_2 = fields.Char(string='Unit 2')

    quick_proc_med_3 = fields.Many2one('product.template', string='Medicine 3',
                                       domain=[('medicine_ok', '=', True)])
    quick_proc_dose_3 = fields.Char(string='Dosage 3')
    quick_proc_unit_3 = fields.Char(string='Unit 3')

    def action_quick_add_procedure(self):
        """Adds a procedure session to Treatment Plan & Procedure Schedule."""
        self.ensure_one()
        if not self.quick_proc_procedure_id:
            raise UserError("Please select a Procedure / Therapy first.")
        plan_vals = {
            'inpatient_id': self.id,
            'procedure_id': self.quick_proc_procedure_id.id,
            'date': self.quick_proc_date or fields.Date.today(),
            'start_date': self.quick_proc_date or fields.Date.today(),
            'start_time': self.quick_proc_start_time or '09:00:00 AM',
            'end_time': self.quick_proc_end_time or '10:00:00 AM',
            'duration': self.quick_proc_duration or '45m',
            'location_site': self.quick_proc_location or '',
            'notes': self.quick_proc_notes or '',
            'instructions': self.quick_proc_notes or '',
            'treatment_room_id': self.quick_proc_room_id.id if self.quick_proc_room_id else False,
            'medicine_id_1': self.quick_proc_med_1.id if self.quick_proc_med_1 else False,
            'dosage_1': self.quick_proc_dose_1 or '',
            'unit_1': self.quick_proc_unit_1 or '',
            'medicine_id_2': self.quick_proc_med_2.id if self.quick_proc_med_2 else False,
            'dosage_2': self.quick_proc_dose_2 or '',
            'unit_2': self.quick_proc_unit_2 or '',
            'medicine_id_3': self.quick_proc_med_3.id if self.quick_proc_med_3 else False,
            'dosage_3': self.quick_proc_dose_3 or '',
            'unit_3': self.quick_proc_unit_3 or '',
            'staff_ids': [(6, 0, self.quick_proc_staff_ids.ids)],
            'therapist_ids': [(6, 0, self.quick_proc_staff_ids.ids)],
            'status': 'scheduled',
            'state': 'active',
        }
        self.env['hospital.treatment.plan'].create(plan_vals)
        self.write({
            'quick_proc_procedure_id': False,
            'quick_proc_med_1': False,
            'quick_proc_dose_1': '',
            'quick_proc_unit_1': '',
            'quick_proc_med_2': False,
            'quick_proc_dose_2': '',
            'quick_proc_unit_2': '',
            'quick_proc_med_3': False,
            'quick_proc_dose_3': '',
            'quick_proc_unit_3': '',
            'quick_proc_duration': '45m',
            'quick_proc_location': '',
            'quick_proc_notes': '',
            'quick_proc_room_id': False,
            'quick_proc_staff_ids': [(5, 0, 0)],
        })
        return True

    def _compute_assessment_count(self):
        for rec in self:
            rec.assessment_count = len(rec.assessment_ids)

    def action_open_assessment(self):
        """Open existing assessment, or create+open a new one for this IP admission."""
        self.ensure_one()
        assessment = self.assessment_ids[:1]
        if not assessment:
            assessment = self.env['hospital.op.assessment'].create({
                'assessment_type': 'inpatient',
                'inpatient_id': self.id,
                'patient_id': self.patient_id.id,
                'doctor_id': self.attending_doctor_id.id if self.attending_doctor_id else False,
            })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Initial Assessment Sheet - IP',
            'res_model': 'hospital.op.assessment',
            'res_id': assessment.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.depends('food_supply_ids.charge')
    def _compute_food_charges_total(self):
        for rec in self:
            rec.food_charges_total = sum(rec.food_supply_ids.mapped('charge'))

    def _compute_test_count(self):
        for rec in self:
            rec.test_count = self.env['lab.test.line'].sudo().search_count(
                [('ip_id', '=', rec.id)])

    # ── Room validation ────────────────────────────────────────────────────────
    @api.constrains('room_id', 'state')
    def _check_room_availability(self):
    
        for rec in self:
            if not rec.room_id or rec.state in ('draft', 'dis', 'cancel'):
                continue
            if rec.room_id.state == 'cleaning':
                raise ValidationError(
                    'Room "' + rec.room_id.name + '" is in Under Cleaning. '
                    'Please select a different room.'
                )
            conflict = self.search([
                ('room_id', '=', rec.room_id.id),
                ('state', 'in', ('reserve', 'admit', 'invoice')),
                ('id', '!=', rec.id),
            ], limit=1)
            if conflict:
                raise ValidationError(
                    'Room "' + rec.room_id.name + '" is already occupied by '
                    + conflict.patient_id.name + ' (' + conflict.name + '). '
                    + 'Please select a different room.'
                )

    # ── write() — update room/bed states on room/bed change ────────────────────
    def write(self, vals):
        if 'room_id' in vals:
            for rec in self:
                old_room = rec.room_id
                new_room_id = vals.get('room_id')
                if (old_room and new_room_id and
                        old_room.id != new_room_id and
                        rec.state in ('reserve', 'admit', 'invoice')):
                    old_room.sudo().write({'state': 'avail'})
                    self.env['patient.room'].browse(new_room_id).sudo().write({'state': 'not'})
        if 'bed_id' in vals:
            for rec in self:
                old_bed = rec.bed_id
                new_bed_id = vals.get('bed_id')
                if (old_bed and new_bed_id and
                        old_bed.id != new_bed_id and
                        rec.state in ('reserve', 'admit', 'invoice')):
                    old_bed.sudo().write({'state': 'avail'})
                    self.env['hospital.bed'].browse(new_bed_id).sudo().write({'state': 'not'})
        res = super().write(vals)
        # Auto-create case log when interns added to IP ward round
        if vals.get('observer_intern_ids'):
            for rec in self:
                for intern in rec.observer_intern_ids:
                    existing = self.env['hospital.case.log'].search([
                        ('intern_id', '=', intern.id),
                        ('inpatient_id', '=', rec.id),
                        ('source', '=', 'ward_round'),
                    ], limit=1)
                    if not existing:
                        self.env['hospital.case.log'].create({
                            'intern_id': intern.id,
                            'date': fields.Date.today(),
                            'source': 'ward_round',
                            'case_type': 'general',
                            'exposure_type': 'observed',
                            'inpatient_id': rec.id,
                            'summary': 'IP Ward Round: ' + rec.name + ' — ' + (rec.patient_id.name or ''),
                        })
        return res

    def action_reserve(self):
        for rec in self:
            if rec.bed_id and rec.bed_id.state == 'cleaning':
                raise UserError(
                    'Bed "' + rec.bed_id.name + '" is in Under Cleaning. '
                    'Please select a different bed.'
                )
            if rec.room_id and rec.room_id.state == 'cleaning':
                raise UserError(
                    'Room "' + rec.room_id.name + '" is in Under Cleaning. '
                    'Please select a different room.'
                )
        res = super().action_reserve()
        for rec in self:
            if rec.bed_id:
                rec.bed_id.state = 'reserve'
        return res
        return res

    # ── Admit ──────────────────────────────────────────────────────────────────
    def action_admit(self):
        for rec in self:
            if rec.room_id and rec.room_id.state not in ('avail', 'reserve'):
                raise UserError(
                    'Room "' + rec.room_id.name + '" is not available. '
                    'Current status: ' + rec.room_id.state + '. '
                    'Please select an available room.'
                )
            if rec.bed_id and rec.bed_id.state not in ('avail', 'reserve'):   # ← was: != 'avail'
                raise UserError('Bed "' + rec.bed_id.name + '" is not available.')
            if not rec.consent_form_ids:
                rec.message_post(
                    body='Note: Patient admitted without signed consent form.',
                    message_type='comment',
                    subtype_xmlid='mail.mt_note',
                )
        res = super().action_admit()
        for rec in self:
            if rec.room_id:
                rec.room_id.sudo().write({'state': 'not'})
        return res

    # ── Discharge ──────────────────────────────────────────────────────────────
    def action_discharge(self):
        if self.bed_id:
            self.bed_id.sudo().write({'state': 'cleaning'})
            self.bed_id.housekeeping_notes = (
                'Cleaning required after discharge of ' + self.patient_id.name +
                ' (' + self.name + ') on ' + str(fields.Date.today())
            )
        if self.room_id:
            self.room_id.sudo().write({'state': 'cleaning'})
            self.room_id.housekeeping_notes = (
                'Cleaning required after discharge of ' + self.patient_id.name +
                ' (' + self.name + ') on ' + str(fields.Date.today())
            )
        self.sudo().write({'state': 'dis', 'discharge_date': fields.Date.today()})

    # ── Bystander Pass ─────────────────────────────────────────────────────────
    def action_generate_bystander_pass(self):
        self.ensure_one()
        if not self.bystander_name:
            raise UserError('Please enter bystander name before generating pass.')
        if not self.bystander_pass_no:
            self.bystander_pass_no = self.env['ir.sequence'].next_by_code(
                'bystander.pass') or 'BP/001'
        return self.env.ref(
            'santhigiri_hms.action_report_bystander_pass').report_action(self)

    # ── 9-Component Invoice ────────────────────────────────────────────────────
    def action_invoice(self):
        for rec in self:
            if rec.invoice_id:
                raise UserError('Invoice already exists for this admission.')
            lines = []
            doc_round_count = len(rec.doctor_round_ids)
            if doc_round_count:
                fee_master = self.env['hospital.fee.master'].search([
                    ('patient_category', '=', rec.patient_category or 'payward'),
                    ('active', '=', True),
                ], limit=1)
                consult_rate = fee_master.amount if fee_master else 0.0
                if consult_rate:
                    lines.append((0, 0, {
                        'name': 'Consultation Fee (' + str(doc_round_count) + ' visit(s))',
                        'quantity': doc_round_count,
                        'price_unit': consult_rate,
                    }))
            if rec.room_rent_amount:
                lines.append((0, 0, {
                    'name': 'Room Charges (' + str(rec.admit_days) + ' day(s))',
                    'quantity': 1, 'price_unit': rec.room_rent_amount,
                }))
            if rec.bed_rent_amount:
                lines.append((0, 0, {
                    'name': 'Bed Charges (' + str(rec.admit_days) + ' day(s))',
                    'quantity': 1, 'price_unit': rec.bed_rent_amount,
                }))
            if rec.service_charge:
                lines.append((0, 0, {
                    'name': 'Service Charges', 'quantity': 1,
                    'price_unit': rec.service_charge,
                }))
            for tp in rec.treatment_plan_ids.filtered(lambda t: t.state == 'done'):
                if tp.procedure_charge:
                    lines.append((0, 0, {
                        'name': 'Procedure: ' + tp.procedure_id.name,
                        'quantity': 1, 'price_unit': tp.procedure_charge,
                    }))
            if rec.ot_charge:
                lines.append((0, 0, {
                    'name': 'OT / Surgical Charges',
                    'quantity': 1, 'price_unit': rec.ot_charge,
                }))
            for mp in rec.medication_plan_ids:
                if mp.total_charge:
                    lines.append((0, 0, {
                        'name': 'Medicines: ' + mp.medicine_id.name,
                        'quantity': 1, 'price_unit': mp.total_charge,
                    }))
            for lab in rec.lab_test_ids:
                lab_total = sum(lab.test_ids.mapped('price'))
                if lab_total:
                    lines.append((0, 0, {
                        'name': 'Lab Tests', 'quantity': 1,
                        'price_unit': lab_total,
                    }))
            if rec.food_charges_total:
                lines.append((0, 0, {
                    'name': 'Diet / Food Charges',
                    'quantity': 1, 'price_unit': rec.food_charges_total,
                }))
            if rec.advance_amount:
                lines.append((0, 0, {
                    'name': 'Less: Advance Paid',
                    'quantity': 1, 'price_unit': -rec.advance_amount,
                }))
            if not lines:
                raise UserError('No chargeable items found for this admission.')
            move = self.env['account.move'].create({
                'move_type': 'out_invoice',
                'partner_id': rec.patient_id.id,
                'invoice_date': fields.Date.today(),
                'invoice_origin': rec.name,
                'invoice_line_ids': lines,
            })
            rec.invoice_id = move.id
            rec.state = 'invoice'
            rec.is_invoice = True
        return True

    # ── IP Pharmacy ────────────────────────────────────────────────────────────
    def action_dispense_ip_medicines(self):
        self.ensure_one()
        if not self.medication_plan_ids:
            raise UserError('No medicines in Medication Plan.')
        order_lines = []
        for med in self.medication_plan_ids:
            if not med.medicine_id:
                continue
            product = self.env['product.product'].sudo().search(
                [('product_tmpl_id', '=', med.medicine_id.id)], limit=1)
            if not product:
                continue
            order_lines.append((0, 0, {
                'product_id': product.id,
                'product_uom_qty': med.duration_days or 1,
                'price_unit': product.list_price,
                'name': med.medicine_id.name,
            }))
        if not order_lines:
            raise UserError('No valid medicines found in Medication Plan.')
        sale_order = self.env['sale.order'].sudo().create({
            'partner_id': self.patient_id.id,
            'dispensing_category': 'patient_medication',
            'inpatient_id': self.id,
            'order_line': order_lines,
        })
        sale_order.action_confirm()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': sale_order.id,
            'view_mode': 'form',
            'name': 'IP Medication Dispensing',
        }

    def action_view_invoice(self):
        self.ensure_one()
        if self.invoice_id:
            return {
                'name': 'Discharge Invoice',
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'res_id': self.invoice_id.id,
                'view_mode': 'form',
                'context': {'create': False},
            }
        return {
            'name': 'Inpatient Invoice',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('invoice_origin', '=', self.name)],
            'context': {'create': False},
        }
        
    def action_ip_daily_procedures(self):
        """IP + Daily Procedures — same wizard concept as the OP
        side's "OP + Daily Procedures" button
        (hospital.outpatient.action_outcome_procedures in
        hospital_outpatient.py): opens the exact same
        hospital.procedure.prescription popup form, just pre-filled
        from this IP admission (inpatient_id) instead of an OP visit
        (outpatient_id) — so an admitted patient gets identical
        Completed/Remaining/Progress % session tracking, without
        needing to route everything through a separate OP visit
        first. attending_doctor_id is already an hr.employee directly
        on hospital.inpatient (unlike hospital.outpatient.doctor_id,
        which points at doctor.allocation), so it can be passed
        straight through as default_doctor_id with no extra lookup."""
        self.ensure_one()
        return {
            'name': 'Create Procedure Prescription',
            'type': 'ir.actions.act_window',
            'res_model': 'hospital.procedure.prescription',
            'view_mode': 'form',
            'context': {
                'default_inpatient_id': self.id,
                'default_patient_id': self.patient_id.id,
                'default_doctor_id': self.attending_doctor_id.id,
            },
            'target': 'new',
        }

    def action_print_discharge_summary(self):
        return self.env.ref(
            'santhigiri_hms.action_report_discharge_summary').report_action(self)
            
            
    # ── Bed validation ─────────────────────────────────────────────────────────
    @api.constrains('bed_id', 'state')
    def _check_bed_availability(self):
        """Same concept as _check_room_availability() above: a bed that
        is already reserved/admitted/invoiced for another inpatient
        cannot be assigned to a second one. Also blocks assigning a bed
        that is currently Under Cleaning — same concept, same message
        style as the "already occupied" check, just a different reason
        the bed isn't available for a new admission right now."""
        for rec in self:
            if not rec.bed_id or rec.state in ('draft', 'dis', 'cancel'):
                continue
            if rec.bed_id.state == 'cleaning':
                raise ValidationError(
                    'Bed "' + rec.bed_id.name + '" is in Under Cleaning. '
                    'Please select a different bed.'
                )
            conflict = self.search([
                ('bed_id', '=', rec.bed_id.id),
                ('state', 'in', ('reserve', 'admit', 'invoice')),
                ('id', '!=', rec.id),
            ], limit=1)
            if conflict:
                raise ValidationError(
                    'Bed "' + rec.bed_id.name + '" is already occupied by '
                    + conflict.patient_id.name + ' (' + conflict.name + '). '
                    + 'Please select a different bed.'
                )


class HospitalRoomTransfer(models.Model):
    _name = 'hospital.room.transfer'
    _description = 'IP Room Transfer'
    _order = 'transfer_date desc'

    inpatient_id = fields.Many2one('hospital.inpatient', required=True,
                                    ondelete='cascade', index=True)
    patient_id = fields.Many2one(related='inpatient_id.patient_id', store=True)

    from_room_id = fields.Many2one('patient.room', string='Current Room',
                                    compute='_compute_from_room',
                                    store=True, readonly=True)
    to_room_id = fields.Many2one('patient.room', string='Transfer To Room',
                                  required=True)
    transfer_date = fields.Date(string='Transfer Date', required=True,
                                 default=fields.Date.today)
    reason = fields.Text(string='Reason for Transfer')
    authorised_by = fields.Many2one('hr.employee', string='Authorised By')
    state = fields.Selection([('draft', 'Draft'), ('done', 'Done')], default='draft')

    @api.depends('inpatient_id.room_id')
    def _compute_from_room(self):
        for rec in self:
            rec.from_room_id = rec.inpatient_id.room_id if rec.inpatient_id else False

    def action_confirm_transfer(self):
        for rec in self:
            if not rec.to_room_id:
                raise UserError('Please select a room to transfer to.')
            if rec.to_room_id.state != 'avail':
                raise UserError(
                    'Room "' + rec.to_room_id.name + '" is not available. '
                    'Current status: ' + rec.to_room_id.state
                )
            # Update IP room → triggers write() → updates room states
            rec.inpatient_id.sudo().write({'room_id': rec.to_room_id.id})
            rec.state = 'done'