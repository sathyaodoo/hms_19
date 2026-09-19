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
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta

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
                
    current_registration_fee = fields.Monetary(
        string='Registration Fee', currency_field='currency_id',
        compute='_compute_current_registration_fee',
        help='The one-time registration fee currently configured under '
             'Configuration > Registration Fee. Shown here for '
             'reference; it is charged automatically when this patient '
             'is first registered.')

    def _compute_current_registration_fee(self):
        fee = self.env['hospital.registration.fee'].sudo().get_current_fee()
        for rec in self:
            rec.current_registration_fee = fee

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

    # ── Previous Medical History / Prescription Onboarding ───────────────────
    # For a NEW patient who already has medical history/medication from
    # before joining this hospital. Separate from prescription_ids /
    # lab_test_ids (base module) because those are system-generated
    # (create="0") from actual OP/IP visits here and cannot be used to
    # log external, pre-existing history.
    medical_history_ids = fields.One2many(
        'patient.medical.history', 'patient_id',
        string='Previous Medical History',
        help="Patient's medical history from before joining this "
             "hospital, captured during onboarding")
    previous_prescription_ids = fields.One2many(
        'patient.previous.prescription', 'patient_id',
        string='Previous Prescriptions',
        help='Medicines the patient was already taking before joining '
             'this hospital, captured during onboarding')

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

    # ── Registration Fee — recurring on a configurable renewal cycle ───────────
    # Same idea as HospitalOutpatient.create_invoice() (category-based
    # Consultation Fee): fetch the configured amount and raise an
    # invoice for it. Registration Fee RENEWS on a rolling basis, for
    # every patient:
    #   - First charge: automatic, the moment a genuinely new patient
    #     is created (create() below) — no click needed.
    #   - Renewal: once the configured renewal period
    #     (hospital.registration.fee.renewal_months — set under
    #     Configuration > Registration Fee, NOT hardcoded anywhere in
    #     this file) has passed since registration_date, "due"
    #     becomes true again, and the "Generate Registration Invoice"
    #     button appears on the patient form. Clicking it
    #     (action_generate_registration_invoice) is the ONLY thing
    #     that ever creates a renewal invoice.
    #   - The scheduled action (ir.cron — see data/ir_cron_data.xml,
    #     _cron_check_due_registration_fees below) runs periodically
    #     too, but it does NOT create any invoice. Its only job is to
    #     check which patients have newly become due and post a
    #     reminder to their chatter, so staff notice and click the
    #     button — it exists purely to support the 3-month renewal
    #     check running on a schedule, never to charge anyone
    #     automatically.
    #
    # registration_date is a real, EDITABLE stored field — this is
    # "the date of registration" the renewal period counts from. Open
    # any patient, change Registration Date to a date more than one
    # renewal period in the past, save — "Registration Fee Due" flips
    # to True and the button appears immediately, with no invoice
    # touching needed to test it. In normal, non-testing use, this
    # field is set automatically to fields.Date.today() on patient
    # creation, and reset to fields.Date.today() again every time a
    # renewal invoice is actually raised via the button (see
    # _charge_registration_fee_if_due below) — so it always reflects
    # "the date this patient's current cycle started."
    registration_date = fields.Date(
        string='Registration Date',
        default=fields.Date.today,
        tracking=True,
        help='Date this patient\'s current registration fee cycle '
             'started. Set automatically on patient creation, and '
             'reset automatically every time a renewal fee is charged '
             '(via the Generate Registration Invoice button) — but '
             'you can also edit it directly, e.g. for TESTING: set it '
             'to a date more than one renewal period in the past, '
             'save, and "Registration Fee Due" / the button will '
             'appear immediately.')
    last_registration_invoice_date = fields.Date(
        string='Last Registration Fee Date',
        compute='_compute_registration_fee_status',
        help='Date the most recent registration fee invoice was raised '
             'for this patient')
    next_registration_due_date = fields.Date(
        string='Next Registration Fee Due',
        compute='_compute_registration_fee_status',
        help='Registration fee renews after the interval configured '
             'under Configuration > Registration Fee, counted from '
             'Registration Date')
    registration_fee_due = fields.Boolean(
        string='Registration Fee Due',
        compute='_compute_registration_fee_status',
        help='True if this patient has no Registration Date set yet, '
             'or if the configured renewal period has passed since '
             'it — controls when the "Generate Registration Invoice" '
             'button appears')

    @api.depends('registration_date')
    def _compute_registration_fee_status(self):
        for rec in self:
            if rec.registration_date:
                rec.last_registration_invoice_date = rec.registration_date
                months = self.env['hospital.registration.fee'].sudo().get_renewal_months()
                rec.next_registration_due_date = (
                    rec.registration_date + relativedelta(months=months))
            else:
                rec.last_registration_invoice_date = False
                rec.next_registration_due_date = False
            rec.registration_fee_due = rec._is_registration_fee_due()

    def _get_last_registration_invoice(self):
        """Most recent registration-fee invoice for this patient, if
        any — kept for anyone wanting to review actual billing history
        (e.g. the invoice smart button). No longer used to determine
        due-ness — that reads registration_date directly (see
        _is_registration_fee_due below), so it can be edited straight
        through the UI for testing without touching any invoice."""
        self.ensure_one()
        return self.env['account.move'].sudo().search([
            ('partner_id', '=', self.id),
            ('move_type', '=', 'out_invoice'),
            ('ref', 'like', 'Registration Fee%'),
        ], order='invoice_date desc, id desc', limit=1)

    def _is_registration_fee_due(self):
        """True if this patient has no Registration Date set yet, or
        the configured renewal period (hospital.registration.fee.
        renewal_months — NOT a hardcoded number, read fresh every
        call) has passed since registration_date."""
        self.ensure_one()
        if not self.registration_date:
            return True
        months = self.env['hospital.registration.fee'].sudo().get_renewal_months()
        return fields.Date.today() >= self.registration_date + relativedelta(months=months)

    def _build_registration_fee_ref(self, on_date=None):
        """One place that builds the invoice ref, so every invoice
        this module raises uses the same format:
        'Registration Fee - <patient code> - <date>'. The date suffix
        is what lets MULTIPLE registration invoices coexist per
        patient over time, one per renewal period."""
        self.ensure_one()
        on_date = on_date or fields.Date.today()
        return 'Registration Fee - %s - %s' % (
            self.patient_seq or self.name, on_date)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            # Same signal the base module's own Patient menu action
            # already relies on (see res_partner_action's domain:
            # patient_seq not in ['New', 'Employee', 'User']) to tell
            # a genuine patient apart from every other kind of
            # res.partner record (companies, vendors, doctors' linked
            # partner, etc.) that also flows through this create().
            if rec.is_company or rec.patient_seq in (False, 'New', 'Employee', 'User'):
                continue
            # force=True: a brand-new patient must always get their
            # first registration invoice, unconditionally. We can't
            # rely on the normal due-check here — registration_date
            # defaults to fields.Date.today() at the FIELD level, so
            # by this point it is already set to today, never empty,
            # so _is_registration_fee_due() would (wrongly) say "not
            # due yet" and silently skip the very first charge. The
            # due-check is only meaningful for RENEWALS (button/cron),
            # where registration_date reflects a real past cycle
            # start, not "the moment this record was created".
            rec._charge_registration_fee_if_due(force=True)
        return records

    def _charge_registration_fee_if_due(self, force=False):
        """The ONLY place that ever actually creates a Registration
        Fee invoice. Called from exactly two places:
          - create() above, with force=True (unconditional first
            charge for a brand-new patient — see the comment there
            for why the normal due-check can't be used here)
          - action_generate_registration_invoice() below, with
            force=False (the manual "Generate Registration Invoice"
            button — must respect the actual due-check, since this is
            a RENEWAL, not the first charge)
        Never called by the cron — see _cron_check_due_registration_fees,
        which only checks and reminds, never charges. Wrapped so a
        billing hiccup can never block patient registration/save.
        Returns the created account.move record, or False if nothing
        was due/configured/charged (including on any billing error)."""
        self.ensure_one()
        try:
            if not force and not self._is_registration_fee_due():
                return False
            fee = self.env['hospital.registration.fee'].sudo().get_current_fee()
            if not fee:
                return False  # no fee configured yet — nothing to charge
            move = self.env['account.move'].sudo().create({
                'move_type': 'out_invoice',
                'partner_id': self.id,
                'invoice_date': fields.Date.today(),
                'ref': self._build_registration_fee_ref(),
                'invoice_line_ids': [(0, 0, {
                    'name': 'Patient Registration Fee',
                    'quantity': 1,
                    'price_unit': fee,
                })],
            })
            # Reset the cycle: registration_date now becomes "today",
            # so the next due-check correctly counts forward from this
            # charge, not from whatever date (possibly a backdated
            # test date) triggered it.
            self.registration_date = fields.Date.today()
            # last_registration_invoice_date/next_registration_due_date/
            # registration_fee_due now correctly recompute on their own
            # — they have a real @api.depends('registration_date'), so
            # writing registration_date above already triggers Odoo's
            # normal cache invalidation.
            return move
        except Exception:
            # Registration must never fail because billing had a
            # problem (e.g. accounting not fully configured yet). The
            # "Generate Registration Invoice" button, or the next
            # create() for a future patient, is unaffected either way.
            return False

    def action_generate_registration_invoice(self):
        """Manually triggered from the "Generate Registration
        Invoice" button on the patient form — visible only once
        registration_fee_due is True. This button is the ONLY way a
        renewal fee is ever charged; the cron below deliberately never
        calls this method or anything that creates an invoice. Reuses
        _charge_registration_fee_if_due() (also used for the
        automatic first charge on create()) so both paths share
        identical due-checking and invoice-building logic. Opens the
        newly created invoice directly afterward."""
        self.ensure_one()
        move = self._charge_registration_fee_if_due()
        if not move:
            raise UserError(
                'Could not generate the Registration Fee invoice. '
                'Either it is not due yet for this patient, or no fee '
                'amount is configured yet under Configuration > '
                'Registration Fee.'
            )
        return {
            'type': 'ir.actions.act_window',
            'name': 'Registration Fee Invoice',
            'res_model': 'account.move',
            'res_id': move.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.model
    def _cron_check_due_registration_fees(self):
        """Scheduled action (see data/ir_cron_data.xml) — runs
        periodically to CHECK which patients have newly become due
        for their registration fee renewal, and posts a short
        reminder to each one's chatter so staff notice and use the
        "Generate Registration Invoice" button. THIS METHOD NEVER
        CREATES AN INVOICE — that only ever happens via
        action_generate_registration_invoice (the button) or create()
        (the first charge for a new patient). The renewal interval
        itself is never hardcoded here — it's read fresh from
        hospital.registration.fee.renewal_months each time via
        registration_fee_due, so changing the configured period in
        Configuration takes effect on the very next cron run, with no
        code change and no redeployment."""
        candidate_patients = self.search([
            ('is_company', '=', False),
            ('patient_seq', 'not in', (False, 'New', 'Employee', 'User')),
        ])
        patients = candidate_patients.filtered(lambda p: p.registration_fee_due)
        
        for patient in patients:
            already_reminded_today = patient.message_ids.filtered(
                lambda m: m.subtype_id.id == self.env.ref('mail.mt_note').id
                and m.date and m.date.date() == fields.Date.today()
                and m.body and 'Registration Fee renewal is due' in (m.body or '')
            )
            if already_reminded_today:
                continue
            patient.message_post(
                body='Registration Fee renewal is due for this patient. '
                     'Use the "Generate Registration Invoice" button to '
                     'raise the invoice.',
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )


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