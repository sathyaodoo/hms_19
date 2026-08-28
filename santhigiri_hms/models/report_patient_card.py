# -*- coding: utf-8 -*-
"""
Fix for base_hospital_management patient card report in Odoo 19.

Odoo 19 traceback shows ir_actions_report.py line 1116:
    return self._render_template(report.report_name, data), 'html'

The 'data' passed here does NOT contain our custom keys (image, name etc.)
in Odoo 19. The fix: override _render_qweb_html on ir.actions.report
to inject the missing keys when rendering the patient card report.
"""
from datetime import date

from dateutil.relativedelta import relativedelta
from odoo import models


class IrActionsReportPatientCardFix(models.Model):
    _inherit = 'ir.actions.report'

    def _render_qweb_html(self, report_ref, res_ids, data=None):
        """
        Override to inject patient card data into QWeb values
        when the patient card report is being rendered.
        """
        report = self._get_report(report_ref)
        if (report and
                report.report_name ==
                'base_hospital_management.patient_card_report' and
                res_ids):
            # Build the required data from the actual patient record
            patient = self.env['res.partner'].sudo().browse(res_ids[0])
            if patient.exists():
                current_age = 0
                gender_caps = ''
                blood_caps = ''
                if patient.gender:
                    gender_caps = patient.gender.capitalize()
                if patient.blood_group:
                    blood_caps = patient.blood_group.capitalize()
                if patient.date_of_birth:
                    today = date.today()
                    current_age = relativedelta(today, patient.date_of_birth).years
                company = self.env.company
                image_data = patient.sudo().read(['image_1920'])[0]
                barcode_data = patient.sudo().read(['barcode_png'])[0]
                if data is None:
                    data = {}
                data.update({
                    'name': patient.name,
                    'code': patient.patient_seq or '',
                    'age': current_age,
                    'gender': gender_caps,
                    'dob': patient.date_of_birth,
                    'blood': blood_caps + str(patient.rh_type or ''),
                    'street': patient.street or '',
                    'street2': patient.street2 or '',
                    'state': patient.state_id.name if patient.state_id else '',
                    'country': (patient.country_id.name
                                if patient.country_id else ''),
                    'city': patient.city or '',
                    'phone': patient.phone or '',
                    'image': image_data,
                    'barcode': barcode_data,
                    'company_name': company.name or '',
                    'company_street': company.street or '',
                    'company_street2': company.street2 or '',
                    'company_city': company.city or '',
                    'company_state': (company.state_id.name
                                      if company.state_id else ''),
                    'company_zip': company.zip or '',
                    # FRD §9.2 — Known Allergies (brief)
                    'allergies': patient.allergy_summary or '',
                    'has_allergy': patient.has_allergy if hasattr(patient, 'has_allergy') else False,
                })
        return super()._render_qweb_html(report_ref, res_ids, data=data)