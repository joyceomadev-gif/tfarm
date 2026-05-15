{
    'name': 'Helpdesk Customizations (Payco)',
    'version': '1.0',
    'category': 'Services/Helpdesk',
    'depends': ['helpdesk', 'mail', 'knowledge', 'voip'],
    'data': [
        'security/ir_rule.xml',
        'data/ir_cron.xml',
        'data/helpdesk_stage_data.xml',
        'views/helpdesk_team_views.xml',
        'views/helpdesk_ticket_views.xml',
    ],
    'installable': True,
    'application': False,
}