# -*- coding: utf-8 -*-
{
    'name': 'Santhigiri HMS — Custom Extensions',
    'version': '19.0.1.0.0',
    'summary': 'Hospital Management System customisation for Santhigiri Ayurveda Hospital',
    'description': '''
        Custom extensions on top of base_hospital_management for Santhigiri Ayurveda Hospital.
        Covers: Patient (nationality/Aadhaar/allergy), OP (category fee, 3 outcomes, Anupanam/Route),
        Casualty (full workflow), IP (categories, treatment/medication plans, discharge bill),
        Food Management, Daily Procedures, Pharmacy (OP/IP split), Lab (abnormal alert),
        Medical Camps, Internship Management, Purchase approval, NCISM reports.
    ''',
    'author': 'Santhigiri HMS Implementation Team',
    'category': 'Healthcare',
    'depends': ['base_hospital_management', 'purchase', 'stock', 'mail', 'website'],
    'data': [
        # Security (load first)
        'security/santhigiri_groups.xml',
        'security/ir.model.access.csv',
        # Sequences & cron
        'data/ir_sequence_data.xml',
        'data/website_data.xml',
        'data/ir_cron_data.xml',
        # Views
        'views/patient_room_views.xml',
        'views/product_template_views.xml',
        'views/lab_test_views.xml',
        'views/hr_employee_views.xml',
        'views/res_partner_views.xml',
        'views/fee_master_views.xml',
        'views/hospital_outpatient_views.xml',
        'views/hospital_inpatient_views.xml',
        'views/hospital_casualty_views.xml',
        'views/hospital_procedure_views.xml',
        'views/hospital_treatment_plan_views.xml',
        'views/hospital_diet_views.xml',
        'views/hospital_camp_views.xml',
        'views/hospital_intern_views.xml',
        'views/portal_templates.xml',
        'views/hospital_followup_views.xml',
        'views/purchase_approval_views.xml',
        'views/menu_views.xml',
        'views/hospital_pharmacy_views.xml',
        'views/patient_emr_views.xml',
        'views/op_assessment_views.xml',
        'views/reassessment_views.xml',

        # Reports
        'reports/patient_card_override.xml',
        'reports/referral_letter_report.xml',
        'reports/camp_report.xml',
        'reports/discharge_summary_report.xml',
        'reports/bystander_pass_report.xml',
        'reports/form_c_report.xml',
        'reports/ncism_reports.xml',
        'reports/santhigiri_custom_reports.xml',
        'reports/report_assessment.xml',
        'reports/reassessment_report.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
