from odoo import models, fields, api
from odoo.exceptions import ValidationError


class EvaluatorAssignment(models.Model):
    _name = 'hr.evaluator.assignment'
    _description = 'Evaluator Assignment per Employee'
    _inherit = ['mail.thread', 'mail.activity.mixin']

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
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        related='employee_id.department_id',
        store=True,
        readonly=True
    )
    job_title_id = fields.Many2one(
        'hr.job',
        string='Job Title',
        related='employee_id.job_id',
        store=True,
        readonly=True
    )
    
    # Technical Evaluators
    line_manager_id = fields.Many2one(
        'hr.employee',
        string='Line Manager',
        required=True,
        domain="[('id', '!=', employee_id)]",
        tracking=True
    )
    hod_id = fields.Many2one(
        'hr.employee',
        string='Head of Department (HOD)',
        domain="[('id', '!=', employee_id)]",
        tracking=True
    )
    
    # Behavioral Evaluators (Peers)
    peer_1_id = fields.Many2one(
        'hr.employee',
        string='Peer 1',
        domain="[('id', '!=', employee_id)]",
        tracking=True
    )
    peer_2_id = fields.Many2one(
        'hr.employee',
        string='Peer 2',
        domain="[('id', '!=', employee_id)]",
        tracking=True
    )
    peer_3_id = fields.Many2one(
        'hr.employee',
        string='Peer 3',
        domain="[('id', '!=', employee_id)]",
        tracking=True
    )
    
    # Subordinate Evaluators
    subordinate_1_id = fields.Many2one(
        'hr.employee',
        string='Subordinate 1',
        domain="[('id', '!=', employee_id), ('parent_id', '=', employee_id)]",
        tracking=True
    )
    subordinate_2_id = fields.Many2one(
        'hr.employee',
        string='Subordinate 2',
        domain="[('id', '!=', employee_id), ('parent_id', '=', employee_id)]",
        tracking=True
    )
    
    # Additional Evaluators
    internal_customer_id = fields.Many2one(
        'hr.employee',
        string='Internal Customer',
        domain="[('id', '!=', employee_id)]",
        tracking=True
    )
    external_customer_id = fields.Char(
        string='External Customer (Name)',
        tracking=True,
        help='Name of external customer (if applicable)'
    )
    
    status = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
    ], string='Status', default='draft', tracking=True)
    
    notes = fields.Text(string='Notes', tracking=True)

    _sql_constraints = [
        (
            'unique_assignment',
            'UNIQUE(cycle_id, employee_id)',
            'Each employee can only be assigned once per cycle.'
        )
    ]

    @api.constrains('line_manager_id', 'employee_id')
    def _check_evaluators(self):
        for assignment in self:
            if assignment.line_manager_id == assignment.employee_id:
                raise ValidationError('Line Manager cannot be the same as the employee.')

    def action_submit_assignment(self):
        """Submit evaluator assignment for HR approval."""
        if not self.line_manager_id:
            raise ValidationError('Line Manager is required.')
        
        self.status = 'submitted'
        self.message_post(body='Evaluator assignment submitted for HR approval.')

    def action_approve_assignment(self):
        """HR approves the assignment and opens goal setting."""
        if self.status != 'submitted':
            raise ValidationError('Only submitted assignments can be approved.')
        
        self.status = 'approved'
        self.message_post(body='Evaluator assignment approved. Goal setting opens.')
        
        # Notify employee
        if self.employee_id.user_id:
            self.employee_id.user_id.notify_info(
                'Evaluators have been assigned for your appraisal. Please set your goals.',
                title='Appraisal: Goal Setting Started'
            )
