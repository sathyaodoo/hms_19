# -*- coding: utf-8 -*-
"""
product.template extension:
- Adds procedure & therapy attributes (is_procedure, procedure_category, standard sessions, duration).
- Adds Ayurvedic medicine attributes (ayurvedic_category, default anupanam, default route).
- Auto-creates master records in pharmacy.medicine when medicines are created.
- Auto-handles quick creation of medicines & procedures from prescription and treatment lines.
"""
from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # ── Procedure / Therapy Master Fields ──────────────────────────────────────
    is_procedure = fields.Boolean(
        string='Is Procedure / Therapy',
        help='Mark this product as a Panchakarma or therapy procedure. '
             'Used in Procedure Prescriptions and IP Treatment Plans.',
        default=False,
    )
    procedure_category = fields.Selection([
        ('panchakarma', 'Panchakarma (Main Cleansing Therapies)'),
        ('upakarma', 'Upakarma / Bahir-parimarjana (Ancillary Therapies)'),
        ('snehana', 'Snehana (Oleation - Abhyanga, Snehapana)'),
        ('swedana', 'Swedana (Sudation - Kizhi, Bashpa, Nadi Sweda)'),
        ('kriya_kalpa', 'Netra Kriya Kalpa (Eye Therapies - Tarpana, Seka)'),
        ('shiro_chikitsa', 'Shiro Chikitsa (Shirodhara, Shirovasthi, Shirolepa)'),
        ('vasthi', 'Vasthi (Kashaya Vasthi, Sneha Vasthi, Matra Vasthi)'),
        ('physiotherapy', 'Physiotherapy & Rehabilitation'),
        ('yoga', 'Yoga & Naturopathy Procedure'),
        ('general', 'General Clinical Procedure'),
    ], string='Procedure Category', default='panchakarma')

    standard_sessions = fields.Integer(string='Standard Sessions', default=7)
    duration_minutes = fields.Integer(string='Duration (Minutes)', default=45)
    procedure_instructions = fields.Text(string='Standard Procedure Instructions')
    procedure_precautions = fields.Text(string='Precautions & Contraindications')

    # ── Ayurvedic Medicine Master Fields ───────────────────────────────────────
    ayurvedic_category = fields.Selection([
        ('kashayam', 'Kashayam (Decoction)'),
        ('arishtam', 'Arishtam / Asavam (Fermented Liquid)'),
        ('churnam', 'Churnam (Herbal Powder)'),
        ('vati', 'Vati / Gulika (Pills / Tablets)'),
        ('tailam', 'Thailam / Taila (Medicated Oil)'),
        ('ghritam', 'Ghritam (Medicated Ghee)'),
        ('lehyam', 'Lehyam / Rasayanam (Medicated Jam)'),
        ('bhasma', 'Bhasma / Sindhoora (Mineral / Herbo-Mineral Calx)'),
        ('kwatham', 'Kwatham Tablets'),
        ('syrup', 'Syrup'),
        ('ointment', 'Ointment / Lepam'),
        ('drops', 'Drops (Netra / Karna / Nasya)'),
        ('capsule', 'Capsules'),
        ('other', 'Other Ayurvedic Medicine'),
    ], string='Ayurvedic Dosage Form')

    default_anupanam = fields.Char(
        string='Standard Anupanam (Adjuvant)',
        help='Recommended adjuvant substance: e.g. Warm water, Honey, Milk, Jeera water',
    )
    default_route = fields.Selection([
        ('oral', 'Oral'),
        ('external', 'External Application'),
        ('nasal', 'Nasal (Nasya)'),
        ('rectal', 'Rectal (Vasthi)'),
        ('ophthalmic', 'Ophthalmic (Netra)'),
        ('ear', 'Ear (Karnapurana)'),
    ], string='Standard Route', default='oral')

    # ── Master Auto-Creation & Quick-Create Hooks ──────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Check medicine context or flag
            if vals.get('medicine_ok') or self.env.context.get('default_medicine_ok'):
                vals['medicine_ok'] = True
                vals.setdefault('type', 'consu')
            # Check procedure context or flag
            if vals.get('is_procedure') or self.env.context.get('default_is_procedure'):
                vals['is_procedure'] = True
                vals.setdefault('type', 'service')

        records = super().create(vals_list)

        # Auto-create entry in pharmacy.medicine so it appears in Pharmacy Medicines master too
        for rec in records:
            if rec.medicine_ok:
                try:
                    PharmacyMed = self.env['pharmacy.medicine'].sudo()
                    existing = PharmacyMed.search([('product_id', '=', rec.id)], limit=1)
                    if not existing:
                        PharmacyMed.create({
                            'product_id': rec.id,
                            'pharmacy_id': rec.pharmacy_id.id if rec.pharmacy_id else False,
                        })
                except Exception:
                    pass

        return records

    @api.model
    def name_create(self, name):
        """Allows quick creation from Many2one with appropriate flags."""
        vals = {'name': name}
        if self.env.context.get('default_medicine_ok'):
            vals['medicine_ok'] = True
            vals['type'] = 'consu'
        if self.env.context.get('default_is_procedure'):
            vals['is_procedure'] = True
            vals['type'] = 'service'
        record = self.create([vals])[0]
        return record.id, record.display_name
