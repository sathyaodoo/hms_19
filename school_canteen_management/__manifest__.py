# -*- coding: utf-8 -*-
{
    'name': 'School Canteen Management',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Canteen menu, token ordering, POS billing, student wallet, '
                'hostel mess integration, inventory & vendor management.',
    'description': """
School Canteen Management
==========================
- Daily/Weekly menu configuration (Breakfast/Lunch/Snacks/Dinner/Beverages)
- Hostel mess menu & meal plan configuration
- Token based pre-ordering with QR code
- POS counter billing integration
- Student prepaid wallet with low balance alerts
- Inventory deduction via BoM (Manufacturing)
- Vendor purchase routing via Purchase module
- Wastage / Spoilage log
- Daily Sales, Popular Items, Revenue vs Cost reports
- Hostel mess charge integration with fee billing
    """,
    'author': 'Custom Development',
    'depends': [
        'point_of_sale',
        'pos_restaurant',
        'stock',
        'purchase',
        'account',
        'portal',
        'mail',
        'website',
    ],
    'data': [
        'security/canteen_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/mail_template_data.xml',
        'data/ir_cron_data.xml',
        'views/canteen_menu_item_views.xml',
        'views/canteen_mess_menu_views.xml',
        'views/canteen_order_views.xml',
        'views/portal_templates.xml',
        'views/student_wallet_views.xml',
        'views/canteen_wastage_log_views.xml',
        'views/pos_config_views.xml',
        'reports/canteen_token_report.xml',
        'reports/canteen_sales_report_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}