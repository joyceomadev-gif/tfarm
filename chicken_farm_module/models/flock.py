from odoo import models, fields, api, _
from datetime import date

class FarmFlock(models.Model):
    _name = 'taghini.flock'
    _description = 'Broiler Flock (Batch)'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Batch Name', required=True, default='New')
    start_date = fields.Date(string='Stocking Date', required=True, default=fields.Date.context_today)
    
    # Configuration
    pen_model_id = fields.Many2one('taghini.pen', string='Pen (Unit)', required=True)
    
    # KEEP EXISTING: Physical Location (Auto-filled)
    pen_id = fields.Many2one('stock.location', string='Location', related='pen_model_id.location_id', store=True, readonly=True)
    breed = fields.Char(string='Breed', default='Ross 308')
    
    # NEW FIELD: Which product is this?
    product_id = fields.Many2one('product.product', string='Bird Variant', required=True)
    # Inventory Data
    initial_birds = fields.Integer(string='Initial Stock', required=True, help="Number of birds at day 0")
    current_birds = fields.Integer(string='Current Birds', compute='_compute_current_birds', store=True)
    
    # Performance Metrics (Computed from Logs)
    total_mortality = fields.Integer(string='Total Mortality', compute='_compute_metrics')
    mortality_rate = fields.Float(string='Mortality %', compute='_compute_metrics')
    current_age = fields.Integer(string='Current Age (Days)', compute='_compute_age')
    
    # Relation to Logs
    log_ids = fields.One2many('taghini.daily.log', 'flock_id', string='Daily Logs')
    standard_id = fields.Many2one('taghini.farm.standard', string='Growth Profile', required=True, help="Defines feed types and expected consumption")

    state = fields.Selection([
        ('draft', 'Draft'),         # Planned, no birds yet
        ('active', 'In Progress'),  # Birds are in the pen
        ('closed', 'Closed'),       # Harvested / Cycle finished
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', required=True, tracking=True)

    @api.depends('start_date')
    def _compute_age(self):
        for record in self:
            if record.start_date:
                delta = date.today() - record.start_date
                record.current_age = delta.days
            else:
                record.current_age = 0

    @api.depends('log_ids.mortality')
    def _compute_metrics(self):
        for record in self:
            dead = sum(record.log_ids.mapped('mortality'))
            record.total_mortality = dead
            record.mortality_rate = (record.total_mortality / record.initial_birds) if record.initial_birds else 0.0

    @api.depends('initial_birds', 'total_mortality')
    def _compute_current_birds(self):
        for record in self:
            # We will add "Harvested" later
            record.current_birds = record.initial_birds - record.total_mortality
            
    def action_escalate_issue(self):
        """ Notify Vet and Manager about issues """
        self.ensure_one()
        if not self.pen_model_id.vet_id or not self.pen_model_id.manager_id:
            raise UserError(_("Please assign a Vet and Manager to the Pen before escalating."))

        # 1. Post the Message (Removed 'priority' to fix crash)
        partners = [self.pen_model_id.vet_id.partner_id.id, self.pen_model_id.manager_id.partner_id.id]
        self.message_post(
            body=_("<b>URGENT:</b> High mortality or health issue reported in %s. Please inspect immediately.") % self.name,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
            partner_ids=partners
        )

        # 2. Schedule an Activity (To-Do) for them
        self.activity_schedule(
            'mail.mail_activity_data_todo',
            user_id=self.pen_model_id.vet_id.id,
            note=f"Health Inspection Required for {self.name}",
            summary="Urgent Inspection"
        )
        
        return {
            'effect': {
                'fadeout': 'slow',
                'message': 'Escalation Sent to Dr. %s' % self.pen_model_id.vet_id.name,
                'type': 'rainbow_man',
                
            }
        }
    # 2. ACTION BUTTONS
    def action_start_batch(self):
        """ Move from Draft to Active. Lock critical fields. """
        for record in self:
            if not record.pen_model_id:
                raise UserError(_("You must assign a Pen before starting the batch."))
            record.state = 'active'

    def action_close_batch(self):
        """ Mark as finished. Usually called automatically by Harvest, but manual is allowed. """
        self.write({'state': 'closed'})

    def action_cancel_batch(self):
        """ Cancel the plan. """
        self.write({'state': 'cancelled'})

    def action_set_draft(self):
        """ Reset for corrections. """
        self.write({'state': 'draft'})