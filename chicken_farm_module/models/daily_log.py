from odoo import models, fields, api, _
from odoo.exceptions import UserError

class FarmDailyLog(models.Model):
    _name = 'taghini.daily.log'
    _description = 'Daily Farm Log'
    _order = 'date desc'

    flock_id = fields.Many2one('taghini.flock', string='Flock/Batch', required=True, ondelete='cascade')
    pen_id = fields.Many2one('stock.location', related='flock_id.pen_id', store=True, string="Location", readonly=True)
    standard_id = fields.Many2one('taghini.farm.standard', related='flock_id.standard_id', store=True)
    company_id = fields.Many2one('res.company', string='Farm/Branch', related='flock_id.company_id', store=True, readonly=True)
    date = fields.Date(string='Date', default=fields.Date.context_today, required=True)
    age_day = fields.Integer(string='Age', compute='_compute_age_day', store=True)
    state = fields.Selection([('draft', 'Draft'), ('done', 'Posted')], default='draft', string='Status')

    # --- 1. MORTALITY & BIRDS ---
    birds_count = fields.Integer(string='Start Birds', compute='_compute_daily_metrics', store=True, help="Birds alive at start of day")
    mortality = fields.Integer(string='Mortality', default=0)
    scrap_id = fields.Many2one('stock.scrap', string='Related Scrap', readonly=True)
    
    # NEW: Mortality Metrics
    daily_mortality_percent = fields.Float(string='Daily Mort %', compute='_compute_daily_metrics', store=True, digits=(16, 2))
    cumm_mortality = fields.Integer(string='Cumm. Mortality', compute='_compute_cumulative_stats', store=True)
    cumm_mortality_percent = fields.Float(string='Cumm. Mort %', compute='_compute_cumulative_stats', store=True, digits=(16, 2))

    # --- 2. FEED SECTION ---
    feed_product_id = fields.Many2one('product.product',compute='_compute_expectations', string='Feed Type')
    feed_consumed_bags = fields.Integer(string='Bags')
    feed_consumed_g = fields.Float(string='Consumed (g)', compute='_compute_feed_g', store=True)
    move_id = fields.Many2one('stock.move', string='Feed Usage', readonly=True)
    
    # NEW: Feed Metrics
    feed_per_bird_g = fields.Float(string='Feed/Bird (g)', compute='_compute_daily_metrics', store=True)
    expected_feed_g = fields.Float(string='Exp. Feed (g)', compute='_compute_expectations', store=True)
    variance_feed_g = fields.Float(string='Feed Var (g)', compute='_compute_expectations', store=True)
    
    # NEW: Cumulative Feed
    cumm_actual_feed_g = fields.Float(string='Cumm. Actual Feed', compute='_compute_cumulative_stats', store=True)
    cumm_expected_feed_g = fields.Float(string='Cumm. Exp. Feed', compute='_compute_cumulative_stats', store=True)

    # --- 3. WEIGHT & BIOMETRICS ---
    actual_avg_weight = fields.Float(string='Actual Avg Wgt (g)')
    
    # NEW: Weight Metrics
    expected_avg_weight = fields.Float(string='Exp. Avg Wgt (g)', compute='_compute_expectations', store=True)
    variance_weight = fields.Float(string='Wgt Variance', compute='_compute_expectations', store=True)
    
    light_hours = fields.Float(string='Light (Hrs)')
    light_period = fields.Char(string='Light Period')

    # --- 4. OTHER & HARVEST ---
    water_consumed = fields.Float(string='Water (L)')
    medication_name = fields.Char(string='Medication')
    vaccine_name = fields.Char(string='Vaccine')
    remarks = fields.Text(string='Remarks')
    harvested_qty = fields.Integer(string='Harvested Qty')
    harvested_weight = fields.Float(string='Harvested Wgt')
    # --- COMPUTES ---
    @api.depends('flock_id.start_date', 'date')
    def _compute_age_day(self):
        for record in self:
            if record.flock_id.start_date and record.date:
                record.age_day = (record.date - record.flock_id.start_date).days
            else:
                record.age_day = 0

    @api.onchange('date', 'flock_id')
    def _on_date_change_set_standard(self):
        if self.flock_id and self.flock_id.standard_id and self.date:
            delta = self.date - self.flock_id.start_date
            current_age = delta.days
            rule = self.env['taghini.farm.standard.line'].search([
                ('standard_id', '=', self.flock_id.standard_id.id),
                ('age_min', '<=', current_age),
                ('age_max', '>=', current_age)
            ], limit=1)
            if rule and not self.feed_product_id:
                self.feed_product_id = rule.product_id

    @api.depends('feed_consumed_bags')
    def _compute_feed_g(self):
        for record in self:
            record.feed_consumed_g = record.feed_consumed_bags * 25000.0

    @api.depends('flock_id', 'date', 'standard_id', 'age_day', 'feed_consumed_g', 'actual_avg_weight')
    def _compute_expectations(self):
        """ Calculates expected values based on the Standard Profile """
        for record in self:
            exp_feed = 0.0
            exp_weight = 0.0
            exp_product = False
            
            if record.standard_id:
                # Find matching rule
                rule = self.env['taghini.farm.standard.line'].search([
                    ('standard_id', '=', record.standard_id.id),
                    ('age_min', '<=', record.age_day),
                    ('age_max', '>=', record.age_day)
                ], limit=1)
                
                if rule:
                    birds = record.birds_count or record.flock_id.initial_birds
                    exp_feed = birds * rule.expected_feed_g
                    exp_weight = rule.expected_weight_g
                    exp_product = rule.product_id

            record.expected_feed_g = exp_feed
            record.variance_feed_g = record.feed_consumed_g - exp_feed
            record.feed_product_id = exp_product
            record.expected_avg_weight = exp_weight
            record.variance_weight = record.actual_avg_weight - exp_weight if record.actual_avg_weight else 0.0

    @api.depends('flock_id.log_ids.mortality', 'flock_id.log_ids.feed_consumed_g', 
                 'flock_id.log_ids.expected_feed_g', 'date', 'flock_id.initial_birds')
    def _compute_cumulative_stats(self):
        """ Heavy computation: Sums up previous days for cumulative stats """
        for record in self:
            if not record.flock_id:
                record.cumm_mortality = 0
                record.cumm_mortality_percent = 0.0
                record.cumm_actual_feed_g = 0.0
                record.cumm_expected_feed_g = 0.0
                continue

            # Fetch all logs for this flock up to this date
            # We use 'search' to handle re-computation correctly
            previous_logs = self.search([
                ('flock_id', '=', record.flock_id.id),
                ('date', '<=', record.date) # Include today
            ])
            
            # Cumulative Sums
            record.cumm_mortality = sum(previous_logs.mapped('mortality'))
            record.cumm_actual_feed_g = sum(previous_logs.mapped('feed_consumed_g'))
            record.cumm_expected_feed_g = sum(previous_logs.mapped('expected_feed_g'))

            # Percentage
            initial = record.flock_id.initial_birds or 1
            record.cumm_mortality_percent = (record.cumm_mortality / initial)

    @api.depends('flock_id.log_ids.mortality', 'flock_id.log_ids.harvested_qty', 
                 'date', 'flock_id.initial_birds', 'mortality', 'feed_consumed_g')
    def _compute_daily_metrics(self):
        for record in self:
            # 1. Calculate Birds Count (Start of Day)
            # Sum mortality/harvest BEFORE today
            previous_logs = self.search([
                ('flock_id', '=', record.flock_id.id),
                ('date', '<', record.date)
            ])
            gone = sum(previous_logs.mapped('mortality')) + sum(previous_logs.mapped('harvested_qty'))
            current_birds = record.flock_id.initial_birds - gone
            record.birds_count = current_birds

            # 2. Daily Mortality %
            if current_birds > 0:
                record.daily_mortality_percent = (record.mortality / current_birds)
                record.feed_per_bird_g = record.feed_consumed_g / current_birds
            else:
                record.daily_mortality_percent = 0.0
                record.feed_per_bird_g = 0.0

    # --- THE FIXED ACTION ---
    def action_post_log(self):
        """ This method is called by the Button. It performs validation and creates moves. """
        for record in self:
            if record.state == 'done':
                continue # Skip already posted

            # 1. Mortality Logic
            if record.mortality > 0 and not record.scrap_id:
                if not record.flock_id.pen_id:
                    raise UserError(_("Please set a Pen Location on the Flock."))
                
                scrap = self.env['stock.scrap'].create({
                    'product_id': record.flock_id.product_id.id,
                    'scrap_qty': record.mortality,
                    'location_id': record.flock_id.pen_id.id,
                    'origin': f"Mortality {record.flock_id.name} - Day {record.age_day}",
                    'state': 'done'
                })
                scrap.action_validate()
                record.scrap_id = scrap.id

            # 2. Feed Logic
            if record.feed_consumed_g > 0 and record.feed_product_id and not record.move_id:
                


                warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
                production_location = self.env['stock.location'].search([
                    ('usage', '=', 'production'),
                    ('company_id', '=', self.env.company.id)
                ], limit=1)


                move = self.env['stock.move'].create({
                    'product_id': record.feed_product_id.id,
                    'product_uom_qty': record.feed_consumed_g,
                    'product_uom': self.feed_product_id.uom_id.id,
                    'location_id': warehouse.lot_stock_id.id,
                    'location_dest_id': production_location.id,
                    'origin': f"Feed {record.flock_id.name} - Day {record.age_day}",
                    'state': 'draft',
                })
                
                move._action_confirm()
                move._action_assign()
                
                # Force Done Quantity
                for line in move.move_line_ids:
                    line.quantity = line.quantity_product_uom
                
                if not move.move_line_ids:
                    # Force creation if stock is missing (Negative Inventory)
                    self.env['stock.move.line'].create({
                        'move_id': move.id,
                        'product_id': move.product_id.id,
                        'product_uom_id': move.product_uom.id,
                        'location_id': move.location_id.id,
                        'location_dest_id': move.location_dest_id.id,
                        'quantity': record.feed_consumed_g,
                    })
                
                move.picked = True
                move._action_done()
                record.move_id = move.id
            
            # Lock the record
            record.state = 'done'
    def unlink(self):
        """ Prevent deleting posted logs to protect data integrity """
        for record in self:
            if record.state == 'done':
                raise UserError(_("You cannot delete a Posted log line because it has already created Stock Moves.\n\nTo correct this, please create a new line with negative values or consult your manager."))
        return super(FarmDailyLog, self).unlink()