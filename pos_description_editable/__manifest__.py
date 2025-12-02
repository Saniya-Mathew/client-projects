# -*- coding: utf-8 -*-
{
    'name': "POS Description Editable",
    'version': '17.0.1.0.0',
    'summary': """POS product Description Editable""",
    'description': """POS product Description Editable""",
    'category': 'Point Of Sale',
    'depends': ['point_of_sale'],
    'data': [

    ],
    "assets": {
        'point_of_sale._assets_pos': [
            'pos_description_editable/static/src/js/pos_custom_button.js',
            'pos_description_editable/static/src/xml/pos_custom_button.xml',
        ],
    },
    'license': "AGPL-3",
    'installable': True,
    'application': True,
}