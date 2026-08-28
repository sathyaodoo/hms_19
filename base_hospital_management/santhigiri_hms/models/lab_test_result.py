# -*- coding: utf-8 -*-
"""
lab.test.result + patient.lab.test extensions.
"""
import requests
from odoo import api, fields, models


class LabTestResult(models.Model):
    _inherit = 'lab.test.result'

    is_abnormal = fields.Boolean(
        string='Abnormal',
        compute='_compute_is_abnormal',
        store=True,
    )

    @api.depends('result', 'normal')
    def _compute_is_abnormal(self):
        for rec in self:
            rec.is_abnormal = False
            if not rec.result or not rec.normal:
                continue
            result_val = rec.result.strip().lower()
            normal_val = rec.normal.strip().lower()
            if 'negative' in normal_val and 'positive' in result_val:
                rec.is_abnormal = True
                continue
            if 'positive' in normal_val and 'negative' in result_val:
                rec.is_abnormal = True
                continue
            try:
                r = float(rec.result.replace(',', '.'))
                for sep in ['–', '-', ' to ', ' - ']:
                    if sep in rec.normal:
                        parts = rec.normal.split(sep)
                        lo = float(parts[0].strip())
                        hi = float(parts[1].strip())
                        if not (lo <= r <= hi):
                            rec.is_abnormal = True
                        break
                if rec.normal.strip().startswith('<'):
                    threshold = float(rec.normal.replace('<', '').strip())
                    if r >= threshold:
                        rec.is_abnormal = True
                elif rec.normal.strip().startswith('>'):
                    threshold = float(rec.normal.replace('>', '').strip())
                    if r <= threshold:
                        rec.is_abnormal = True
            except (ValueError, AttributeError):
                pass

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.is_abnormal:
                rec._notify_doctor_abnormal()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'result' in vals or 'normal' in vals:
            for rec in self:
                if rec.is_abnormal:
                    rec._notify_doctor_abnormal()
        return res

    def _notify_doctor_abnormal(self):
        """Alert doctor via patient record chatter (res.partner has mail.thread)."""
        # lab.test.result links to patient.lab.test via parent_id field
        lab_test = self.parent_id
        if not lab_test:
            return

        # Find doctor — patient.lab.test.test_id → lab.test.LINE → doctor_id
        doctor = None
        if lab_test.test_id and lab_test.test_id.doctor_id:
            doctor = lab_test.test_id.doctor_id
        elif (lab_test.inpatient_id
              and lab_test.inpatient_id.attending_doctor_id):
            doctor = lab_test.inpatient_id.attending_doctor_id

        from markupsafe import Markup
        test_name = self.test_id.name if self.test_id else 'Unknown'
        patient_name = lab_test.patient_id.name if lab_test.patient_id else ''

        body = Markup(
            '<p><b>⚠ ABNORMAL RESULT ALERT</b></p>'
            '<p>Test: <b>{test}</b><br/>'
            'Patient: <b>{patient}</b><br/>'
            'Result: <b>{result}</b> — Normal Range: {normal}</p>'
        ).format(
            test=test_name,
            patient=patient_name,
            result=self.result or '',
            normal=self.normal or '',
        )

        partner_ids = []
        if doctor and doctor.user_id and doctor.user_id.partner_id:
            partner_ids.append(doctor.user_id.partner_id.id)

        # Post on patient record with Markup body (renders HTML properly)
        if lab_test.patient_id:
            lab_test.patient_id.sudo().message_post(
                body=body,
                partner_ids=partner_ids,
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
                subject=f'⚠ Abnormal Lab Result — {patient_name}',
                author_id=self.env.user.partner_id.id,
            )


class PatientLabTest(models.Model):
    _inherit = 'patient.lab.test'

    priority = fields.Selection([
        ('routine', 'Routine'),
        ('urgent', 'Urgent'),
        ('stat', 'STAT (Immediate)'),
    ], string='Priority', default='routine')

    clinical_notes = fields.Text(string='Clinical Notes')

    is_external = fields.Boolean(string='External Lab', default=False)
    external_lab_name = fields.Char(string='External Lab Name')
    external_ref_no = fields.Char(string='External Reference No.')
    external_charge = fields.Monetary(
        string='External Lab Charge',
        currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda s: s.env.company.currency_id)

    abnormal_count = fields.Integer(
        string='Abnormal Results',
        compute='_compute_abnormal_count',
        store=True)

    @api.depends('result_ids', 'result_ids.is_abnormal')
    def _compute_abnormal_count(self):
        for rec in self:
            rec.abnormal_count = len(rec.result_ids.filtered('is_abnormal'))

    def action_import_from_equipment(self):
        """Import results from lab equipment via HTTP API."""
        self.ensure_one()
        params = self.env['ir.config_parameter'].sudo()
        equipment_url = params.get_param(
            'santhigiri_hms.lab_equipment_url', '')
        api_key = params.get_param(
            'santhigiri_hms.lab_equipment_api_key', '')
        if not equipment_url:
            from odoo.exceptions import UserError
            raise UserError(
                'Lab equipment URL not configured. '
                'Go to Settings → Technical → System Parameters.')
        try:
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            }
            response = requests.get(
                f'{equipment_url}/results/{self.id}',
                headers=headers,
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
            for item in data.get('results', []):
                result_line = self.result_ids.filtered(
                    lambda r: r.test_id.name == item.get('test_name'))
                if result_line:
                    result_line.write({
                        'result': str(item.get('value', '')),
                        'state': 'completed',
                    })
        except Exception as e:
            from odoo.exceptions import UserError
            raise UserError(
                f'Equipment import failed: {e}. Use manual entry as fallback.')

class LabTestLine(models.Model):
    """Extend lab.test.line to add priority and clinical notes (FRD §17.1)."""
    _inherit = 'lab.test.line'

    priority = fields.Selection([
        ('routine', 'Routine'),
        ('urgent', 'Urgent'),
        ('stat', 'STAT (Immediate)'),
    ], string='Priority', default='routine',
       help='Routine: normal queue | Urgent: fast-track | STAT: immediate')

    clinical_notes = fields.Text(
        string='Clinical Notes',
        help="Doctor's notes for the lab technician",
    )

class PatientLabTestInvoiceOverride(models.Model):
    """Override create_invoice to include external lab charges."""
    _inherit = 'patient.lab.test'

    def action_create_invoice(self):
        """Override to add external lab charge to invoice."""
        # Call base invoice creation
        super().action_create_invoice()
        # Add external charge if present
        if self.external_charge and self.invoice_id:
            self.invoice_id.sudo().write({
                'invoice_line_ids': [(0, 0, {
                    'name': f'External Lab: {self.external_lab_name or "External"}'
                            f' (Ref: {self.external_ref_no or "-"})',
                    'quantity': 1,
                    'price_unit': self.external_charge,
                })]
            })