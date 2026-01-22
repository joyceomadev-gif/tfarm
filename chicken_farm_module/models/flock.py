from odoo import models, fields, api
from datetime import date

class FarmFlock(models.Model):
    _name = 'taghini.flock'
    _description = 'Broiler Flock (Batch)'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Batch Name', required=True, default='New')
    start_date = fields.Date(string='Stocking Date', required=True, default=fields.Date.context_today)
    
    # Configuration
    pen_id = fields.Many2one('stock.location', string='Pen Location', domain="[('usage', '=', 'internal')]")
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
            record.mortality_rate = (dead / record.initial_birds * 100) if record.initial_birds else 0.0

    @api.depends('initial_birds', 'total_mortality')
    def _compute_current_birds(self):
        for record in self:
            # We will add "Harvested" later
            record.current_birds = record.initial_birds - record.total_mortality