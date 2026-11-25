from odoo import models, fields, api
from odoo.exceptions import ValidationError


class PerformanceGoal(models.Model):
    _name = 'hr.performance.goal'
    _description = 'Performance Goal'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']

    def _compute_access_url(self):
        super()._compute_access_url()
        for goal in self:
            goal.access_url = f'/my/performance/goals/{goal.id}'

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
    
    goal_code = fields.Char(string='Goal Code', required=True, tracking=True)
    goal_description = fields.Text(string='Goal Description', required=True, tracking=True)
    objective = fields.Text(string='Objective', required=True, tracking=True)
    kpi = fields.Char(string='KPI (Key Performance Indicator)', required=True, tracking=True)
    measurement_criteria = fields.Text(string='Measurement Criteria', required=True, tracking=True)
    weight = fields.Float(
        string='Weight (%)',
        required=True,
        default=0.0,
        tracking=True,
        help='Percentage weight of this goal towards final score'
    )
    
    start_date = fields.Date(string='Start Date', required=True, tracking=True)
    end_date = fields.Date(string='End Date', required=True, tracking=True)
    
    expected_outcome = fields.Text(string='Expected Outcome', tracking=True)
    required_tools = fields.Text(string='Required Tools', tracking=True)
    required_training = fields.Text(string='Required Training', tracking=True)
    resources_needed = fields.Text(string='Resources Needed', tracking=True)
    
    status = fields.Selection([
        ('draft', 'Draft'),
        ('employee_review', 'Employee Review'),
        ('employee_response', 'Employee Response'),
        ('manager_revision', 'Manager Revision'),
        ('approved', 'Approved'),
        ('locked', 'Locked'),
        ('closed', 'Closed'),
    ], string='Status', default='draft', tracking=True)
    
    # Achievement and Progress
    progress_percentage = fields.Float(
        string='Progress %',
        compute='_compute_progress',
        store=True,
        readonly=True
    )
    actual_achievement_percentage = fields.Float(
        string='Actual Achievement %',
        default=0.0,
        tracking=True,
        help='Final achievement % when goal closes'
    )
    
    # Relations
    progress_update_ids = fields.One2many(
        'hr.goal.progress.update',
        'goal_id',
        string='Progress Updates'
    )
    technical_evaluation_id = fields.One2many(
        'hr.technical.evaluation',
        'goal_id',
        string='Technical Evaluations'
    )
    behavioural_evaluation_ids = fields.One2many(
        'hr.behavioural.evaluation',
        'goal_id',
        string='Behavioral Evaluations'
    )
    
    employee_comments = fields.Text(
        string='Employee Comments on Goal',
        tracking=True,
        help='Employee feedback/modifications requested'
    )
    manager_comments = fields.Text(
        string='Manager Comments',
        tracking=True
    )

    _sql_constraints = [
        (
            'unique_goal_code',
            'UNIQUE(cycle_id, employee_id, goal_code)',
            'Goal code must be unique per employee per cycle.'
        ),
        (
            'weight_positive',
            'CHECK(weight >= 0)',
            'Weight must be positive.'
        )
    ]

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for goal in self:
            if goal.end_date < goal.start_date:
                raise ValidationError('End Date must be after Start Date.')

    @api.depends('progress_update_ids')
    def _compute_progress(self):
        for goal in self:
            if goal.progress_update_ids:
                goal.progress_percentage = max(goal.progress_update_ids.mapped('progress_percentage'))
            else:
                goal.progress_percentage = 0.0

    def action_request_employee_review(self):
        """Manager sends goal to employee for review."""
        if self.status != 'draft':
            raise ValidationError('Goal must be in Draft status.')
        
        self.status = 'employee_review'
        self.message_post(body='Goal sent to employee for review.')
        
        if self.employee_id.user_id:
            self.employee_id.user_id.notify_info(
                f'Manager {self.manager_id.name} has set a goal for your review.',
                title='Goal Review Required'
            )

    def action_employee_agree(self):
        """Employee agrees to the goal."""
        if self.status != 'employee_review':
            raise ValidationError('Goal must be under Employee Review.')
        
        self.status = 'approved'
        self.message_post(body='Employee agreed to goal. Goal approved and locked.')

    def action_employee_request_modification(self):
        """Employee requests modification."""
        if self.status != 'employee_review':
            raise ValidationError('Goal must be under Employee Review.')
        
        self.status = 'employee_response'
        self.message_post(body='Employee requested modification. Awaiting manager revision.')
        
        if self.manager_id.user_id:
            self.manager_id.user_id.notify_info(
                f'Employee {self.employee_id.name} requested modification on goal.',
                title='Goal Modification Requested'
            )

    def action_manager_revise_goal(self):
        """Manager revises the goal after employee feedback."""
        if self.status != 'employee_response':
            raise ValidationError('Goal must be under Employee Response status.')
        
        self.status = 'manager_revision'
        self.message_post(body='Goal revised by manager. Sent back to employee.')
        
        if self.employee_id.user_id:
            self.employee_id.user_id.notify_info(
                'Your manager has revised the goal. Please review.',
                title='Goal Revision for Review'
            )

    def action_approve_goal(self):
        """Final approval - goal is locked for execution."""
        if self.status not in ('draft', 'employee_review', 'manager_revision'):
            raise ValidationError('Goal must be in Draft, Employee Review, or Manager Revision status.')
        
        self.status = 'approved'
        self.message_post(body='Goal approved and locked for execution.')

    def action_lock_goal(self):
        """Lock goal to prevent further editing."""
        if self.status != 'approved':
            raise ValidationError('Goal must be Approved before locking.')
        
        self.status = 'locked'
        self.message_post(body='Goal locked. No further edits allowed.')

    def action_close_goal(self):
        """Close goal after cycle closes."""
        self.status = 'closed'
        self.message_post(body='Goal closed with actual achievement: ' + str(self.actual_achievement_percentage) + '%')

    def action_add_personal_development_goal(self):
        """Quick action for employee to add a personal development goal."""
        return {
            'name': 'Add Personal Development Goal',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.performance.goal',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_cycle_id': self.cycle_id.id,
                'default_employee_id': self.employee_id.id,
                'default_goal_code': 'PD-' + self.employee_id.id,
            }
        }
