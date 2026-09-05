# -*- coding: utf-8 -*-
"""
res.partner extensions for Santhigiri HMS.
BASE MODULE already provides:
  date_of_birth, blood_group, rh_type, gender, marital_status, is_alive,
  patient_seq, barcode, barcode_png, risk (allergy notes), insurance_id,
  family_ids, lab_test_ids, prescription_ids, economic_level, income, notes.
THIS FILE ADDS:
  nationality, aadhaar_no, passport_no, visa_no, arrival_date, immigration_copy,
  vulnerability, payward_preference, jeevanam_scheme, geo_location,
  allergy_ids (proper allergy field), duplicate constraint, EMR action,
  emergency_contact_name, emergency_contact_phone, existing_conditions,
  form_c_submitted_date.
"""
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # ── Age (computed from base module's date_of_birth) ──────────────────────
    age = fields.Integer(string='Age', compute='_compute_age', store=True)
    age_manual = fields.Integer(
        string='Age (Approx., if DOB unknown)',
        help='Enter approximate age only when exact Date of Birth is not available.',
    )

    @api.depends('date_of_birth', 'age_manual')
    def _compute_age(self):
        today = fields.Date.today()
        for rec in self:
            if rec.date_of_birth:
                dob = rec.date_of_birth
                rec.age = today.year - dob.year - (
                    (today.month, today.day) < (dob.month, dob.day))
            elif rec.age_manual:
                rec.age = rec.age_manual
            else:
                rec.age = False

    # ── Nationality & ID ───────────────────────────────────────────────────────
    nationality = fields.Selection(
        selection=[('indian', 'Indian'), ('foreign', 'Foreign National')],
        string='Nationality',
        default='indian',
        tracking=True,
    )
    aadhaar_no = fields.Char(
        string='Aadhaar Number',
        help='Optional for Indian nationals',
        size=14,
    )
    passport_no = fields.Char(
        string='Passport Number',
        help='Mandatory for foreign nationals',
    )
    visa_no = fields.Char(string='VISA Number')
    visa_type = fields.Char(string='VISA Type')
    arrival_date = fields.Date(
        string='Arrival Date in India',
        help='Date of arrival — mandatory for foreign nationals',
    )
    port_of_entry = fields.Char(string='Port of Entry')
    immigration_copy = fields.Binary(
        string='Immigration Copy',
        attachment=True,
        help='Scanned immigration document — mandatory for foreign nationals',
    )
    immigration_filename = fields.Char(string='Immigration File Name')
    form_c_ref = fields.Char(string='Form C Reference No.')
    form_c_submitted_date = fields.Date(string='Form C Submitted On')

    # ── Emergency Contact ──────────────────────────────────────────────────────
    emergency_contact_name = fields.Char(string='Emergency Contact Name')
    emergency_contact_phone = fields.Char(string='Emergency Contact Phone')

    # ── Clinical ───────────────────────────────────────────────────────────────
    # NOTE: base module has 'risk' (Text) as "Genetic Risks" — we repurpose + extend
    allergy_ids = fields.Many2many(
        'santhigiri.allergy',
        'partner_allergy_rel',
        'partner_id',
        'allergy_id',
        string='Known Allergies',
        help='Select all known allergies — a red alert will appear on all clinical screens',
    )
    existing_conditions = fields.Text(
        string='Existing Medical Conditions',
        help='Known chronic or pre-existing conditions',
    )

    # ── Santhigiri-Specific Classification ────────────────────────────────────
    vulnerability = fields.Selection(
        selection=[
            ('bpl', 'BPL (Below Poverty Line)'),
            ('differently_abled', 'Differently Abled'),
            ('senior_citizen', 'Senior Citizen (60+)'),
            ('none', 'None'),
        ],
        string='Vulnerability',
        default='none',
    )
    payward_preference = fields.Char(
        string='Payward / Ward Preference',
        help='Preferred ward or room type',
    )
    jeevanam_scheme = fields.Boolean(
        string='Jeevanam Scheme',
        help='Enrolled in Jeevanam government health scheme',
    )
    geo_location = fields.Char(
        string='Geographical Location',
        help='City / District / State for area-wise reporting and patient tracking',
    )

    # ── Computed ───────────────────────────────────────────────────────────────
    has_allergy = fields.Boolean(
        string='Has Allergy',
        compute='_compute_has_allergy',
        store=True,
    )
    allergy_summary = fields.Char(
        string='Allergy Summary',
        compute='_compute_has_allergy',
        store=True,
    )

    # ── Constraints ───────────────────────────────────────────────────────────
    @api.constrains('nationality', 'passport_no', 'arrival_date')
    def _check_foreign_patient_mandatory_fields(self):
        for rec in self:
            if rec.nationality == 'foreign':
                if not rec.passport_no:
                    raise ValidationError(
                        'Passport Number is mandatory for foreign nationals.'
                    )
                if not rec.arrival_date:
                    raise ValidationError(
                        'Arrival Date in India is mandatory for foreign nationals.'
                    )

    @api.constrains('aadhaar_no')
    def _check_duplicate_aadhaar(self):
        for rec in self:
            if rec.aadhaar_no:
                dup = self.search([
                    ('aadhaar_no', '=', rec.aadhaar_no),
                    ('id', '!=', rec.id),
                    ('patient_seq', '!=', False),
                ])
                if dup:
                    raise ValidationError(
                        f'A patient with Aadhaar {rec.aadhaar_no} already exists: '
                        f'{dup[0].name} ({dup[0].patient_seq})'
                    )

    @api.constrains('passport_no')
    def _check_duplicate_passport(self):
        for rec in self:
            if rec.passport_no:
                dup = self.search([
                    ('passport_no', '=', rec.passport_no),
                    ('id', '!=', rec.id),
                    ('patient_seq', '!=', False),
                ])
                if dup:
                    raise ValidationError(
                        f'A patient with Passport No. {rec.passport_no} already exists:\n'
                        f'Name: {dup[0].name}\n'
                        f'Patient ID: {dup[0].patient_seq}\n'
                        f'Please open the existing record instead of creating a new one.'
                    )

    @api.constrains('phone', 'name', 'date_of_birth')
    def _check_duplicate_phone_name_dob(self):
        """
        Duplicate check: same Phone + same Name + same Date of Birth
        catches duplicate registrations when Aadhaar/Passport not provided.
        """
        for rec in self:
            if not rec.patient_seq:
                # Only check for patient records (has patient_seq)
                continue
            if rec.phone and rec.name and rec.date_of_birth:
                dup = self.search([
                    ('phone', '=', rec.phone),
                    ('name', 'ilike', rec.name),
                    ('date_of_birth', '=', rec.date_of_birth),
                    ('id', '!=', rec.id),
                    ('patient_seq', '!=', False),
                ])
                if dup:
                    raise ValidationError(
                        f'A patient with the same Name, Phone and Date of Birth already exists:\n'
                        f'Name: {dup[0].name}\n'
                        f'Phone: {dup[0].phone}\n'
                        f'DOB: {dup[0].date_of_birth}\n'
                        f'Patient ID: {dup[0].patient_seq}\n'
                        f'Please check if this is a duplicate registration.'
                    )

    # ── Computed Methods ───────────────────────────────────────────────────────
    @api.depends('allergy_ids')
    def _compute_has_allergy(self):
        for rec in self:
            rec.has_allergy = bool(rec.allergy_ids)
            rec.allergy_summary = ', '.join(rec.allergy_ids.mapped('name')) if rec.allergy_ids else ''

    # ── EMR Timeline Action ────────────────────────────────────────────────────
    def action_open_emr_timeline(self):
        """Open a unified EMR timeline showing all patient interactions."""
        self.ensure_one()
        return {
            'name': f'EMR Timeline — {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'santhigiri.emr.event',
            'view_mode': 'list,form',
            'domain': [('patient_id', '=', self.id)],
            'context': {'default_patient_id': self.id},
        }

    # ── Form C Report Action ──────────────────────────────────────────────────
    def action_print_form_c(self):
        self.ensure_one()
        if self.nationality != 'foreign':
            raise ValidationError('Form C is only applicable for foreign nationals.')
        return self.env.ref('santhigiri_hms.action_report_form_c').report_action(self)


    def action_generate_patient_card(self):
        """
        Override to pass self as docids (not None) so Odoo 19
        populates res_ids in the rendering pipeline.
        The actual data injection happens in IrActionsReportPatientCardFix.
        """
        # Ensure barcode is generated (base module logic)
        if not self.barcode:
            try:
                # Generate barcode via base logic
                from pyBarcode import EAN13
                from barcode.writer import ImageWriter
                import base64
                ean = self.sudo().generate_ean(str(self.id))
                self.sudo().write({'barcode': ean})
                my_code = EAN13(str(self.barcode), writer=ImageWriter())
                my_code.save("code")
                with open('code.png', 'rb') as f:
                    self.sudo().write({'barcode_png': base64.b64encode(f.read())})
            except Exception:
                pass  # barcode generation is optional

        return self.env.ref(
            'base_hospital_management.action_report_patient_card'
        ).report_action(self)  # pass self — not None


class SanthigiriAllergy(models.Model):
    """Master list of known allergens."""
    _name = 'santhigiri.allergy'
    _description = 'Allergy Master'
    _order = 'name'

    name = fields.Char(string='Allergy / Allergen', required=True)
    category = fields.Selection([
        ('medicine', 'Medicine'),
        ('food', 'Food'),
        ('environmental', 'Environmental'),
        ('other', 'Other'),
    ], string='Category', default='medicine')
    notes = fields.Text(string='Notes')


class SanthigiriEMREvent(models.Model):
    """Unified read-only EMR timeline aggregating all patient interactions."""
    _name = 'santhigiri.emr.event'
    _description = 'Patient EMR Timeline'
    _order = 'event_date desc'
    _rec_name = 'summary'

    patient_id = fields.Many2one('res.partner', string='Patient', required=True, index=True)
    event_date = fields.Date(string='Date', required=True)
    event_type = fields.Selection([
        ('op_visit', 'OP Visit'),
        ('ip_admission', 'IP Admission'),
        ('casualty', 'Casualty Visit'),
        ('lab_test', 'Lab Test'),
        ('procedure', 'Procedure / Therapy'),
        ('prescription', 'Prescription'),
    ], string='Type', required=True)
    summary = fields.Char(string='Summary')
    ref_model = fields.Char(string='Reference Model')
    ref_id = fields.Integer(string='Reference ID')
    details = fields.Text(string='Details / Notes')
    doctor_id = fields.Many2one('hr.employee', string='Doctor / RMO')