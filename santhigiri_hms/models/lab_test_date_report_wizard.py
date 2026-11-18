# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class LabTestDateReportWizard(models.TransientModel):
    _name = 'lab.test.date.report.wizard'
    _description = 'Lab Test Datewise Report Wizard'

    start_date = fields.Date(string='Start Date', required=True)
    end_date = fields.Date(string='End Date', required=True)

    def action_print_pdf(self):
        self.ensure_one()
        if self.start_date > self.end_date:
            raise ValidationError(_('Start Date cannot be later than End Date.'))
        return self.env.ref(
            'santhigiri_hms.action_report_lab_test_datewise'
        ).report_action(self)


class ReportLabTestDatewise(models.AbstractModel):
    _name = 'report.santhigiri_hms.report_lab_test_datewise'
    _description = 'Lab Test Datewise PDF Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['lab.test.date.report.wizard'].browse(docids)
        wizard = docs[:1]
        lines = []

        if wizard:
            results = self.env['lab.test.result'].search([
                ('parent_id.state', '=', 'completed'),
                ('parent_id.date', '>=', wizard.start_date),
                ('parent_id.date', '<=', wizard.end_date),
            ], order='parent_id asc, id asc')

            for res in results:
                pt = res.parent_id
                lines.append({
                    'date': pt.date,
                    'patient': pt.patient_id.name or '',
                    'test': res.test_id.name or '',
                    'result': res.result or '',
                    'normal': res.normal or res.test_id.default_normal_range_male or '',
                    'unit': res.uom_id.name or res.test_id.default_uom_id.name or '',
                })

        return {
            'doc_ids': docids,
            'doc_model': 'lab.test.date.report.wizard',
            'docs': docs,
            'lines': lines,
        }