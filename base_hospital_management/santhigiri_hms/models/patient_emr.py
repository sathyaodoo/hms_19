# -*- coding: utf-8 -*-
"""
§9.8 Patient EMR Timeline
Aggregates all patient interactions into a unified chronological view.
"""
from odoo import api, fields, models


class PatientEMRTimeline(models.Model):
    _name = 'patient.emr.timeline'
    _description = 'Patient EMR / Medical Timeline'
    _order = 'date desc'
    _rec_name = 'summary'

    partner_id = fields.Many2one('res.partner', string='Patient',
                                  required=True, ondelete='cascade', index=True)
    date = fields.Date(string='Date', required=True)
    event_type = fields.Selection([
        ('op', 'OP Consultation'),
        ('ip', 'IP Admission'),
        ('casualty', 'Casualty'),
        ('lab', 'Lab Test'),
        ('procedure', 'Procedure / Therapy'),
        ('discharge', 'Discharge'),
        ('allergy', 'Allergy / History Update'),
        ('vitals', 'Vitals'),
    ], string='Type', required=True)
    summary = fields.Char(string='Summary')
    doctor_id = fields.Many2one('hr.employee', string='Doctor / RMO')
    notes = fields.Text(string='Details / Notes')
    is_abnormal = fields.Boolean(string='Abnormal', default=False)

    # Source record links
    op_id = fields.Many2one('hospital.outpatient', string='OP Reference')
    ip_id = fields.Many2one('hospital.inpatient', string='IP Reference')
    casualty_id = fields.Many2one('hospital.casualty', string='Casualty Reference')
    lab_id = fields.Many2one('patient.lab.test', string='Lab Reference')
    procedure_id = fields.Many2one('hospital.procedure.prescription',
                                    string='Procedure Reference')


class ResPartnerEMR(models.Model):
    """Add EMR button and rebuild method to patient (res.partner)."""
    _inherit = 'res.partner'

    emr_ids = fields.One2many('patient.emr.timeline', 'partner_id',
                               string='EMR Timeline')
    emr_count = fields.Integer(string='EMR Events',
                                compute='_compute_emr_count')

    def _compute_emr_count(self):
        for rec in self:
            rec.emr_count = len(rec.emr_ids)

    def action_open_emr_timeline(self):
        """Alias — base module button calls this name."""
        return self.action_view_emr()

    def action_view_emr(self):
        self.ensure_one()
        # Build EMR lines fresh without deleting existing
        self._build_emr_lines()
        return {
            'type': 'ir.actions.act_window',
            'name': f'EMR Timeline — {self.name}',
            'res_model': 'patient.emr.timeline',
            'view_mode': 'list',
            'domain': [('partner_id', '=', self.id)],
            'context': {'create': False, 'edit': False},
        }

    def _build_emr_lines(self):
        """Build EMR lines — delete and rebuild for this patient."""
        self.ensure_one()
        EMR = self.env['patient.emr.timeline'].sudo()
        # Delete existing for this patient
        EMR.search([('partner_id', '=', self.id)]).unlink()
        lines = []

        # OP Visits
        for op in self.env['hospital.outpatient'].sudo().search(
                [('patient_id', '=', self.id)]):
            lines.append({
                'partner_id': self.id,
                'date': op.op_date or fields.Date.today(),
                'event_type': 'op',
                'summary': f'OP: {op.op_reference} — {op.reason or "Consultation"}',
                'doctor_id': op.doctor_id.id if op.doctor_id else False,
                'notes': f'Outcome: {op.outcome or "-"}',
                'op_id': op.id,
            })

        # IP Admissions
        for ip in self.env['hospital.inpatient'].sudo().search(
                [('patient_id', '=', self.id)]):
            lines.append({
                'partner_id': self.id,
                'date': ip.hosp_date or fields.Date.today(),
                'event_type': 'ip',
                'summary': f'IP: {ip.name} — {ip.reason or "Admission"}',
                'doctor_id': ip.attending_doctor_id.id
                             if ip.attending_doctor_id else False,
                'notes': f'Room: {ip.room_id.name if ip.room_id else "-"} | '
                         f'Discharge: {ip.discharge_date or "Active"}',
                'ip_id': ip.id,
            })

        # Casualty
        for cas in self.env['hospital.casualty'].sudo().search(
                [('patient_id', '=', self.id)]):
            lines.append({
                'partner_id': self.id,
                'date': cas.date or fields.Date.today(),
                'event_type': 'casualty',
                'summary': f'Casualty: {cas.name} — {cas.chief_complaint or ""}',
                'notes': f'Outcome: {cas.state or "-"}',
                'casualty_id': cas.id,
            })

        # Lab Tests
        for lab in self.env['patient.lab.test'].sudo().search(
                [('patient_id', '=', self.id)]):
            abnormal = len(lab.result_ids.filtered(lambda r: r.is_abnormal))
            lines.append({
                'partner_id': self.id,
                'date': lab.date or fields.Date.today(),
                'event_type': 'lab',
                'summary': f'Lab: {lab.test_id.name if lab.test_id else "Test"}'
                           f'{" ⚠ ABNORMAL" if abnormal else ""}',
                'is_abnormal': bool(abnormal),
                'notes': f'Status: {lab.state or "-"}',
                'lab_id': lab.id,
            })

        # Procedures
        for proc in self.env['hospital.procedure.prescription'].sudo().search(
                [('patient_id', '=', self.id)]):
            lines.append({
                'partner_id': self.id,
                'date': proc.start_date or fields.Date.today(),
                'event_type': 'procedure',
                'summary': f'Procedure: {proc.procedure_id.name if proc.procedure_id else "-"}'
                           f' ({proc.completed_sessions}/{proc.no_of_sessions})',
                'notes': f'State: {proc.state or "-"}',
                'procedure_id': proc.id,
            })

        if lines:
            EMR.create(lines)