from odoo import models, fields, api
from datetime import datetime


class GoalProgressUpdate(models.Model):
    _name = 'hr.goal.progress.update'
    _description = 'Goal Progress Update'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_updated DESC'

    goal_id = fields.Many2one(
        'hr.performance.goal',
        string='Goal',
        required=True,
        ondelete='cascade'
    )
    cycle_id = fields.Many2one(
        'hr.performance.cycle',
        string='Cycle',
        related='goal_id.cycle_id',
        store=True,
        readonly=True
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        related='goal_id.employee_id',
        store=True,
        readonly=True
    )
    manager_id = fields.Many2one(
        'hr.employee',
        string='Manager',
        related='goal_id.manager_id',
        store=True,
        readonly=True
    )
    
    date_updated = fields.Date(
        string='Update Date',
        required=True,
        default=lambda self: fields.Date.context_today(self),
        tracking=True
    )
    
    progress_percentage = fields.Float(
        string='Progress %',
        required=True,
        tracking=True,
        help='Percentage of goal completed'
    )
    
    achievements = fields.Text(
        string='Achievements',
        tracking=True,
        help='What has been accomplished since last update'
    )
    
    challenges = fields.Text(
        string='Challenges',
        tracking=True,
        help='Obstacles or difficulties faced'
    )
    
    support_required = fields.Text(
        string='Support Required',
        tracking=True,
        help='What support is needed from manager'
    )
    
    evidence_attachment_ids = fields.Many2many(
        'ir.attachment',
        'goal_progress_attachment_rel',
        'progress_id',
        'attachment_id',
        string='Evidence Attachments',
        help='Documents, photos, reports, certificates, etc.'
    )

    @api.constrains('progress_percentage')
    def _check_progress(self):
        for update in self:
            if not (0 <= update.progress_percentage <= 100):
                raise ValidationError('Progress percentage must be between 0 and 100.')

    @api.onchange('progress_percentage')
    def _onchange_progress(self):
        """Update goal's progress when update is created."""
        if self.goal_id and self.progress_percentage > self.goal_id.progress_percentage:
            self.goal_id.progress_percentage = self.progress_percentage
