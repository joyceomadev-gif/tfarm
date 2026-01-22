{
    'name': 'Taghini Farm Management',
    'version': '1.0',
    'category': 'Manufacturing/Agriculture',
    'summary': 'Manage Broiler Flocks, Mortality, and Daily Logs',
    'depends': ['base', 'stock', 'product'],
    'data': [
        'security/ir.model.access.csv',
        'views/flock_views.xml',
        'views/daily_log_views.xml',
    ],
    'installable': True,
    'application': True,
}