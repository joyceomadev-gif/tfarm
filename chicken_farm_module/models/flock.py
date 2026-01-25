from odoo import models, fields, api, _
from datetime import date

class FarmFlock(models.Model):
    _name = 'taghini.flock'
    _description = 'Broiler Flock (Batch)'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Batch Name', required=True, default='New')
    start_date = fields.Date(string='Stocking Date', required=True, default=fields.Date.context_today)
    
    # Configuration
    pen_model_id = fields.Many2one('taghini.pen', string='Pen (Unit)', required=True, domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    company_id = fields.Many2one('res.company', string='Farm/Branch', related='pen_model_id.company_id', store=True, readonly=True)
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

    harvest_ids = fields.One2many('taghini.harvest', 'flock_id', string='Harvest Records')
    harvest_count = fields.Integer(compute='_compute_harvest_count', string='Harvest Count')

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

    @api.depends('initial_birds', 'log_ids.mortality', 'log_ids.harvested_qty')
    def _compute_current_birds(self):
        for record in self:
            # Sum all mortality and harvest from daily logs
            total_dead = sum(record.log_ids.mapped('mortality'))
            total_harvested = sum(record.log_ids.mapped('harvested_qty'))
            
            # Calculate remaining
            record.current_birds = record.initial_birds - total_dead - total_harvested
            
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

    def action_add_daily_log(self):
        """ Opens the Daily Log Form in a Modal (Pop-up) """
        self.ensure_one()
        return {
            'name': _('Add Daily Log'),
            'type': 'ir.actions.act_window',
            'res_model': 'taghini.daily.log',
            'view_mode': 'form',
            # Force the Master Form View we just created
            'view_id': self.env.ref('chicken_farm_module.view_taghini_log_form').id,
            'target': 'new', # This opens it as a Pop-up/Modal
            'context': {
                'default_flock_id': self.id,
                'default_pen_id': self.pen_id.id,
                'default_date': fields.Date.context_today(self),
                # Optional: Pre-fill Feed Product if Standard is set
                'default_feed_product_id': self.product_id.id if self.product_id else False, 
            }
        }

    @api.depends('harvest_ids')
    def _compute_harvest_count(self):
        for record in self:
            record.harvest_count = len(record.harvest_ids)

    def action_view_harvests(self):
        """ Smart Button Action """
        self.ensure_one()
        return {
            'name': _('Harvest Records'),
            'type': 'ir.actions.act_window',
            'res_model': 'taghini.harvest',
            'view_mode': 'list,form',
            'domain': [('flock_id', '=', self.id)],
            'context': {
                'default_flock_id': self.id,
                'default_pen_id': self.pen_model_id.id if self.pen_model_id else False,
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