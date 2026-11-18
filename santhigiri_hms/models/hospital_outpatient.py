# -*- coding: utf-8 -*-
"""
hospital.outpatient extensions for Santhigiri HMS.
BASE MODULE already handles:
  op_reference, patient_id, doctor_id (→ doctor.allocation), op_date, reason,
  state (draft/op/inpatient/invoice/cancel), prescription_ids, test_ids, invoice_id,
  create_invoice(), action_convert_to_inpatient(), action_confirm(), action_print_prescription().
THIS FILE ADDS:
  - Registration fields: UHID, COP, DOP auto-generation
  - Date & Time of Registration
  - Referred by & Claim (Yes/No)
  - Categories: Jeevanam, Pay ward, Amrutham
  - Department Allotment
  - Registration Fee Amount & Accounts Payment Reception fetch
  - Auto-fetch of all patient details when old patient ID is entered
  - 3-Outcome routing (Regular OP / Daily Procedures / IP Admission)
"""
from odoo import api, fields, models
from odoo.exceptions import UserError


class HospitalOutpatient(models.Model):
    _inherit = 'hospital.outpatient'

    # ── Identifiers: UHID, COP, DOP ───────────────────────────────────────────
    uhid_no = fields.Char(
        string='UHID No.',
        index=True,
        copy=False,
        help='Unique Health ID / Hospital ID of the patient',
    )
    cop_no = fields.Char(
        string='COP No.',
        index=True,
        readonly=True,
        copy=False,
        help='Central Outpatient Number generated upon registration',
    )
    dop_no = fields.Char(
        string='DOP No.',
        index=True,
        readonly=True,
        copy=False,
        help='Department Outpatient Number generated upon registration',
    )
    registration_datetime = fields.Datetime(
        string='Registration Date & Time',
        default=fields.Datetime.now,
        required=True,
        index=True,
        help='Exact date and time when the patient was registered at reception',
    )

    # ── Registration & Referral ───────────────────────────────────────────────
    claim = fields.Selection(
        selection=[('yes', 'Yes'), ('no', 'No')],
        string='Claim (Insurance / Mediclaim)',
        default='no',
        required=True,
        tracking=True,
        help='Yes or No option indicating if this visit is under an insurance/mediclaim claim',
    )
    is_referred = fields.Boolean(string='Referred Patient', default=False)
    referred_by = fields.Char(
        string='Referred By',
        tracking=True,
        help='Doctor, Hospital, Clinic, or Person referring the patient',
    )
    referring_hospital = fields.Char(string='Referring Hospital / Clinic')
    referral_date = fields.Date(string='Referral Date')
    referral_reason = fields.Text(string='Reason for Referral')
    referral_document_ids = fields.Many2many(
        'ir.attachment',
        'op_referral_doc_rel',
        'op_id', 'attachment_id',
        string='Referral Letter / Documents',
    )

    # ── Department & Doctor ───────────────────────────────────────────────────
    department_id = fields.Many2one(
        'hr.department',
        string='Department Allotted',
        required=True,
        index=True,
        tracking=True,
        help='Medical department allotted from registration',
    )
    appointment_id = fields.Many2one(
        'hospital.appointment',
        string='Source Appointment',
        readonly=True,
        copy=False,
    )
    appointment_reason = fields.Selection(
        selection=[
            ('consultation', 'Consultation'),
            ('counselling', 'Counselling'),
            ('yoga', 'Yoga'),
        ],
        string='Reason for Appointment',
    )

    # ── Patient Auto-fetch Helpers ─────────────────────────────────────────────
    patient_phone = fields.Char(string='Phone Number')
    patient_age = fields.Integer(string='Age')
    patient_gender = fields.Selection(related='patient_id.gender', string='Gender', readonly=True)
    visit_type = fields.Selection([
        ('new', 'New Visit'),
        ('followup', 'Follow-up'),
    ], string='Visit Type', default='new', compute='_compute_visit_type', store=True, readonly=False, tracking=True)

    # ── Category & Fee ─────────────────────────────────────────────────────────
    patient_category = fields.Selection([
        ('jeevanam', 'Jeevanam'),
        ('payward', 'Pay Ward'),
        ('amrutham', 'Amrutham'),
        ('general', 'General'),
        ('senior_citizen', 'Senior Citizen'),
        ('bpl', 'BPL / Karunyam'),
        ('ardram', 'Ardram'),
    ], string='Patient Category', default='jeevanam', required=True, tracking=True)

    category_fee = fields.Monetary(
        string='Consultation Fee (Category)',
        compute='_compute_category_fee',
        store=True,
        currency_field='currency_id',
        help='Auto-fetched from fee master based on category',
    )
    registration_fee = fields.Monetary(
        string='Registration Fee Amount',
        currency_field='currency_id',
        default=0.0,
        tracking=True,
        help='Registration fee charged at reception / accounts',
    )
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda s: s.env.company.currency_id,
    )

    # ── Accounts Payment Reception ─────────────────────────────────────────────
    accounts_payment_status = fields.Selection([
        ('pending', 'Pending Accounts'),
        ('received', 'Received by Accounts'),
        ('waived', 'Waived / Free'),
    ], string='Payment Status (Accounts)', default='pending', tracking=True)
    payment_amount_received = fields.Monetary(
        string='Payment Received by Accounts',
        currency_field='currency_id',
        copy=False,
        help='Amount received by accounts section for registration/consultation',
    )
    payment_received_date = fields.Datetime(
        string='Payment Received On',
        copy=False,
        help='Date and time when accounts section received the payment',
    )

    camp_id = fields.Many2one(
        'hospital.camp',
        string='Medical Camp',
        domain=[('state', '=', 'active')],
        help='Link this OP visit to a Medical Camp for auto-discount billing.',
    )

    # ── Outcome / Routing ─────────────────────────────────────────────────────
    outcome = fields.Selection([
        ('regular', 'Regular OP (Discharged)'),
        ('procedure', 'OP + Daily Procedures'),
        ('inpatient', 'IP Admission'),
    ], string='Consultation Outcome', tracking=True)

    procedure_prescription_ids = fields.One2many(
        'hospital.procedure.prescription',
        'outpatient_id',
        string='Procedure Prescriptions',
    )

    # ── Interns observing this consultation ───────────────────────────────────
    observer_intern_ids = fields.Many2many(
        'hospital.intern',
        'op_intern_observer_rel',
        'op_id',
        'intern_id',
        string='Observing Interns',
    )

    # ── Follow-up ─────────────────────────────────────────────────────────────
    followup_date = fields.Date(string='Follow-Up Date')
    followup_notes = fields.Text(string='Follow-Up Instructions')
    followup_id = fields.Many2one('hospital.followup', string='Follow-Up Record', readonly=True)

    # ── Case Sheet Fields ─────────────────────────────────────────────────────
    chief_complaint = fields.Text(string='Chief Complaint')
    examination_findings = fields.Text(string='Examination Findings')
    provisional_diagnosis = fields.Text(string='Provisional Diagnosis')
    treatment_notes = fields.Text(string='Treatment Notes / Plan')

    # ── OP Clinical Consultation Tables (Complaints, History, Exam, Diagnosis, Advices) ──
    complaint_ids = fields.One2many(
        'hospital.op.complaint', 'outpatient_id',
        string='Presenting Complaints', copy=True,
    )
    history_ids = fields.One2many(
        'hospital.op.history', 'outpatient_id',
        string='Medical History', copy=True,
    )
    examination_ids = fields.One2many(
        'hospital.op.examination', 'outpatient_id',
        string='Clinical Examination', copy=True,
    )
    diagnosis_ids = fields.One2many(
        'hospital.op.diagnosis', 'outpatient_id',
        string='Diagnosis', copy=True,
    )
    advice_ids = fields.One2many(
        'hospital.op.advice', 'outpatient_id',
        string='Advices', copy=True,
    )

    def action_submit_op_record(self):
        """SUBMIT OP RECORD: confirms consultation and marks OP recorded."""
        for rec in self:
            if rec.state == 'draft':
                rec.action_confirm()
            if rec.state == 'op':
                rec.state = 'opdone'
            rec.message_post(
                body="<strong>OP Clinical Record Submitted</strong><br/>"
                     "Consultation details (Complaints, History, Examination, Investigations, Diagnosis, Advices, Prescriptions, Procedures) submitted successfully.",
                subtype_xmlid="mail.mt_note",
            )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'OP Record Submitted',
                'message': 'OP consultation record has been submitted successfully.',
                'type': 'success',
                'sticky': False,
            }
        }

    # ── Procedure Schedule Link ───────────────────────────────────────────────
    procedure_schedule_ids = fields.One2many(
        'hospital.procedure.schedule',
        'outpatient_id',
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
        """Open existing Procedure Schedule, or create+open a new one for this OP visit."""
        self.ensure_one()
        schedule = self.procedure_schedule_ids[:1]
        if not schedule:
            schedule = self.env['hospital.procedure.schedule'].create({
                'schedule_type': 'outpatient',
                'outpatient_id': self.id,
                'patient_id': self.patient_id.id,
                'visit_date': self.op_date or fields.Date.today(),
            })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Case Sheet (Procedure Schedule)',
            'res_model': 'hospital.procedure.schedule',
            'res_id': schedule.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ── Inpatient Admission Link ──────────────────────────────────────────────
    inpatient_id = fields.Many2one(
        'hospital.inpatient',
        string='Inpatient Admission',
        readonly=True,
        copy=False,
        help='Linked Inpatient admission if patient was moved/admitted to IP',
    )
    inpatient_count = fields.Integer(
        string='Inpatient Count',
        compute='_compute_inpatient_count',
    )

    def _compute_inpatient_count(self):
        for rec in self:
            rec.inpatient_count = 1 if rec.inpatient_id else 0

    def action_open_inpatient(self):
        """Open the linked IP admission form."""
        self.ensure_one()
        if not self.inpatient_id:
            return self.action_outcome_inpatient()
        return {
            'type': 'ir.actions.act_window',
            'name': 'IP Admission',
            'res_model': 'hospital.inpatient',
            'res_id': self.inpatient_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ── Patient Screening Link ────────────────────────────────────────────────
    screening_id = fields.Many2one(
        'hospital.patient.screening',
        string='Screening Record',
        readonly=True,
        copy=False,
        help='Linked OPD screening record from which this OP consultation was created',
    )
    screening_count = fields.Integer(
        string='Screening Count',
        compute='_compute_screening_count',
    )

    def _compute_screening_count(self):
        for rec in self:
            rec.screening_count = 1 if rec.screening_id else 0

    def action_open_screening(self):
        """Open the linked Screening form."""
        self.ensure_one()
        if not self.screening_id:
            raise UserError("No screening record linked to this OP record.")
        return {
            'type': 'ir.actions.act_window',
            'name': 'Patient Screening Record',
            'res_model': 'hospital.patient.screening',
            'res_id': self.screening_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ── Auto-fetch on Patient Change ──────────────────────────────────────────
    @api.onchange('patient_id')
    def _onchange_patient_id_fetch_all(self):
        """
        When patient ID is entered/selected:
        All registration details automatically fetch:
        UHID, Category, Claim (Yes/No), Referred By, Phone, Age, Gender.
        """
        if self.patient_id:
            p = self.patient_id
            self.uhid_no = p.uhid_no or (p.patient_seq if p.patient_seq not in ('Employee', 'User', 'New') else '')
            if p.patient_category:
                self.patient_category = p.patient_category
            if p.claim:
                self.claim = p.claim
            if p.referred_by:
                self.referred_by = p.referred_by
                self.is_referred = True
            self.patient_phone = p.phone or getattr(p, 'mobile', '') or ''
            self.patient_age = p.age or 0

    @api.onchange('doctor_id')
    def _onchange_doctor_set_dept(self):
        """When doctor allocation is selected, set department automatically."""
        if self.doctor_id and self.doctor_id.department_id:
            self.department_id = self.doctor_id.department_id

    @api.onchange('department_id')
    def _onchange_department_id_update_dop(self):
        """Update DOP number to match selected department code if in draft or new."""
        if self.department_id and (not self.state or self.state == 'draft'):
            code = self._get_department_code(self.department_id.name)
            curr_code = self.dop_no.split('/')[-1] if self.dop_no and '/' in self.dop_no else ''
            if curr_code != code:
                self.dop_no = self._next_dop_number(code)

    # ── Computed ───────────────────────────────────────────────────────────────
    @api.depends('patient_id')
    def _compute_visit_type(self):
        """Auto-detect New Visit vs Follow-up based on prior OP records for this patient."""
        for rec in self:
            if rec.patient_id:
                domain = [('patient_id', '=', rec.patient_id.id)]
                if rec.id:
                    domain.append(('id', '!=', rec.id))
                prior_count = self.search_count(domain)
                rec.visit_type = 'followup' if prior_count > 0 else 'new'
            else:
                rec.visit_type = 'new'

    @api.depends('patient_category', 'department_id')
    def _compute_category_fee(self):
        FeeMaster = self.env['hospital.fee.master']
        for rec in self:
            domain = [
                ('patient_category', '=', rec.patient_category),
                ('active', '=', True),
            ]
            if rec.department_id:
                fee_rec = FeeMaster.search(domain + [('department_id', '=', rec.department_id.id)], limit=1)
                if not fee_rec:
                    fee_rec = FeeMaster.search(domain + [('department_id', '=', False)], limit=1)
            else:
                fee_rec = FeeMaster.search(domain, limit=1)
            rec.category_fee = fee_rec.amount if fee_rec else 0.0

    @api.model
    def _get_department_code(self, dept_name):
        """
        Map department name to standard SAMC (Santhigiri Ayurveda Medical College) code:
          - KYC: Kayachikitsa
          - PKM: Panchakarma
          - PSR: Prasootitantra & Striroga
          - KMB: Kaumarbhrithya (Balroga)
          - SLY: Salyatantra (Shalya Tantra)
          - SLK: Salakyatantra (Shalakya Tantra)
          - SWS: Swasthya Rakshana / Swasthavritta & Yoga
          - CLT: Casualty / Emergency
          - AGT: Agada Tantra
        """
        if not dept_name:
            return 'GEN'
        n = dept_name.lower().strip()
        if 'admin' in n:
            return 'ADM'
        elif 'kaya' in n:
            return 'KYC'
        elif 'pancha' in n:
            return 'PKM'
        elif any(k in n for k in ('prasoo', 'prasut', 'stri', 'stree')):
            return 'PSR'
        elif any(k in n for k in ('kaumar', 'bala', 'child')):
            return 'KMB'
        elif any(k in n for k in ('salya', 'shalya', 'surg')):
            return 'SLY'
        elif any(k in n for k in ('salakya', 'shalakya', 'ent', 'eye')):
            return 'SLK'
        elif any(k in n for k in ('swasth', 'yoga')):
            return 'SWS'
        elif any(k in n for k in ('casua', 'emerg')):
            return 'CLT'
        elif any(k in n for k in ('agad', 'tox', 'visha')):
            return 'AGT'
        else:
            words = dept_name.split()
            if len(words) >= 3:
                return ''.join([w[0].upper() for w in words[:3]])
            elif len(words) == 2:
                return (words[0][:2] + words[1][:1]).upper()
            return dept_name[:3].upper()

    def _next_dop_number(self, dept_code):
        """
        Generate sequential Department OP Number (DOP No.) per department code.
        Format: {count}/{dept_code} (e.g. 1/ADM, 2/ADM, 1/AGT, 2/AGT, 1/PSR, 1/GEN...).
        Each department has its own independent sequential numbering starting from 1.
        """
        dept_code = dept_code.upper().strip() if dept_code else 'GEN'
        existing_records = self.sudo().search([('dop_no', '=like', f'%/{dept_code}')])
        max_num = 0
        for r in existing_records:
            if r.dop_no and '/' in r.dop_no:
                prefix = r.dop_no.split('/')[0].strip()
                if prefix.isdigit():
                    num = int(prefix)
                    if num > max_num:
                        max_num = num
        next_num = max_num + 1
        return f"{next_num}/{dept_code}"

    # ── Create: Generate UHID, COP, DOP ───────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # 1. UHID generation for patient if not present
            partner_id = vals.get('patient_id')
            if partner_id:
                partner = self.env['res.partner'].browse(partner_id)
                if partner.exists():
                    if not partner.uhid_no:
                        uhid = self.env['ir.sequence'].next_by_code('santhigiri.uhid') or partner.patient_seq or ''
                        partner.sudo().write({'uhid_no': uhid})
                    if not vals.get('uhid_no'):
                        vals['uhid_no'] = partner.uhid_no

            # 2. COP Number (Central OP Number)
            if not vals.get('cop_no'):
                vals['cop_no'] = self.env['ir.sequence'].next_by_code('santhigiri.cop') or 'COP/0001'

            # 3. DOP Number (Department OP Number - department-specific sequence)
            if not vals.get('dop_no'):
                dept_code = 'GEN'
                if vals.get('department_id'):
                    dept = self.env['hr.department'].browse(vals['department_id'])
                    if dept.exists() and dept.name:
                        dept_code = self._get_department_code(dept.name)
                vals['dop_no'] = self._next_dop_number(dept_code)

            # 4. Registration Date & Time default
            if not vals.get('registration_datetime'):
                vals['registration_datetime'] = fields.Datetime.now()

            # 5. Fallback op_reference from base logic if needed
            if vals.get('op_reference', 'New') == 'New' and vals.get('cop_no'):
                vals['op_reference'] = vals['cop_no']

        return super().create(vals_list)

    # ── Accounts Payment Reception Action ─────────────────────────────────────
    def action_receive_registration_fee(self):
        """
        Called when account section receives the patient or records the payment.
        Updates payment received amount, timestamp, and status in the registration tab.
        """
        for rec in self:
            total_fee = (rec.registration_fee or 0.0) + (rec.category_fee or 0.0)
            rec.write({
                'accounts_payment_status': 'received',
                'payment_amount_received': total_fee,
                'payment_received_date': fields.Datetime.now(),
            })
            rec.message_post(
                body=f"<b>Accounts Payment Confirmed:</b> Amount received: {total_fee} "
                     f"(Registration Fee: {rec.registration_fee}, Consultation Fee: {rec.category_fee}) "
                     f"on {fields.Datetime.now().strftime('%d/%m/%Y %H:%M:%S')}.",
                message_type='notification',
            )
        return True

    # ── Override create_invoice to include registration & category fee ────────
    def create_invoice(self):
        """Override to include consultation fee and registration fee."""
        for rec in self:
            if rec.invoice_id:
                raise UserError('Invoice already created for this OP.')
            invoice_lines = []
            if rec.category_fee:
                invoice_lines.append((0, 0, {
                    'name': f'Consultation Fee — {rec.cop_no or rec.op_reference} ({rec.get_patient_category_label()})',
                    'quantity': 1,
                    'price_unit': rec.category_fee,
                }))
            if rec.registration_fee:
                invoice_lines.append((0, 0, {
                    'name': f'Registration Fee — {rec.cop_no or rec.op_reference} ({rec.uhid_no or ""})',
                    'quantity': 1,
                    'price_unit': rec.registration_fee,
                }))
            if not invoice_lines:
                invoice_lines.append((0, 0, {
                    'name': f'Consultation / Registration Fee — {rec.cop_no or rec.op_reference}',
                    'quantity': 1,
                    'price_unit': 0.0,
                }))

            move = self.env['account.move'].create({
                'move_type': 'out_invoice',
                'partner_id': rec.patient_id.id,
                'invoice_date': fields.Date.today(),
                'invoice_line_ids': invoice_lines,
            })
            rec.invoice_id = move.id
            rec.state = 'invoice'
            rec.invoiced = True
        return True

    def get_patient_category_label(self):
        self.ensure_one()
        labels = dict(self._fields['patient_category'].selection)
        return labels.get(self.patient_category, '')

    # ── 3-Outcome Routing Buttons ─────────────────────────────────────────────
    def action_outcome_regular(self):
        """Outcome 1: Regular OP — prescription routed to pharmacy."""
        self.ensure_one()
        self.outcome = 'regular'
        self.state = 'opdone'
        if self.followup_date:
            self._create_followup()
        return True

    def action_outcome_procedures(self):
        """Outcome 2: OP + Daily Procedures — opens procedure prescription wizard."""
        self.ensure_one()
        self.outcome = 'procedure'
        return {
            'name': 'Create Procedure Prescription',
            'type': 'ir.actions.act_window',
            'res_model': 'hospital.procedure.prescription',
            'view_mode': 'form',
            'context': {
                'default_outpatient_id': self.id,
                'default_patient_id': self.patient_id.id,
            },
            'target': 'new',
        }

    def action_outcome_inpatient(self):
        """Outcome 3: Move / Admit Patient from OP to IP with all matching details."""
        self.ensure_one()

        # If already admitted, simply navigate to the existing IP admission
        if self.inpatient_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'IP Admission',
                'res_model': 'hospital.inpatient',
                'res_id': self.inpatient_id.id,
                'view_mode': 'form',
                'target': 'current',
            }

        # 1. Category mapping (OP -> IP)
        cat_map = {
            'payward': 'payward',
            'jeevanam': 'ardram',
            'amrutham': 'karunyam',
        }
        ip_cat = cat_map.get(self.patient_category, 'payward')

        # 2. Attending doctor (comodel is hr.employee)
        doc_emp_id = False
        if self.doctor_id and self.doctor_id.doctor_id:
            doc_emp_id = self.doctor_id.doctor_id.id
        elif hasattr(self.env.user, 'employee_id') and self.env.user.employee_id:
            doc_emp_id = self.env.user.employee_id.id
        if not doc_emp_id:
            doc_emp = self.env['hr.employee'].search([('job_id.name', 'ilike', 'doctor')], limit=1)
            doc_emp_id = doc_emp.id if doc_emp else False

        # 3. Assemble clinical condition summary from OP Case Sheet
        cond_parts = []
        if self.complaint_ids:
            cond_parts.append("Presenting Complaints:\n" + "\n".join(
                f"• {c.name}" + (f" ({c.notes})" if c.notes else "") for c in self.complaint_ids
            ))
        if self.history_ids:
            cond_parts.append("Medical History:\n" + "\n".join(
                f"• {h.name}" + (f" ({h.notes})" if h.notes else "") for h in self.history_ids
            ))
        if self.examination_ids:
            cond_parts.append("Clinical Examination:\n" + "\n".join(
                f"• {e.name}" + (f" ({e.notes})" if e.notes else "") for e in self.examination_ids
            ))
        if self.diagnosis_ids:
            cond_parts.append("Diagnosis:\n" + "\n".join(
                f"• {d.name}" + (f" ({d.notes})" if d.notes else "") for d in self.diagnosis_ids
            ))
        if self.advice_ids:
            cond_parts.append("Advices:\n" + "\n".join(
                f"• {a.name}" + (f" ({a.notes})" if a.notes else "") for a in self.advice_ids
            ))
        condition_text = "\n\n".join(cond_parts) if cond_parts else (self.examination_findings or '')

        # 4. Reason for admission
        diag_names = ", ".join(self.diagnosis_ids.mapped('name'))
        reason_text = self.reason or (f"Admission for {diag_names}" if diag_names else (self.chief_complaint or f"Admitted from OP {self.cop_no or self.op_reference}"))

        # 5. Prescriptions -> IP Medication Plan + base prescription lines
        med_lines = []
        base_presc_lines = []
        for p in self.prescription_ids:
            route_val = p.route if p.route in ('oral', 'external', 'nasal', 'rectal') else 'oral'
            timing_note = []
            if p.timing:
                timing_note.append(f"Timing: {p.timing}")
            if p.note:
                timing_note.append(f"{p.note}")
            instructions = (p.remarks or '') + (f" [{', '.join(timing_note)}]" if timing_note else "")

            med_lines.append((0, 0, {
                'medicine_id': p.medicine_id.id,
                'dosage': p.dosage or '',
                'route': route_val,
                'anupanam': p.anupanam or '',
                'duration_days': p.duration_days or 7,
                'start_date': fields.Date.today(),
                'instructions': instructions,
            }))
            base_presc_lines.append((0, 0, {
                'medicine_id': p.medicine_id.id,
                'quantity': p.quantity or 1.0,
                'no_intakes': p.no_intakes or 1,
                'note': p.note or '',
                'time': p.time or '',
            }))

        # 6. Procedures -> IP Treatment Plans
        treat_lines = []
        for proc in self.procedure_prescription_ids:
            proc_date = proc.start_date or fields.Date.today()
            treat_lines.append((0, 0, {
                'procedure_id': proc.procedure_id.id,
                'date': proc_date,
                'start_date': proc_date,
                'start_time': '09:00:00 AM',
                'end_time': '10:00:00 AM',
                'duration': '45m',
                'location_site': proc.site_location or '',
                'no_of_sessions': proc.no_of_sessions or 7,
                'therapist_ids': [(6, 0, proc.therapist_ids.ids)],
                'staff_ids': [(6, 0, proc.therapist_ids.ids)],
                'instructions': proc.instructions or '',
                'notes': proc.instructions or '',
                'status': 'scheduled',
                'state': 'active',
            }))

        # 7. Create Inpatient record
        ip_vals = {
            'patient_id': self.patient_id.id,
            'source_op_id': self.id,
            'cop_no': self.cop_no or self.op_reference or '',
            'dop_no': self.dop_no or '',
            'attending_doctor_id': doc_emp_id,
            'type_admission': 'routine',
            'patient_category': ip_cat,
            'hosp_date': fields.Date.today(),
            'reason': reason_text,
            'condition': condition_text,
            'observer_intern_ids': [(6, 0, self.observer_intern_ids.ids)],
            'medication_plan_ids': med_lines,
            'prescription_ids': base_presc_lines,
            'treatment_plan_ids': treat_lines,
        }
        ip = self.env['hospital.inpatient'].sudo().create(ip_vals)

        # 8. Link to OP and update state
        self.write({
            'inpatient_id': ip.id,
            'outcome': 'inpatient',
            'state': 'inpatient',
        })
        self.message_post(
            body=f"Patient admitted to IP: <strong>{ip.name}</strong>.<br/>"
                 f"Clinical details, {len(med_lines)} medicines, and {len(treat_lines)} procedure therapies transferred to IP record.",
            subtype_xmlid="mail.mt_note",
        )

        return {
            'type': 'ir.actions.act_window',
            'name': 'IP Admission',
            'res_model': 'hospital.inpatient',
            'res_id': ip.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _create_followup(self):
        """Create a follow-up record after OP consultation."""
        self.ensure_one()
        followup = self.env['hospital.followup'].create({
            'patient_id': self.patient_id.id,
            'followup_date': self.followup_date,
            'reason': f'Post OP follow-up ({self.cop_no or self.op_reference})',
            'advised_by': self.env.user.employee_id.id if hasattr(self.env.user, 'employee_id') else False,
            'source_op_id': self.id,
        })
        self.followup_id = followup.id

    # ── Auto-log intern observation ────────────────────────────────────────────
    def write(self, vals):
        if 'department_id' in vals and vals['department_id']:
            dept = self.env['hr.department'].browse(vals['department_id'])
            if dept.exists() and dept.name:
                new_code = self._get_department_code(dept.name)
                for rec in self:
                    if not rec.dop_no or rec.dop_no.endswith('/GEN'):
                        vals['dop_no'] = self._next_dop_number(new_code)
        res = super().write(vals)
        if vals.get('observer_intern_ids'):
            for rec in self:
                for intern in rec.observer_intern_ids:
                    self.env['hospital.case.log'].create({
                        'intern_id': intern.id,
                        'date': rec.op_date or fields.Date.today(),
                        'source': 'op_observation',
                        'case_type': 'general',
                        'exposure_type': 'observed',
                        'summary': f'OP observation: {rec.cop_no or rec.op_reference} — {rec.provisional_diagnosis or rec.reason or ""}',
                    })
        return res

    def action_dispense_op_prescription(self):
        self.ensure_one()
        if not self.prescription_ids:
            raise UserError('No medicines in Prescription.')
        order_lines = []
        for presc in self.prescription_ids:
            if not presc.medicine_id:
                continue
            product = self.env['product.product'].sudo().search(
                [('product_tmpl_id', '=', presc.medicine_id.id)], limit=1)
            if not product:
                continue
            order_lines.append((0, 0, {
                'product_id': product.id,
                'product_uom_qty': presc.quantity or 1,
                'price_unit': product.list_price,
                'name': presc.medicine_id.name,
            }))
        if not order_lines:
            raise UserError('No valid medicines found in Prescription.')
        sale_order = self.env['sale.order'].sudo().create({
            'partner_id': self.patient_id.id,
            'dispensing_category': 'op_dispensing',
            'outpatient_id': self.id,
            'order_line': order_lines,
        })
        sale_order.action_confirm()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': sale_order.id,
            'view_mode': 'form',
            'name': 'OP Prescription Dispensing',
        }


class HospitalOPComplaint(models.Model):
    _name = 'hospital.op.complaint'
    _description = 'OP Presenting Complaint'
    _order = 'sequence, id'

    outpatient_id = fields.Many2one('hospital.outpatient', string='OP Visit', ondelete='cascade', index=True)
    sequence = fields.Integer(string='Sr.No.', default=1)
    name = fields.Char(string='Complaint', required=True)
    notes = fields.Char(string='Notes / Duration')


class HospitalOPHistory(models.Model):
    _name = 'hospital.op.history'
    _description = 'OP Medical History'
    _order = 'id'

    outpatient_id = fields.Many2one('hospital.outpatient', string='OP Visit', ondelete='cascade', index=True)
    name = fields.Text(string='Medical History', required=True)
    notes = fields.Char(string='Notes')


class HospitalOPExamination(models.Model):
    _name = 'hospital.op.examination'
    _description = 'OP Clinical Examination'
    _order = 'id'

    outpatient_id = fields.Many2one('hospital.outpatient', string='OP Visit', ondelete='cascade', index=True)
    name = fields.Char(string='Examination', required=True)
    notes = fields.Char(string='Findings / Notes')


class HospitalOPDiagnosis(models.Model):
    _name = 'hospital.op.diagnosis'
    _description = 'OP Diagnosis'
    _order = 'id'

    outpatient_id = fields.Many2one('hospital.outpatient', string='OP Visit', ondelete='cascade', index=True)
    name = fields.Char(string='Diagnosis', required=True)
    notes = fields.Char(string='Notes')


class HospitalOPAdvice(models.Model):
    _name = 'hospital.op.advice'
    _description = 'OP Advice & Instructions'
    _order = 'id'

    outpatient_id = fields.Many2one('hospital.outpatient', string='OP Visit', ondelete='cascade', index=True)
    name = fields.Text(string='Advice', required=True)
    notes = fields.Char(string='Notes')
