{
    'name': 'HR Performance Management System',
    'version': '1.0.0',
    'category': 'Human Resources',
    'summary': '360-Degree Performance Management with Goal Setting, Evaluations, and Coaching',
    'description': """
        Complete HR Performance Management System featuring:
        - Performance cycle management (annual, quarterly, etc.)
        - Multi-evaluator assessment (technical, behavioral, peers, subordinates)
        - SMART goal setting and tracking with progress updates
        - Continuous coaching and review meetings
        - Automated scorecard consolidation
        - Employee appeals and acknowledgement
        - Performance Improvement Plan (PIP) auto-trigger
        - Historical archival and reporting
        - Role-based dashboards (HR, Manager, Employee)
    """,
    'author': 'Kadi',
    'depends': [
        'base',
        'hr',
        'mail',
        'web',
    ],
    'data': [
        # Security
        'security/performance_security.xml',
        
        # Data
        'data/ir_sequence_data.xml',
        'security/ir.model.access.csv',
        
        # Views - Performance Cycle
        'views/performance_cycle_views.xml',
        
        # Views - Evaluator Assignment
        'views/evaluator_assignment_views.xml',
        
        # Views - Performance Goal
        'views/performance_goal_views.xml',
        
        # Views - Goal Progress
        'views/goal_progress_update_views.xml',
        
        # Views - Coaching Session
        'views/coaching_session_views.xml',
        
        # Views - Technical Evaluation
        'views/technical_evaluation_views.xml',
        
        # Views - Behavioral Evaluation
        'views/behavioural_evaluation_views.xml',
        
        # Views - Final Scorecard
        'views/final_scorecard_views.xml',
        
        # Views - Appeal Record
        'views/appeal_record_views.xml',
        
        # Views - PIP
        'views/performance_improvement_plan_views.xml',
        
        # Menus
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
