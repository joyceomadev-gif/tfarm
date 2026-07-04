from odoo import models, fields, api


class CoachingSession(models.Model):
    _name = 'hr.coaching.session'
    _description = 'Coaching & Review Meeting'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'meeting_date DESC'

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
    supervisor_id = fields.Many2one(
        'hr.employee',
        string='Supervisor',
        required=True,
        domain="[('id', '!=', employee_id)]",
        tracking=True
    )
    
    meeting_date = fields.Date(
        string='Meeting Date',
        required=True,
        tracking=True
    )
    meeting_duration = fields.Float(
        string='Duration (Hours)',
        tracking=True
    )
    
    objectives_discussed = fields.Text(
        string='Objectives Discussed',
        required=True,
        tracking=True
    )
    
    employee_feedback = fields.Text(
        string='Employee Feedback',
        tracking=True,
        help='What the employee said during the session'
    )
    
    supervisor_feedback = fields.Text(
        string='Supervisor Feedback',
        tracking=True,
        help='Feedback from supervisor to employee'
    )
    
    action_items = fields.Text(
        string='Action Items',
        tracking=True,
        help='Agreed-upon actions from the session'
    )
    
    follow_up_date = fields.Date(
        string='Follow-Up Date',
        tracking=True,
        help='Scheduled date for next coaching session'
    )
    
    session_notes = fields.Text(
        string='Session Notes',
        tracking=True
    )
    
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'coaching_attachment_rel',
        'session_id',
        'attachment_id',
        string='Attachments',
        help='Meeting minutes, improvement plans, etc.'
    )
    
    status = fields.Selection([
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='scheduled', tracking=True)

    def action_mark_completed(self):
        """Mark coaching session as completed."""
        if self.status != 'scheduled':
            raise ValidationError('Only scheduled sessions can be marked as completed.')
        
        self.status = 'completed'
        self.message_post(body='Coaching session completed.')
        
        if self.supervisor_id.user_id:
            self.supervisor_id.user_id.notify_info(
                'Coaching session marked as completed. Consider scheduling a follow-up.',
                title='Coaching Session Completed'
            )

    def action_cancel_session(self):
        """Cancel the coaching session."""
        if self.status == 'completed':
            raise ValidationError('Completed sessions cannot be cancelled.')
        
        self.status = 'cancelled'
        self.message_post(body='Coaching session cancelled.')

    def action_schedule_follow_up(self):
        """Quick action to create follow-up session."""
        return {
            'name': 'Schedule Follow-Up Session',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.coaching.session',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_cycle_id': self.cycle_id.id,
                'default_employee_id': self.employee_id.id,
                'default_supervisor_id': self.supervisor_id.id,
                'default_meeting_date': self.follow_up_date,
            }
        }
