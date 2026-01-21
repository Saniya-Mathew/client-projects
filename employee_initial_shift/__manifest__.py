{
    'name': 'Employee Initial Shift',
    'version': '1.0.0',
    'summary': 'Add initial shift to employees and expose it in Planning',
    'category': 'Human Resources',
    'author': 'Custom',
    'license': 'LGPL-3',
    'depends': ['hr', 'planning'],
    'data': [
        'security/ir.model.access.csv',
        'views/hr_employee_views.xml',
        'views/planning_views.xml',
        'views/planning_template_views.xml',
        'views/skills_views.xml',
        'data/shift_rotation_cron.xml',
    ],
    'installable': True,
    'application': False,
}
