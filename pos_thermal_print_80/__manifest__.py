{
    'name': 'POS Thermal Print 80mm',
    'version': '17.0.1.0.0',
    'category': 'Point of Sale',
    'summary': 'POS Order 80mm thermal print with KOPIJA header and tax calculation fix',
    'description': """
        This module provides:
        - POS Order 80mm thermal print action for backend printing
        - KOPIJA header to distinguish from original frontend receipts
        - Fixed tax calculation to ensure tax total matches tax specification
        - Optimized layout for 80mm thermal roll paper
    """,
    'depends': ['point_of_sale', 'pos_fiscalization'],
    'data': [
        'report/pos_order_80_report.xml',
        'report/pos_order_80_template.xml',
    ],
    'sequence': -150,
    'installable': True,
    'auto_install': False,
    'application': False,
}
