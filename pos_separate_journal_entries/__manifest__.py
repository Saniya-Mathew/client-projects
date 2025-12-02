{
    'name': 'POS Separate Journal Entries',
    'version': '17.0.2.1.1',
    'category': 'Point of Sale',
    'summary': 'Add partner information to POS journal entries',
    'description': """
        This module add customer information to POS journal entries
        for better tracking and reconciliation.
    """,
    'depends': ['point_of_sale'],
    'data': [
        'views/pos_session_view.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}