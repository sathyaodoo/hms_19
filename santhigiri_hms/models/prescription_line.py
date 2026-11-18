# -*- coding: utf-8 -*-
"""
prescription.line extensions:
BASE MODULE provides: medicine_id, quantity, no_intakes, time, note,
                      inpatient_id, outpatient_id, res_partner_id.
THIS FILE ADDS: anupanam, route, duration_days, pathya_apathya, casualty_id,
medication_plan_id, reassessment_id, assessment_id, and automatic master synchronization.
"""
from odoo import api, fields, models


class PrescriptionLine(models.Model):
    _inherit = 'prescription.line'

    anupanam = fields.Char(
        string='Anupanam (Adjuvant)',
        help='Adjuvant substance — e.g. Honey, Warm Water, Milk, Ghee, Buttermilk',
    )
    route = fields.Selection([
        ('oral', 'Oral'),
        ('external', 'External Application'),
        ('nasal', 'Nasal (Nasya)'),
        ('rectal', 'Rectal (Vasthi)'),
        ('ophthalmic', 'Ophthalmic'),
        ('ear', 'Ear (Karnapurana)'),
    ], string='Route of Administration', default='oral')
    duration_days = fields.Integer(
        string='Duration (Days)',
        help='Number of days for which medicine is prescribed',
        default=7,
    )
    # Links to casualty
    casualty_id = fields.Many2one(
        'hospital.casualty',
        string='Casualty Reference',
        ondelete='cascade',
    )
    # Links to medication plan
    medication_plan_id = fields.Many2one(
        'hospital.medication.plan',
        string='Medication Plan',
        ondelete='cascade',
    )
    # Links to OP reassessment (Form SAMC/CS/14)
    reassessment_id = fields.Many2one(
        'hospital.op.reassessment',
        string='OP Reassessment',
        ondelete='cascade',
    )
    # Links to Initial Assessment (Form SAMC/CS/11)
    assessment_id = fields.Many2one(
        'hospital.op.assessment',
        string='Initial Assessment',
        ondelete='cascade',
        index=True,
    )
    quantity = fields.Integer(string='Quantity', default=1)
    no_intakes = fields.Float(string='Intakes / Dose', default=1.0)
    time = fields.Selection(
        [('once', 'Once in a day'), ('twice', 'Twice in a Day'),
         ('thrice', 'Thrice in a day'), ('morning', 'In Morning'),
         ('noon', 'In Noon'), ('evening', 'In Evening')], string='Time',
        default='twice',
    )
    note = fields.Selection(
        [('before', 'Before Food'), ('after', 'After Food')],
        string='Before/ After Food', default='after',
    )
    pathya_apathya = fields.Char(
        string='Pathya-Apathya',
        help='Dietary do\'s (Pathya) and don\'ts (Apathya) for this medicine/course',
    )

    timing = fields.Selection([
        ('1-0-0', '1-0-0 (Morning)'),
        ('0-1-0', '0-1-0 (Noon)'),
        ('0-0-1', '0-0-1 (Night)'),
        ('1-0-1', '1-0-1 (Morning & Night)'),
        ('1-1-1', '1-1-1 (Morning, Noon & Night)'),
        ('1-1-0', '1-1-0 (Morning & Noon)'),
        ('0-1-1', '0-1-1 (Noon & Night)'),
        ('sos', 'SOS (As needed)'),
    ], string='Timing', default='1-0-1')
    dosage = fields.Char(string='Dosage', default='1')
    unit = fields.Char(string='Unit', default='NOS')
    remarks = fields.Char(string='Notes / Instructions')

    @api.onchange('timing')
    def _onchange_timing(self):
        if self.timing:
            mapping = {
                '1-0-0': 'morning',
                '0-1-0': 'noon',
                '0-0-1': 'evening',
                '1-0-1': 'twice',
                '1-1-1': 'thrice',
                '1-1-0': 'twice',
                '0-1-1': 'twice',
                'sos': 'once',
            }
            if self.timing in mapping:
                self.time = mapping[self.timing]

    @api.onchange('medicine_id')
    def _onchange_medicine_id_defaults(self):
        if self.medicine_id:
            if hasattr(self.medicine_id, 'default_anupanam') and self.medicine_id.default_anupanam:
                self.anupanam = self.medicine_id.default_anupanam
            if hasattr(self.medicine_id, 'default_route') and self.medicine_id.default_route:
                self.route = self.medicine_id.default_route

    # ── Auto-sync with Master Tables ──────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('assessment_id'):
                ass = self.env['hospital.op.assessment'].browse(vals['assessment_id'])
                if not vals.get('outpatient_id') and ass.outpatient_id:
                    vals['outpatient_id'] = ass.outpatient_id.id
                if not vals.get('inpatient_id') and ass.inpatient_id:
                    vals['inpatient_id'] = ass.inpatient_id.id
                if not vals.get('res_partner_id') and ass.patient_id:
                    vals['res_partner_id'] = ass.patient_id.id
            elif vals.get('outpatient_id') and not vals.get('assessment_id'):
                ass = self.env['hospital.op.assessment'].search([
                    ('outpatient_id', '=', vals['outpatient_id']),
                ], limit=1)
                if ass:
                    vals['assessment_id'] = ass.id
            elif vals.get('inpatient_id') and not vals.get('assessment_id'):
                ass = self.env['hospital.op.assessment'].search([
                    ('inpatient_id', '=', vals['inpatient_id']),
                ], limit=1)
                if ass:
                    vals['assessment_id'] = ass.id
            if not vals.get('quantity'):
                vals['quantity'] = 1
            if not vals.get('no_intakes'):
                vals['no_intakes'] = 1.0
            if not vals.get('time'):
                vals['time'] = 'twice'
            if not vals.get('note'):
                vals['note'] = 'after'
            med_id = vals.get('medicine_id')
            if med_id:
                med = self.env['product.template'].sudo().browse(med_id)
                if not med.medicine_ok:
                    med.write({'medicine_ok': True})
                try:
                    PharmacyMed = self.env['pharmacy.medicine'].sudo()
                    if not PharmacyMed.search([('product_id', '=', med.id)], limit=1):
                        PharmacyMed.create({'product_id': med.id})
                except Exception:
                    pass

        lines = super().create(vals_list)
        for line in lines:
            line._ensure_prescription_master()
        return lines

    def write(self, vals):
        if 'medicine_id' in vals and vals['medicine_id']:
            med = self.env['product.template'].sudo().browse(vals['medicine_id'])
            if not med.medicine_ok:
                med.write({'medicine_ok': True})
            try:
                PharmacyMed = self.env['pharmacy.medicine'].sudo()
                if not PharmacyMed.search([('product_id', '=', med.id)], limit=1):
                    PharmacyMed.create({'product_id': med.id})
            except Exception:
                pass
        res = super().write(vals)
        for line in self:
            if not line.prescription_id:
                line._ensure_prescription_master()
        return res

    def _ensure_prescription_master(self):
        """Auto-create or link to a hospital.prescription master record for grouping."""
        for line in self:
            if line.prescription_id:
                continue
            patient = False
            doctor = False
            dept = False
            op = line.outpatient_id
            ip = line.inpatient_id
            cas = line.casualty_id
            ass = line.assessment_id

            if op:
                patient = op.patient_id
                if op.doctor_id and hasattr(op.doctor_id, 'doctor_id') and op.doctor_id.doctor_id:
                    doctor = op.doctor_id.doctor_id
                elif op.doctor_id and getattr(op.doctor_id, '_name', '') == 'hr.employee':
                    doctor = op.doctor_id
                dept = op.department_id
            elif ip:
                patient = ip.patient_id
                doctor = ip.attending_doctor_id
                dept = getattr(ip, 'department_id', False) or (ip.attending_doctor_id.department_id if ip.attending_doctor_id else False)
            elif cas:
                patient = cas.patient_id
                if cas.doctor_id and hasattr(cas.doctor_id, 'doctor_id') and cas.doctor_id.doctor_id:
                    doctor = cas.doctor_id.doctor_id
                elif cas.doctor_id and getattr(cas.doctor_id, '_name', '') == 'hr.employee':
                    doctor = cas.doctor_id
            elif ass:
                patient = ass.patient_id
                doctor = ass.doctor_id
                dept = ass.department_id
                op = ass.outpatient_id
                ip = ass.inpatient_id
            elif line.res_partner_id:
                patient = line.res_partner_id

            if not doctor and ass and ass.doctor_id:
                doctor = ass.doctor_id

            if patient:
                domain = [('patient_id', '=', patient.id)]
                if op:
                    domain.append(('outpatient_id', '=', op.id))
                elif ip:
                    domain.append(('inpatient_id', '=', ip.id))
                else:
                    domain.append(('prescription_date', '=', fields.Date.today()))

                presc = self.env['hospital.prescription'].sudo().search(domain, limit=1)
                if not presc:
                    p_name = patient.name[:12] if patient.name else 'Patient'
                    presc_name = f"RX/{p_name}/{fields.Date.today().strftime('%d%m%y')}"
                    presc = self.env['hospital.prescription'].sudo().create({
                        'name': presc_name,
                        'patient_id': patient.id,
                        'doctor_id': doctor.id if doctor else False,
                        'department_id': dept.id if dept else False,
                        'outpatient_id': op.id if op else False,
                        'inpatient_id': ip.id if ip else False,
                        'prescription_date': fields.Date.today(),
                    })
                line.sudo().write({'prescription_id': presc.id})
