# -*- coding: utf-8 -*-
"""
Hospital Patient Screening (NCISM Guidelines Compliant).
Covers:
(c) Screening carried out by trained person / interns
(d) Departmental OPD and specialty OPD routing criteria
(e) Chief complaints, height, weight, BMI, blood pressure, temperature,
    Naadi recording by equipment, and basic Ayurvedic parameters
(f) Screening counters in accordance with patient flow
+ One-click 'Move to OP' action carrying all vitals & clinical details to OP consultation.
"""
from odoo import api, fields, models
from odoo.exceptions import UserError


class HospitalPatientScreening(models.Model):
    _name = 'hospital.patient.screening'
    _description = 'Patient OPD Screening (NCISM Standard)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string='Screening Ref', default='New', readonly=True, copy=False, tracking=True)
    date = fields.Datetime(string='Screening Date & Time', default=fields.Datetime.now, required=True, tracking=True)
    state = fields.Selection([
        ('draft', 'Waiting / Registered'),
        ('in_progress', 'Under Screening'),
        ('screened', 'Screened / Completed'),
        ('op_created', 'Moved to OP'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    # ── Patient Information ───────────────────────────────────────────────────
    patient_id = fields.Many2one(
        'res.partner', string='Patient', required=True, tracking=True,
        domain="[('patient_seq', '!=', False), ('patient_seq', 'not in', ['New', 'Employee', 'User']), ('is_company', '=', False)]",
        help='Registered patients from Reception / Registration',
    )
    uhid_no = fields.Char(string='UHID No.', readonly=True)
    patient_phone = fields.Char(string='Phone Number')
    patient_age = fields.Integer(string='Age')
    patient_gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ], string='Gender')
    patient_category = fields.Selection([
        ('payward', 'Pay Ward'),
        ('jeevanam', 'Jeevanam'),
        ('amrutham', 'Amrutham'),
    ], string='Patient Category', default='payward', tracking=True)

    # ── (c) Screener & (f) Counter Details ────────────────────────────────────
    screened_by_role = fields.Selection([
        ('intern', 'Intern (Fully Established College)'),
        ('trained_person', 'Trained Person (College Under Establishment)'),
        ('doctor', 'Medical Officer / Doctor'),
        ('nurse', 'Staff Nurse'),
    ], string='Screened By Category', default='intern', required=True, tracking=True,
       help='Screening carried out by trained person or intern as per NCISM guidelines')
    screened_by_id = fields.Many2one('hr.employee', string='Screened By (Staff / Doctor)',
                                     default=lambda self: self.env.user.employee_id)
    intern_id = fields.Many2one('hospital.intern', string='Screening Intern',
                                domain=[('state', '=', 'active')])
    counter_no = fields.Char(string='Screening Counter No.', default='Counter 1',
                             help='Screening counter in accordance with patient flow')

    # ── (d) Departmental Routing & Triage ─────────────────────────────────────
    department_id = fields.Many2one('hospital.department', string='Recommended Department (OPD)', ondelete='set null', tracking=True,
                                    help='Ayurveda OPD department decided as per screening criteria')
    specialty_opd = fields.Char(string='Specialty OPD', help='Specialty Out Patient Department if any')
    doctor_id = fields.Many2one('hr.employee', string='Recommended Doctor', domain=[('doctor', '=', True)])
    triage_priority = fields.Selection([
        ('routine', 'Routine / Normal Flow'),
        ('priority', 'Priority (Elderly / Pediatric / Antenatal)'),
        ('urgent', 'Urgent (Severe Pain / Acute Discomfort)'),
        ('emergency', 'Emergency (Refer to Casualty)'),
    ], string='Triage Priority', default='routine', tracking=True)

    # ── (e) Chief Complaints ──────────────────────────────────────────────────
    chief_complaints = fields.Text(string='Chief Complaints & Duration', required=True)
    complaint_ids = fields.One2many('hospital.screening.complaint', 'screening_id',
                                    string='Complaints Breakdown', copy=True)

    # ── (e) Physical Parameters & Vitals ─────────────────────────────────────
    height = fields.Float(string='Height (cm)', digits=(5, 1))
    weight = fields.Float(string='Weight (kg)', digits=(5, 1))
    bmi = fields.Float(string='BMI', compute='_compute_bmi', store=True, digits=(4, 2))
    bmi_category = fields.Selection([
        ('underweight', 'Underweight (< 18.5)'),
        ('normal', 'Normal (18.5 - 24.9)'),
        ('overweight', 'Overweight (25 - 29.9)'),
        ('obese', 'Obese (≥ 30)'),
    ], string='BMI Category', compute='_compute_bmi', store=True)

    bp_systolic = fields.Integer(string='BP Systolic (mmHg)')
    bp_diastolic = fields.Integer(string='BP Diastolic (mmHg)')
    blood_pressure = fields.Char(string='Blood Pressure', compute='_compute_blood_pressure', store=True)
    pulse = fields.Integer(string='Pulse / Heart Rate (bpm)')
    temperature = fields.Float(string='Temperature (°F)', default=98.4, digits=(4, 1))
    respiratory_rate = fields.Integer(string='Respiratory Rate (/min)')
    spo2 = fields.Integer(string='SpO2 (%)')
    blood_sugar_rbs = fields.Float(string='Blood Sugar RBS (mg/dL)')

    # ── (e) Naadi Recording (Ayurvedic Pulse Examination) ─────────────────────
    naadi_equipment_used = fields.Boolean(string='Recorded by Naadi Equipment?', default=True,
                                          help='Naadi recording carried out by Naadi recording equipment')
    naadi_equipment_name = fields.Char(string='Equipment / Device Name',
                                       default='Digital Nadi Sensor / Nadi Tarangini')
    naadi_type = fields.Selection([
        ('vata', 'Vata (Sarpa Gati - Fast / Feeble / Crooked)'),
        ('pitta', 'Pitta (Manduka Gati - Jumping / Fast / Bounding)'),
        ('kapha', 'Kapha (Hamsa Gati - Slow / Steady / Heavy)'),
        ('vata_pitta', 'Vata-Pitta'),
        ('pitta_kapha', 'Pitta-Kapha'),
        ('vata_kapha', 'Vata-Kapha'),
        ('tridosha', 'Sannipataja / Tridosha'),
    ], string='Dominant Naadi (Dosha)')
    naadi_gati = fields.Char(string='Naadi Gati / Rhythm')
    naadi_rate = fields.Integer(string='Naadi Rate (bpm)')
    naadi_findings = fields.Text(string='Naadi Recording Observations / Findings')

    # ── Basic Ayurvedic Parameters ───────────────────────────────────────────
    tongue_jihva = fields.Selection([
        ('normal', 'Niram / Clear / Normal'),
        ('coated', 'Sam / Coated (Ama Present)'),
        ('dry', 'Dry / Rough'),
        ('pale', 'Pale / Pandu'),
        ('red', 'Red / Rakta'),
    ], string='Tongue (Jihva Pariksha)')
    bowel_koshtha = fields.Selection([
        ('krura', 'Krura Koshtha (Hard / Constipated)'),
        ('madhya', 'Madhya Koshtha (Moderate / Normal)'),
        ('mridu', 'Mridu Koshtha (Soft / Loose)'),
    ], string='Bowel (Koshtha)')
    appetite_agni = fields.Selection([
        ('sama', 'Samagni (Balanced / Normal)'),
        ('vishama', 'Vishamagni (Irregular / Vata)'),
        ('tikshna', 'Tikshnagni (Excessive / Pitta)'),
        ('manda', 'Mandagni (Low / Sluggish / Kapha)'),
    ], string='Digestive Fire (Agni)')
    screening_notes = fields.Text(string='Screening Observations / Notes for OPD')

    # ── Link to OP & Destination ──────────────────────────────────────────────
    outpatient_id = fields.Many2one('hospital.outpatient', string='Created OP Record', readonly=True, copy=False)

    # ── Computes & Onchanges ──────────────────────────────────────────────────
    @api.onchange('patient_id')
    def _onchange_patient_id(self):
        if self.patient_id:
            p = self.patient_id
            self.uhid_no = p.uhid_no or ''
            self.patient_phone = p.phone or p.mobile or ''
            self.patient_age = p.age or 0
            self.patient_gender = p.gender or False
            self.patient_category = p.patient_category or 'payward'

    @api.depends('height', 'weight')
    def _compute_bmi(self):
        for rec in self:
            if rec.height and rec.height > 0 and rec.weight and rec.weight > 0:
                h_m = rec.height / 100.0
                bmi_val = round(rec.weight / (h_m * h_m), 2)
                rec.bmi = bmi_val
                if bmi_val < 18.5:
                    rec.bmi_category = 'underweight'
                elif bmi_val < 25.0:
                    rec.bmi_category = 'normal'
                elif bmi_val < 30.0:
                    rec.bmi_category = 'overweight'
                else:
                    rec.bmi_category = 'obese'
            else:
                rec.bmi = 0.0
                rec.bmi_category = False

    @api.depends('bp_systolic', 'bp_diastolic')
    def _compute_blood_pressure(self):
        for rec in self:
            if rec.bp_systolic or rec.bp_diastolic:
                rec.blood_pressure = f"{rec.bp_systolic or 0}/{rec.bp_diastolic or 0} mmHg"
            else:
                rec.blood_pressure = ''

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                seq = self.env['ir.sequence'].next_by_code('hospital.patient.screening') or 'SCR/001'
                vals['name'] = seq
            if vals.get('patient_id'):
                p = self.env['res.partner'].browse(vals['patient_id'])
                if p.exists():
                    if not vals.get('uhid_no') and p.uhid_no:
                        vals['uhid_no'] = p.uhid_no
                    if not vals.get('patient_phone') and (p.phone or p.mobile):
                        vals['patient_phone'] = p.phone or p.mobile
                    if not vals.get('patient_age') and getattr(p, 'age', False):
                        vals['patient_age'] = p.age
                    if not vals.get('patient_gender') and getattr(p, 'gender', False):
                        vals['patient_gender'] = p.gender
                    if not vals.get('patient_category') and getattr(p, 'patient_category', False):
                        vals['patient_category'] = p.patient_category
        return super().create(vals_list)

    # ── Workflow State Actions ────────────────────────────────────────────────
    def action_start_screening(self):
        self.ensure_one()
        self.write({'state': 'in_progress'})

    def action_mark_screened(self):
        self.ensure_one()
        self.write({'state': 'screened'})

    def action_cancel(self):
        self.ensure_one()
        self.write({'state': 'cancel'})

    # ── Move from Screening to OP Action ─────────────────────────────────────
    def action_move_to_op(self):
        """
        Converts/moves this screening record directly to an Outpatient (OP) consultation.
        Transfers: Patient, UHID, Recommended Department & Doctor, Category,
        Chief complaints, Vitals, and Ayurvedic examination findings.
        """
        self.ensure_one()
        if self.outpatient_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'OP Consultation Record',
                'res_model': 'hospital.outpatient',
                'res_id': self.outpatient_id.id,
                'view_mode': 'form',
                'target': 'current',
            }

        # 1. Ensure patient partner exists
        partner = self.patient_id
        if not partner:
            raise UserError("Please select a Patient before moving to OP.")

        # 2. Find matching Doctor Allocation for the department / doctor
        today = fields.Date.today()
        allocation = False
        if self.doctor_id:
            allocation = self.env['doctor.allocation'].search([
                ('doctor_id', '=', self.doctor_id.id),
                ('date', '=', today),
                ('state', '=', 'confirm'),
            ], limit=1)
        if not allocation and self.department_id:
            allocation = self.env['doctor.allocation'].search([
                ('department_id', '=', self.department_id.id),
                ('date', '=', today),
                ('state', '=', 'confirm'),
            ], limit=1)
        if not allocation:
            allocation = self.env['doctor.allocation'].search([
                ('date', '=', today),
                ('state', '=', 'confirm'),
            ], limit=1)
        if not allocation:
            allocation = self.env['doctor.allocation'].search([], limit=1)

        dept_id = self.department_id.id if self.department_id else (
            allocation.department_id.id if allocation and allocation.department_id else False
        )
        if not dept_id:
            dept_id = self.env['hospital.department'].search([], limit=1).id

        # 3. Build OP Complaints Table lines
        complaint_lines = []
        if self.complaint_ids:
            for c in self.complaint_ids:
                complaint_lines.append((0, 0, {
                    'name': c.name,
                    'notes': c.duration or c.notes or '',
                }))
        elif self.chief_complaints:
            complaint_lines.append((0, 0, {
                'name': self.chief_complaints,
                'notes': 'From Initial Screening',
            }))

        # 4. Build OP Clinical Examination lines from Screening Vitals & Naadi
        exam_lines = []
        # Vitals
        vitals_text = []
        if self.bp_systolic or self.bp_diastolic:
            vitals_text.append(f"BP: {self.bp_systolic}/{self.bp_diastolic} mmHg")
        if self.pulse:
            vitals_text.append(f"Pulse: {self.pulse} bpm")
        if self.temperature:
            vitals_text.append(f"Temp: {self.temperature} °F")
        if self.spo2:
            vitals_text.append(f"SpO2: {self.spo2}%")
        if self.respiratory_rate:
            vitals_text.append(f"RR: {self.respiratory_rate}/min")
        if self.blood_sugar_rbs:
            vitals_text.append(f"RBS: {self.blood_sugar_rbs} mg/dL")

        if vitals_text:
            exam_lines.append((0, 0, {
                'name': 'Screening Vitals',
                'notes': ", ".join(vitals_text),
            }))

        # Anthropometry / BMI
        if self.height or self.weight or self.bmi:
            bmi_cat_label = dict(self._fields['bmi_category'].selection).get(self.bmi_category, '') if self.bmi_category else ''
            exam_lines.append((0, 0, {
                'name': 'Anthropometry / BMI',
                'notes': f"Height: {self.height} cm, Weight: {self.weight} kg, BMI: {self.bmi} ({bmi_cat_label})",
            }))

        # Naadi Pariksha
        if self.naadi_type or self.naadi_findings or self.naadi_gati:
            naadi_label = dict(self._fields['naadi_type'].selection).get(self.naadi_type, self.naadi_type or '')
            naadi_desc = f"Dominant: {naadi_label}"
            if self.naadi_gati:
                naadi_desc += f", Gati: {self.naadi_gati}"
            if self.naadi_rate:
                naadi_desc += f", Rate: {self.naadi_rate} bpm"
            if self.naadi_findings:
                naadi_desc += f". Findings: {self.naadi_findings}"
            if self.naadi_equipment_used:
                naadi_desc += f" [Device: {self.naadi_equipment_name or 'Naadi Sensor'}]"
            exam_lines.append((0, 0, {
                'name': 'Naadi Pariksha (Pulse Examination)',
                'notes': naadi_desc,
            }))

        # Basic Ayurvedic Parameters (Jihva / Agni / Koshtha)
        ayur_text = []
        if self.tongue_jihva:
            t_label = dict(self._fields['tongue_jihva'].selection).get(self.tongue_jihva, '')
            ayur_text.append(f"Jihva (Tongue): {t_label}")
        if self.appetite_agni:
            a_label = dict(self._fields['appetite_agni'].selection).get(self.appetite_agni, '')
            ayur_text.append(f"Agni: {a_label}")
        if self.bowel_koshtha:
            k_label = dict(self._fields['bowel_koshtha'].selection).get(self.bowel_koshtha, '')
            ayur_text.append(f"Koshtha: {k_label}")
        if ayur_text:
            exam_lines.append((0, 0, {
                'name': 'Ashtavidha / Basic Parameters',
                'notes': ", ".join(ayur_text),
            }))

        # 5. Create OP Consultation record
        op_vals = {
            'patient_id': partner.id,
            'department_id': dept_id,
            'doctor_id': allocation.id if allocation else False,
            'op_date': today,
            'registration_datetime': fields.Datetime.now(),
            'patient_category': self.patient_category or partner.patient_category or 'payward',
            'reason': self.chief_complaints or 'Screening Consultation',
            'chief_complaint': self.chief_complaints or '',
            'screening_id': self.id,
            'complaint_ids': complaint_lines,
            'examination_ids': exam_lines,
            'visit_type': 'new',
        }
        op = self.env['hospital.outpatient'].create(op_vals)

        # 6. Update screening state and link
        self.write({
            'state': 'op_created',
            'outpatient_id': op.id,
        })

        # 7. Post chatter messages
        op_label = op.op_reference or f"OP #{op.id}"
        self.message_post(
            body=f"Patient screening completed and moved to OP: <strong>{op_label}</strong>.<br/>"
                 f"Assigned Department: <strong>{self.department_id.name}</strong>.",
            subtype_xmlid="mail.mt_note",
        )
        op.message_post(
            body=f"OP Consultation generated from Screening Ref: <strong>{self.name}</strong>.<br/>"
                 f"Screened By: <strong>{self.screened_by_id.name if self.screened_by_id else self.screened_by_role}</strong> "
                 f"at <strong>{self.counter_no}</strong>.",
            subtype_xmlid="mail.mt_note",
        )

        return {
            'type': 'ir.actions.act_window',
            'name': 'OP Consultation Record',
            'res_model': 'hospital.outpatient',
            'res_id': op.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_op_record(self):
        """Stat button: Opens the linked OP record."""
        self.ensure_one()
        if not self.outpatient_id:
            raise UserError("No OP record linked to this screening yet.")
        return {
            'type': 'ir.actions.act_window',
            'name': 'OP Consultation Record',
            'res_model': 'hospital.outpatient',
            'res_id': self.outpatient_id.id,
            'view_mode': 'form',
            'target': 'current',
        }


class HospitalScreeningComplaint(models.Model):
    _name = 'hospital.screening.complaint'
    _description = 'Screening Chief Complaint Line'
    _order = 'sequence, id'

    screening_id = fields.Many2one('hospital.patient.screening', string='Screening',
                                   ondelete='cascade', required=True, index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Complaint', required=True)
    duration = fields.Char(string='Duration')
    notes = fields.Char(string='Notes / Severity')
