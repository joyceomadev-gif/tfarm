from odoo import models, fields, api
from odoo.exceptions import ValidationError


class TechnicalEvaluation(models.Model):
    _name = 'hr.technical.evaluation'
    _description = 'Technical Evaluation'
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
        string='Evaluator (Manager/HOD)',
        required=True,
        tracking=True
    )
    
    # Evaluation Areas with Weights (fixed)
    goal_achievement_score = fields.Float(
        string='Goal Achievement Score',
        required=True,
        tracking=True,
        help='Score for goal achievement (0-100)'
    )
    goal_achievement_weight = fields.Float(
        string='Goal Achievement Weight %',
        default=60.0,
        readonly=True
    )
    
    quality_of_work_score = fields.Float(
        string='Quality of Work Score',
        required=True,
        tracking=True,
        help='Score for quality (0-100)'
    )
    quality_of_work_weight = fields.Float(
        string='Quality Weight %',
        default=15.0,
        readonly=True
    )
    
    productivity_score = fields.Float(
        string='Productivity Score',
        required=True,
        tracking=True,
        help='Score for productivity (0-100)'
    )
    productivity_weight = fields.Float(
        string='Productivity Weight %',
        default=10.0,
        readonly=True
    )
    
    innovation_score = fields.Float(
        string='Innovation Score',
        required=True,
        tracking=True,
        help='Score for innovation (0-100)'
    )
    innovation_weight = fields.Float(
        string='Innovation Weight %',
        default=15.0,
        readonly=True
    )
    
    # Weighted Total
    technical_score = fields.Float(
        string='Technical Score',
        compute='_compute_technical_score',
        store=True,
        help='Weighted average of all evaluation areas'
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

    @api.constrains('goal_achievement_score', 'quality_of_work_score', 'productivity_score', 'innovation_score')
    def _check_scores(self):
        for eval_record in self:
            scores = [
                eval_record.goal_achievement_score,
                eval_record.quality_of_work_score,
                eval_record.productivity_score,
                eval_record.innovation_score,
            ]
            for score in scores:
                if not (0 <= score <= 100):
                    raise ValidationError('All scores must be between 0 and 100.')

    @api.depends(
        'goal_achievement_score', 'quality_of_work_score',
        'productivity_score', 'innovation_score'
    )
    def _compute_technical_score(self):
        for eval_record in self:
            eval_record.technical_score = (
                (eval_record.goal_achievement_score * eval_record.goal_achievement_weight / 100) +
                (eval_record.quality_of_work_score * eval_record.quality_of_work_weight / 100) +
                (eval_record.productivity_score * eval_record.productivity_weight / 100) +
                (eval_record.innovation_score * eval_record.innovation_weight / 100)
            )

    def action_submit_evaluation(self):
        """Submit technical evaluation."""
        if self.status != 'draft':
            raise ValidationError('Only draft evaluations can be submitted.')
        
        self.status = 'submitted'
        self.message_post(body='Technical evaluation submitted.')

    def action_finalize_evaluation(self):
        """Finalize evaluation (prevent further edits)."""
        if self.status != 'submitted':
            raise ValidationError('Only submitted evaluations can be finalized.')
        
        self.status = 'finalized'
        self.message_post(body='Technical evaluation finalized.')
