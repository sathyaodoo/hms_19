{
    'name': 'Company Wise Menu Visibility',
    'version': '19.0.1.0.0',
    'category': 'Technical',
    'summary': 'Show/hide App Menus (Sales, Purchase, Inventory, etc.) based on active company',
    'description': """
Company Wise Menu Visibility
=============================
Adds a "Companies" field on Menu Items (Settings > Technical > User
Interface > Menu Items).

- If you leave the "Companies" field EMPTY on a menu, it behaves as
  before -> visible to everyone (subject to normal group access).
- If you SELECT one or more companies on a menu (e.g. the root "Sales"
  app menu), that menu -and all its sub menus- will be visible ONLY
  when one of the selected companies is the currently active
  (selected) company in the top-right company switcher.

Example: set "Company 2" on the Purchase app root menu -> Purchase
app will disappear from the left sidebar for anyone whose active
company is not Company 2, and reappear the moment they switch to
Company 2.
    """,
    'author': 'Custom',
    'website': '',
    'depends': ['web'],
    'data': [
        'views/ir_ui_menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'company_wise_menu/static/src/js/company_wise_menu_patch.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
