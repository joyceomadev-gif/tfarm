from odoo import models, fields, api
from odoo.exceptions import ValidationError


class PerformanceCycle(models.Model):
    _name = 'hr.performance.cycle'
    _description = 'Performance Management Cycle'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date DESC'

    name = fields.Char(string='Cycle Name', required=True, tracking=True)
    description = fields.Text(string='Description', tracking=True)
    start_date = fields.Date(string='Start Date', required=True, tracking=True)
    goal_submission_deadline = fields.Date(string='Goal Submission Deadline', required=True, tracking=True)
    mid_year_review_date = fields.Date(string='Mid-Year Review Date', tracking=True)
    final_evaluation_date = fields.Date(string='Final Evaluation Date', tracking=True)
    first_cycle_launch_date = fields.Date(string='First Cycle Launch Date', tracking=True)
    
    status = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('evaluation', 'Evaluation Phase'),
        ('closed', 'Closed'),
    ], string='Status', default='draft', tracking=True)
    
    hr_coordinator_id = fields.Many2one(
        'res.users',
        string='HR Coordinator',
        tracking=True,
        help='Responsible HR Officer'
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company
    )
    
    # Relations
    evaluator_assignment_ids = fields.One2many(
        'hr.evaluator.assignment',
        'cycle_id',
        string='Evaluator Assignments'
    )
    goal_ids = fields.One2many(
        'hr.performance.goal',
        'cycle_id',
        string='Performance Goals'
    )
    coaching_session_ids = fields.One2many(
        'hr.coaching.session',
        'cycle_id',
        string='Coaching Sessions'
    )
    scorecard_ids = fields.One2many(
        'hr.final.scorecard',
        'cycle_id',
        string='Final Scorecards'
    )
    
    # Computed fields for dashboard
    total_employees = fields.Integer(
        string='Total Employees',
        compute='_compute_cycle_stats',
        store=True
    )
    goals_approved_count = fields.Integer(
        string='Goals Approved',
        compute='_compute_cycle_stats',
        store=True
    )
    evaluations_pending_count = fields.Integer(
        string='Evaluations Pending',
        compute='_compute_cycle_stats',
        store=True
    )
    evaluations_completed_count = fields.Integer(
        string='Evaluations Completed',
        compute='_compute_cycle_stats',
        store=True
    )

    @api.depends('evaluator_assignment_ids', 'goal_ids', 'scorecard_ids')
    def _compute_cycle_stats(self):
        for cycle in self:
            cycle.total_employees = len(cycle.evaluator_assignment_ids.mapped('employee_id'))
            cycle.goals_approved_count = len(cycle.goal_ids.filtered(lambda g: g.status == 'approved'))
            cycle.evaluations_pending_count = len(cycle.scorecard_ids.filtered(lambda s: s.status == 'draft'))
            cycle.evaluations_completed_count = len(cycle.scorecard_ids.filtered(lambda s: s.status != 'draft'))

    @api.constrains('goal_submission_deadline', 'start_date')
    def _check_dates(self):
        for cycle in self:
            if cycle.goal_submission_deadline < cycle.start_date:
                raise ValidationError('Goal Submission Deadline must be after Start Date.')

    def action_launch_cycle(self):
        """Launch the performance cycle and notify managers."""
        if self.status != 'draft':
            raise ValidationError('Only draft cycles can be launched.')
        
        self.status = 'open'
        self.message_post(body='Performance Cycle launched. Managers notified to nominate evaluators.')
        
        # Send notifications to all managers
        managers = self.env['hr.employee'].search([]).mapped('parent_id').filtered(lambda m: m.id)
        for manager in managers:
            manager.message_notify(
                body='Please nominate evaluators for your team members.',
                subject=f'Evaluator Nomination - {self.name}',
                partner_ids=manager.user_id.partner_id.ids if manager.user_id else []
            )

    def action_start_goal_setting(self):
        """Move cycle to in_progress phase."""
        if self.status != 'open':
            raise ValidationError('Cycle must be in Open status.')
        self.status = 'in_progress'
        self.message_post(body='Goal Setting phase opened for employees.')

    def action_start_evaluation(self):
        """Move cycle to evaluation phase."""
        if self.status != 'in_progress':
            raise ValidationError('Cycle must be in In Progress status.')
        
        # Verify all goals are approved
        unapproved = self.goal_ids.filtered(lambda g: g.status != 'approved')
        if unapproved:
            raise ValidationError(f'{len(unapproved)} goals are not yet approved. Please approve all goals before starting evaluation.')
        
        self.status = 'evaluation'
        self.message_post(body='Evaluation phase started. Evaluators notified to complete assessments.')

    def action_close_cycle(self):
        """Close the cycle and archive data."""
        if self.status not in ('evaluation', 'in_progress'):
            raise ValidationError('Only cycles in Evaluation or In Progress status can be closed.')
        
        self.status = 'closed'
        self.message_post(body='Performance Cycle closed and archived for historical records.')

    def action_reopen_cycle(self):
        """Reopen a closed cycle for corrections (HR only)."""
        if self.status != 'closed':
            raise ValidationError('Only closed cycles can be reopened.')
        self.status = 'evaluation'
        self.message_post(body='Cycle reopened for corrections.')
