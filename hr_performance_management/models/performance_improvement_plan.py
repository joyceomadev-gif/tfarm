from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import timedelta


class PerformanceImprovementPlan(models.Model):
    _name = 'hr.performance.improvement.plan'
    _description = 'Performance Improvement Plan (PIP)'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    scorecard_id = fields.Many2one(
        'hr.final.scorecard',
        string='Related Scorecard',
        required=True,
        ondelete='cascade'
    )
    cycle_id = fields.Many2one(
        'hr.performance.cycle',
        string='Performance Cycle',
        related='scorecard_id.cycle_id',
        store=True,
        readonly=True
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
        required=True,
        tracking=True
    )
    hr_specialist_id = fields.Many2one(
        'res.users',
        string='HR Specialist',
        tracking=True,
        help='HR person responsible for monitoring PIP'
    )
    
    # PIP Timeline
    start_date = fields.Date(
        string='PIP Start Date',
        required=True,
        tracking=True
    )
    duration_weeks = fields.Integer(
        string='Duration (Weeks)',
        default=13,
        tracking=True,
        help='Typically 13 weeks (3 months)'
    )
    end_date = fields.Date(
        string='PIP End Date',
        compute='_compute_end_date',
        store=True,
        readonly=True
    )
    
    # Improvement Areas
    improvement_areas = fields.Text(
        string='Areas for Improvement',
        required=True,
        tracking=True,
        help='Specific areas where performance must improve'
    )
    
    objectives = fields.Text(
        string='PIP Objectives',
        required=True,
        tracking=True,
        help='Specific, measurable objectives employee must achieve'
    )
    
    success_criteria = fields.Text(
        string='Success Criteria',
        required=True,
        tracking=True,
        help='Clear metrics to measure if PIP is successful'
    )
    
    # Support & Resources
    support_provided = fields.Text(
        string='Support & Resources Provided',
        tracking=True,
        help='Training, mentoring, tools provided to help employee succeed'
    )
    
    training_required = fields.Text(
        string='Required Training',
        tracking=True
    )
    
    # Monitoring
    review_frequency = fields.Selection([
        ('weekly', 'Weekly'),
        ('biweekly', 'Bi-weekly'),
        ('monthly', 'Monthly'),
    ], string='Review Frequency', default='weekly', tracking=True)
    
    progress_tracking = fields.Text(
        string='Progress Tracking Notes',
        tracking=True,
        help='Updated periodically to record progress'
    )
    
    # Status & Outcome
    status = fields.Selection([
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('converted', 'Converted to Disciplinary'),
        ('terminated', 'Terminated'),
    ], string='Status', default='active', tracking=True)
    
    outcome = fields.Selection([
        ('not_met', 'Not Met'),
        ('partially_met', 'Partially Met'),
        ('met', 'Met'),
        ('exceeded', 'Exceeded'),
    ], string='Outcome', tracking=True)
    
    outcome_notes = fields.Text(
        string='Outcome Notes',
        tracking=True,
        help='Summary of PIP results and recommendations'
    )
    
    # Follow-up Action
    follow_up_action = fields.Selection([
        ('continue_employment', 'Continue Employment'),
        ('extension', 'PIP Extension'),
        ('disciplinary', 'Escalate to Disciplinary'),
        ('termination', 'Termination'),
    ], string='Follow-up Action', tracking=True)

    @api.depends('start_date', 'duration_weeks')
    def _compute_end_date(self):
        for pip in self:
            if pip.start_date and pip.duration_weeks:
                pip.end_date = pip.start_date + timedelta(weeks=pip.duration_weeks)
            else:
                pip.end_date = False

    @api.constrains('start_date', 'duration_weeks')
    def _check_pip_timeline(self):
        for pip in self:
            if pip.duration_weeks <= 0:
                raise ValidationError('Duration must be greater than 0 weeks.')

    def action_activate_pip(self):
        """Activate PIP and notify employee."""
        if self.status != 'active':
            self.status = 'active'
        
        self.message_post(body='Performance Improvement Plan activated.')
        
        # Notify employee and manager
        body = f"""
        A Performance Improvement Plan (PIP) has been created for you.
        
        Duration: {self.duration_weeks} weeks (from {self.start_date} to {self.end_date})
        Review Frequency: {self.review_frequency}
        
        Areas for Improvement:
        {self.improvement_areas}
        
        Objectives:
        {self.objectives}
        
        Please meet with your manager to discuss the plan.
        """
        
        if self.employee_id.user_id:
            self.employee_id.user_id.notify_info(body, title='Performance Improvement Plan Created')

    def action_update_progress(self):
        """Record progress update during PIP period."""
        return {
            'name': 'Update PIP Progress',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.performance.improvement.plan',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_complete_pip(self):
        """Complete PIP and record outcome."""
        if not self.outcome:
            raise ValidationError('Outcome must be selected before completing PIP.')
        
        self.status = 'completed'
        self.message_post(body=f'PIP completed with outcome: {self.outcome}')
        
        # Auto-recommend follow-up action based on outcome
        if self.outcome == 'not_met':
            self.follow_up_action = 'disciplinary'
        elif self.outcome == 'partially_met':
            self.follow_up_action = 'extension'
        elif self.outcome in ('met', 'exceeded'):
            self.follow_up_action = 'continue_employment'
        
        # Notify HR and Manager
        self.manager_id.message_notify(
            body=f'PIP completed for {self.employee_id.name}. Outcome: {self.outcome}',
            subject='Performance Improvement Plan Completed',
            partner_ids=self.manager_id.user_id.partner_id.ids if self.manager_id.user_id else []
        )

    def action_convert_to_disciplinary(self):
        """Convert PIP to formal disciplinary process."""
        self.status = 'converted'
        self.follow_up_action = 'disciplinary'
        self.message_post(body='PIP converted to formal disciplinary process.')

    def action_terminate_pip(self):
        """Terminate PIP and employee."""
        self.status = 'terminated'
        self.follow_up_action = 'termination'
        self.message_post(body='PIP terminated and employee separation initiated.')
