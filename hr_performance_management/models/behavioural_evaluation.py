from odoo import models, fields, api
from odoo.exceptions import ValidationError


class BehaviouralEvaluation(models.Model):
    _name = 'hr.behavioural.evaluation'
    _description = 'Behavioral Evaluation'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    cycle_id = fields.Many2one(
        'hr.performance.cycle',
        string='Performance Cycle',
        required=True,
        ondelete='cascade'
    )
    goal_id = fields.Many2one(
        'hr.performance.goal',
        string='Goal',
        required=True,
        ondelete='cascade'
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        related='goal_id.employee_id',
        store=True,
        readonly=True
    )
    
    evaluator_id = fields.Many2one(
        'hr.employee',
        string='Evaluator (Peer/Subordinate/Customer)',
        required=True,
        tracking=True
    )
    evaluator_type = fields.Selection([
        ('peer', 'Peer'),
        ('subordinate', 'Subordinate'),
        ('internal_customer', 'Internal Customer'),
        ('external_customer', 'External Customer'),
    ], string='Evaluator Type', required=True, tracking=True)
    
    # Behavioral Areas - 5-point scale (1-5)
    teamwork_score = fields.Integer(
        string='Teamwork',
        required=True,
        tracking=True,
        help='Scale 1-5: Poor to Excellent'
    )
    
    communication_score = fields.Integer(
        string='Communication',
        required=True,
        tracking=True,
        help='Scale 1-5: Poor to Excellent'
    )
    
    leadership_score = fields.Integer(
        string='Leadership',
        required=True,
        tracking=True,
        help='Scale 1-5: Poor to Excellent'
    )
    
    integrity_score = fields.Integer(
        string='Integrity',
        required=True,
        tracking=True,
        help='Scale 1-5: Poor to Excellent'
    )
    
    initiative_score = fields.Integer(
        string='Initiative',
        required=True,
        tracking=True,
        help='Scale 1-5: Poor to Excellent'
    )
    
    problem_solving_score = fields.Integer(
        string='Problem Solving',
        required=True,
        tracking=True,
        help='Scale 1-5: Poor to Excellent'
    )
    
    # Computed average
    behavioral_average_score = fields.Float(
        string='Behavioral Average Score',
        compute='_compute_behavioral_average',
        store=True,
        help='Average of all behavioral areas'
    )
    
    evaluator_comments = fields.Text(
        string='Evaluator Comments',
        tracking=True
    )
    
    status = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('finalized', 'Finalized'),
    ], string='Status', default='draft', tracking=True)
    
    anonymous_feedback = fields.Boolean(
        string='Anonymous Feedback',
        default=True,
        help='Whether this evaluation should be kept anonymous from the employee'
    )

    _sql_constraints = [
        (
            'unique_evaluator_per_goal',
            'UNIQUE(cycle_id, goal_id, evaluator_id)',
            'Each evaluator can only evaluate an employee once per cycle.'
        )
    ]

    @api.constrains(
        'teamwork_score', 'communication_score', 'leadership_score',
        'integrity_score', 'initiative_score', 'problem_solving_score'
    )
    def _check_scores(self):
        for eval_record in self:
            scores = [
                eval_record.teamwork_score,
                eval_record.communication_score,
                eval_record.leadership_score,
                eval_record.integrity_score,
                eval_record.initiative_score,
                eval_record.problem_solving_score,
            ]
            for score in scores:
                if not (1 <= score <= 5):
                    raise ValidationError('All behavioral scores must be between 1 (Poor) and 5 (Excellent).')

    @api.depends(
        'teamwork_score', 'communication_score', 'leadership_score',
        'integrity_score', 'initiative_score', 'problem_solving_score'
    )
    def _compute_behavioral_average(self):
        for eval_record in self:
            scores = [
                eval_record.teamwork_score,
                eval_record.communication_score,
                eval_record.leadership_score,
                eval_record.integrity_score,
                eval_record.initiative_score,
                eval_record.problem_solving_score,
            ]
            eval_record.behavioral_average_score = sum(scores) / len(scores) if scores else 0.0

    def action_submit_evaluation(self):
        """Submit behavioral evaluation."""
        if self.status != 'draft':
            raise ValidationError('Only draft evaluations can be submitted.')
        
        self.status = 'submitted'
        self.message_post(body='Behavioral evaluation submitted.')

    def action_finalize_evaluation(self):
        """Finalize evaluation (prevent further edits)."""
        if self.status != 'submitted':
            raise ValidationError('Only submitted evaluations can be finalized.')
        
        self.status = 'finalized'
        self.message_post(body='Behavioral evaluation finalized.')
