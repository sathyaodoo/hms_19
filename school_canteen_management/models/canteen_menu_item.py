# -*- coding: utf-8 -*-
from odoo import api, fields, models


class CanteenMenuItem(models.Model):
    _name = 'canteen.menu.item'
    _description = 'Canteen Menu Item'
    _order = 'category, name'

    name = fields.Char(string='Item Name', required=True)
    category = fields.Selection([
        ('breakfast', 'Breakfast'),
        ('lunch', 'Lunch'),
        ('snacks', 'Snacks'),
        ('dinner', 'Dinner'),
        ('beverages', 'Beverages'),
    ], string='Category', required=True, default='lunch')

    price = fields.Float(string='Price', required=True)
    prep_time = fields.Float(string='Preparation Time (mins)')

    available_mon = fields.Boolean(string='Mon', default=True)
    available_tue = fields.Boolean(string='Tue', default=True)
    available_wed = fields.Boolean(string='Wed', default=True)
    available_thu = fields.Boolean(string='Thu', default=True)
    available_fri = fields.Boolean(string='Fri', default=True)
    available_sat = fields.Boolean(string='Sat', default=True)
    available_sun = fields.Boolean(string='Sun', default=True)

    time_slot_from = fields.Float(string='Available From')
    time_slot_to = fields.Float(string='Available To')

    product_id = fields.Many2one(
        'product.product', string='Linked POS Product',
        help='POS product used for billing this menu item.')
    # NOTE: 'mrp' is not a dependency of this module (it caused an
    # unrelated core view-validation error on some servers: l10n_in_gsp
    # field missing on res.config.settings when mrp installs).
    # If/when 'mrp' is available and working on your server, add 'mrp'
    # back to the 'depends' list in __manifest__.py and uncomment the
    # field below to link a Bill of Materials for recipe-based stock
    # deduction on sale.
    # bom_id = fields.Many2one(
    #     'mrp.bom', string='Recipe / BoM',
    #     help='Raw material recipe used to auto-deduct inventory on sale.')

    image_1920 = fields.Image(string='Image')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)

    is_mess_item = fields.Boolean(
        string='Hostel Mess Item',
        help='Tick if this item belongs to the hostel mess menu '
             'rather than the general canteen menu.')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if not rec.product_id:
                rec._create_pos_product()
        return records

    def _create_pos_product(self):
        """Auto create/link a POS sellable product for this menu item."""
        self.ensure_one()
        # Odoo 19 dropped the old "All" root category (product.product_category_all)
        # in favour of a flatter set of default categories (Goods/Expenses/Services),
        # and categ_id is no longer required on product.template. "Goods" is the
        # closest match for a sellable canteen item; fall back to no category
        # at all if, for some reason, it isn't found.
        categ = self.env.ref('product.product_category_goods', raise_if_not_found=False)
        vals = {
            'name': self.name,
            'list_price': self.price,
            'type': 'consu',
            'available_in_pos': True,
        }
        if categ:
            vals['categ_id'] = categ.id
        product = self.env['product.product'].create(vals)
        self.product_id = product.id