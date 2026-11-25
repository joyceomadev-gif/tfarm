from odoo import models, fields, api
from odoo.exceptions import ValidationError


class FinalScorecard(models.Model):
    _name = 'hr.final.scorecard'
    _description = 'Final Performance Scorecard'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']

    def _compute_access_url(self):
        super()._compute_access_url()
        for scorecard in self:
            scorecard.access_url = f'/my/performance/scorecards/{scorecard.id}'

    cycle_id = fields.Many2one(
        'hr.performance.cycle',
        string='Performance Cycle',
        required=True,
        ondelete='cascade'
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        tracking=True
    )
    manager_id = fields.Many2one(
        'hr.employee',
        string='Manager',
        related='employee_id.parent_id',
        store=True,
        readonly=True
    )
    
    # Goal Achievement Component (60% weight)
    total_goals = fields.Integer(
        string='Total Goals',
        compute='_compute_goal_metrics',
        store=True
    )
    goals_approved = fields.Integer(
        string='Goals Approved',
        compute='_compute_goal_metrics',
        store=True
    )
    average_goal_achievement = fields.Float(
        string='Average Goal Achievement %',
        compute='_compute_goal_metrics',
        store=True
    )
    goal_achievement_score = fields.Float(
        string='Goal Achievement Score',
        compute='_compute_goal_achievement_score',
        store=True,
        help='Avg goal achievement % (60% of final)'
    )
    goal_achievement_weight = fields.Float(
        string='Goal Weight %',
        default=60.0,
        readonly=True
    )
    
    # Technical Evaluation Component (25% weight)
    technical_evaluation_ids = fields.One2many(
        'hr.technical.evaluation',
        compute='_get_technical_evaluations'
    )
    average_technical_score = fields.Float(
        string='Average Technical Score',
        compute='_compute_technical_metrics',
        store=True,
        help='Average of all manager/HOD technical evaluations'
    )
    technical_weight = fields.Float(
        string='Technical Weight %',
        default=25.0,
        readonly=True
    )
    
    # Behavioral Evaluation Component (15% weight)
    behavioural_evaluation_ids = fields.One2many(
        'hr.behavioural.evaluation',
        compute='_get_behavioural_evaluations'
    )
    
    scorecard_goal_ids = fields.One2many(
    'hr.performance.goal',
    compute='_compute_scorecard_goals',
    string='Goals'
    )
    
    average_behavioral_score = fields.Float(
        string='Average Behavioral Score',
        compute='_compute_behavioral_metrics',
        store=True,
        help='Average of all peer/subordinate behavioral evaluations'
    )
    behavioral_weight = fields.Float(
        string='Behavioral Weight %',
        default=15.0,
        readonly=True
    )
    
    # FINAL SCORE
    final_score = fields.Float(
        string='Final Score',
        compute='_compute_final_score',
        store=True,
        help='Weighted average of all components (0-100)'
    )
    
    performance_rating = fields.Selection([
        ('poor', 'Poor (1-20)'),
        ('fair', 'Fair (21-40)'),
        ('good', 'Good (41-60)'),
        ('very_good', 'Very Good (61-80)'),
        ('excellent', 'Excellent (81-100)'),
    ], string='Performance Rating', compute='_compute_performance_rating', store=True)
    
    # Employee Review & Acknowledgement
    employee_acknowledgement = fields.Selection([
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('appealed', 'Appealed'),
    ], string='Employee Acknowledgement', default='pending', tracking=True)
    
    employee_comments = fields.Text(
        string='Employee Comments on Appraisal',
        tracking=True
    )
    
    # HR Approval
    hr_approved = fields.Boolean(
        string='HR Approved',
        tracking=True,
        default=False
    )
    
    status = fields.Selection([
        ('draft', 'Draft'),
        ('technical_evaluation', 'Technical Evaluation Pending'),
        ('behavioral_evaluation', 'Behavioral Evaluation Pending'),
        ('employee_review', 'Awaiting Employee Review'),
        ('appeal', 'Under Appeal'),
        ('closed', 'Closed'),
    ], string='Status', default='draft', tracking=True)
    
    # PIP Check
    requires_pip = fields.Boolean(
        string='Requires PIP',
        compute='_compute_requires_pip',
        store=True,
        help='Auto-set if final score < 60%'
    )
    pip_id = fields.One2many(
        'hr.performance.improvement.plan',
        'scorecard_id',
        string='Performance Improvement Plans'
    )

    @api.depends('cycle_id', 'employee_id')
    def _get_technical_evaluations(self):
        for scorecard in self:
            scorecard.technical_evaluation_ids = self.env['hr.technical.evaluation'].search([
                ('cycle_id', '=', scorecard.cycle_id.id),
                ('employee_id', '=', scorecard.employee_id.id),
            ])

    @api.depends('cycle_id', 'employee_id')
    def _get_behavioural_evaluations(self):
        for scorecard in self:
            scorecard.behavioural_evaluation_ids = self.env['hr.behavioural.evaluation'].search([
                ('cycle_id', '=', scorecard.cycle_id.id),
                ('employee_id', '=', scorecard.employee_id.id),
            ])

    @api.depends('cycle_id', 'employee_id')
    def _compute_goal_metrics(self):
        for scorecard in self:
            goals = self.env['hr.performance.goal'].search([
                ('cycle_id', '=', scorecard.cycle_id.id),
                ('employee_id', '=', scorecard.employee_id.id),
            ])
            scorecard.total_goals = len(goals)
            scorecard.goals_approved = len(goals.filtered(lambda g: g.status == 'approved'))
            
            achievements = goals.mapped('actual_achievement_percentage')
            scorecard.average_goal_achievement = sum(achievements) / len(achievements) if achievements else 0.0

    @api.depends('average_goal_achievement')
    def _compute_goal_achievement_score(self):
        for scorecard in self:
            scorecard.goal_achievement_score = scorecard.average_goal_achievement

    @api.depends('technical_evaluation_ids')
    def _compute_technical_metrics(self):
        for scorecard in self:
            scores = scorecard.technical_evaluation_ids.mapped('technical_score')
            scorecard.average_technical_score = sum(scores) / len(scores) if scores else 0.0

    @api.depends('behavioural_evaluation_ids')
    def _compute_behavioral_metrics(self):
        for scorecard in self:
            scores = scorecard.behavioural_evaluation_ids.mapped('behavioral_average_score')
            scorecard.average_behavioral_score = sum(scores) / len(scores) if scores else 0.0

    @api.depends('goal_achievement_score', 'average_technical_score', 'average_behavioral_score')
    def _compute_final_score(self):
        for scorecard in self:
            scorecard.final_score = (
                (scorecard.goal_achievement_score * scorecard.goal_achievement_weight / 100) +
                (scorecard.average_technical_score * scorecard.technical_weight / 100) +
                (scorecard.average_behavioral_score * scorecard.behavioral_weight / 100)
            )

    @api.depends('final_score')
    def _compute_performance_rating(self):
        for scorecard in self:
            if scorecard.final_score >= 81:
                scorecard.performance_rating = 'excellent'
            elif scorecard.final_score >= 61:
                scorecard.performance_rating = 'very_good'
            elif scorecard.final_score >= 41:
                scorecard.performance_rating = 'good'
            elif scorecard.final_score >= 21:
                scorecard.performance_rating = 'fair'
            else:
                scorecard.performance_rating = 'poor'

    @api.depends('final_score')
    def _compute_requires_pip(self):
        for scorecard in self:
            scorecard.requires_pip = scorecard.final_score < 60.0
    
    
    @api.depends('cycle_id', 'employee_id')
    def _compute_scorecard_goals(self):
        for scorecard in self:
            scorecard.scorecard_goal_ids = self.env['hr.performance.goal'].search([
                ('cycle_id', '=', scorecard.cycle_id.id),
                ('employee_id', '=', scorecard.employee_id.id),
            ])

    def action_request_employee_review(self):
        """Send scorecard to employee for acknowledgement."""
        if self.status != 'draft':
            raise ValidationError('Only draft scorecards can be sent for employee review.')
        
        self.status = 'employee_review'
        self.message_post(body=f'Scorecard sent to employee for review. Final Score: {self.final_score:.2f}%')
        
        if self.employee_id.user_id:
            self.employee_id.user_id.notify_info(
                f'Your final appraisal score is {self.final_score:.2f}%. Please review and acknowledge.',
                title='Final Appraisal Review Required'
            )

    def action_employee_accept(self):
        """Employee accepts the appraisal."""
        if self.status != 'employee_review':
            raise ValidationError('Scorecard must be in Employee Review status.')
        
        self.employee_acknowledgement = 'accepted'
        self.message_post(body='Employee accepted the final appraisal.')
        
        # Auto-trigger PIP if needed
        if self.requires_pip:
            self._create_pip()

    def action_employee_appeal(self):
        """Employee appeals the scorecard."""
        if self.status != 'employee_review':
            raise ValidationError('Scorecard must be in Employee Review status.')
        
        self.employee_acknowledgement = 'appealed'
        self.status = 'appeal'
        self.message_post(body='Employee appealed the appraisal. Creating appeal record.')
        
        # Create appeal record
        self.env['hr.appeal.record'].create({
            'scorecard_id': self.id,
            'employee_id': self.employee_id.id,
            'appeal_reason': 'Employee initiated appeal',
        })

    def action_hr_approve(self):
        """HR approves and closes the scorecard."""
        if self.status not in ('employee_review', 'appeal'):
            raise ValidationError('Scorecard must be in Employee Review or Appeal status.')
        
        self.hr_approved = True
        self.status = 'closed'
        self.message_post(body='Appraisal approved by HR and closed.')
        
        # Auto-trigger PIP if needed and not already created
        if self.requires_pip and not self.pip_id:
            self._create_pip()

    def _create_pip(self):
        """Auto-create Performance Improvement Plan if score < 60%."""
        self.env['hr.performance.improvement.plan'].create({
            'scorecard_id': self.id,
            'employee_id': self.employee_id.id,
            'manager_id': self.manager_id.id,
            'start_date': fields.Date.context_today(self),
            'duration_weeks': 13,
        })
        self.message_post(body='Performance Improvement Plan automatically created due to low score.')

    def action_view_appeal(self):
        """View or create appeal record."""
        appeals = self.pip_id
        if appeals:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Appeal Record',
                'res_model': 'hr.appeal.record',
                'res_id': appeals[0].id,
                'view_mode': 'form',
            }
        else:
            return {
                'name': 'Create Appeal',
                'type': 'ir.actions.act_window',
                'res_model': 'hr.appeal.record',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_scorecard_id': self.id,
                    'default_employee_id': self.employee_id.id,
                }
            }
