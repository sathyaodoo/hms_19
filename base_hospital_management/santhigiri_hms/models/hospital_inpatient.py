# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


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

    # ── write() — update room states on room change ────────────────────────────
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
        return super().write(vals)

    # ── Admit ──────────────────────────────────────────────────────────────────
    def action_admit(self):
        for rec in self:
            if rec.room_id and rec.room_id.state not in ('avail', 'reserve'):
                raise UserError(
                    'Room "' + rec.room_id.name + '" is not available. '
                    'Current status: ' + rec.room_id.state + '. '
                    'Please select an available room.'
                )
            if rec.bed_id and rec.bed_id.state != 'avail':
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
            self.bed_id.state = 'avail'
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

    def action_print_discharge_summary(self):
        return self.env.ref(
            'santhigiri_hms.action_report_discharge_summary').report_action(self)


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