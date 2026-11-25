from odoo import models, fields, api
from odoo.exceptions import ValidationError


class AppealRecord(models.Model):
    _name = 'hr.appeal.record'
    _description = 'Employee Appeal / Grievance'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']

    def _compute_access_url(self):
        super()._compute_access_url()
        for appeal in self:
            appeal.access_url = f'/my/performance/appeals/{appeal.id}'

    scorecard_id = fields.Many2one(
        'hr.final.scorecard',
        string='Final Scorecard',
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
    
    appeal_reason = fields.Text(
        string='Reason for Appeal',
        required=True,
        tracking=True,
        help='Why the employee is disputing the appraisal'
    )
    
    appeal_date = fields.Date(
        string='Appeal Date',
        default=lambda self: fields.Date.context_today(self),
        tracking=True
    )
    
    supporting_evidence = fields.Text(
        string='Supporting Evidence',
        tracking=True,
        help='Evidence or documentation to support the appeal'
    )
    
    evidence_attachment_ids = fields.Many2many(
        'ir.attachment',
        'appeal_attachment_rel',
        'appeal_id',
        'attachment_id',
        string='Attachments'
    )
    
    # HR Review
    hr_reviewer_id = fields.Many2one(
        'res.users',
        string='HR Reviewer',
        tracking=True
    )
    
    review_date = fields.Date(
        string='Review Date',
        tracking=True
    )
    
    review_notes = fields.Text(
        string='HR Review Notes',
        tracking=True
    )
    
    # Resolution
    appeal_status = fields.Selection([
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('resolved', 'Resolved'),
        ('escalated', 'Escalated to Director'),
    ], string='Appeal Status', default='submitted', tracking=True)
    
    resolution = fields.Selection([
        ('sustained', 'Sustained (Appeal Upheld)'),
        ('dismissed', 'Dismissed (Score Stands)'),
        ('partial', 'Partially Upheld'),
    ], string='Resolution', tracking=True)
    
    resolution_notes = fields.Text(
        string='Resolution Notes',
        tracking=True
    )
    
    adjusted_final_score = fields.Float(
        string='Adjusted Final Score',
        tracking=True,
        help='If appeal is upheld, adjusted score can be recorded here'
    )

    def action_submit_to_hr(self):
        """Formally submit appeal to HR."""
        if self.appeal_status != 'submitted':
            raise ValidationError('Only submitted appeals can be formally processed.')
        
        self.appeal_status = 'under_review'
        self.message_post(body='Appeal submitted to HR for review.')

    def action_mark_resolved(self):
        """Mark appeal as resolved."""
        if not self.resolution:
            raise ValidationError('Resolution must be selected before closing.')
        
        self.appeal_status = 'resolved'
        self.message_post(body=f'Appeal resolved: {self.resolution}')
        
        # Update scorecard if sustained
        if self.resolution in ('sustained', 'partial') and self.adjusted_final_score:
            self.scorecard_id.final_score = self.adjusted_final_score
            self.message_post(body='Scorecard final score adjusted.')

    def action_escalate(self):
        """Escalate appeal to director/senior management."""
        if self.appeal_status != 'under_review':
            raise ValidationError('Only appeals under review can be escalated.')
        
        self.appeal_status = 'escalated'
        self.message_post(body='Appeal escalated to senior management for final review.')

    def action_view_scorecard(self):
        """Quick navigation to related scorecard."""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Performance Scorecard',
            'res_model': 'hr.final.scorecard',
            'res_id': self.scorecard_id.id,
            'view_mode': 'form',
        }
