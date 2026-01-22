from odoo import models, fields, api, _
from odoo.exceptions import UserError

class FarmDailyLog(models.Model):
    _name = 'taghini.daily.log'
    _description = 'Daily Farm Log'
    _order = 'date desc'

    flock_id = fields.Many2one('taghini.flock', string='Flock/Batch', required=True, ondelete='cascade')
    date = fields.Date(string='Date', default=fields.Date.context_today, required=True)
    age_day = fields.Integer(string='Age', compute='_compute_age_day', store=True)

    # --- Mortality Section ---
    mortality = fields.Integer(string='Mortality', default=0)
    # We store the created scrap ID so we don't create it twice
    scrap_id = fields.Many2one('stock.scrap', string='Related Scrap', readonly=True)

    # --- Feed Section ---
    feed_product_id = fields.Many2one('product.product', string='Feed Type')
    feed_consumed_bags = fields.Integer(string='Feed (Bags)', default=0)
    feed_consumed_kg = fields.Float(string='Feed (Kg)', compute='_compute_feed_kg', store=True)
    
    # We store the stock move ID
    move_id = fields.Many2one('stock.move', string='Feed Usage', readonly=True)

    # --- Other Data ---
    water_consumed = fields.Float(string='Water (L)')
    body_weight = fields.Float(string='Avg Weight (g)')
    remarks = fields.Text(string='Remarks')

    @api.depends('flock_id.start_date', 'date')
    def _compute_age_day(self):
        for record in self:
            if record.flock_id.start_date and record.date:
                record.age_day = (record.date - record.flock_id.start_date).days
            else:
                record.age_day = 0

    @api.depends('feed_consumed_bags')
    def _compute_feed_kg(self):
        for record in self:
            # Hardcoded 25kg per bag for now. Better to add 'weight' on product later.
            record.feed_consumed_kg = record.feed_consumed_bags * 25.0

    # --- AUTOMATION LOGIC ---
    def write(self, vals):
        res = super(FarmDailyLog, self).write(vals)
        for record in self:
            record._process_stock_updates()
        return res

    @api.model
    def create(self, vals):
        record = super(FarmDailyLog, self).create(vals)
        record._process_stock_updates()
        return record

    def _process_stock_updates(self):
        """ Automatically creates Stock Moves when data is entered """
        self.ensure_one()

        # 1. HANDLE MORTALITY (Create Scrap)
        if self.mortality > 0 and not self.scrap_id:
            if not self.flock_id.pen_id:
                raise UserError(_("Please set a Pen Location on the Flock before recording mortality."))

            scrap = self.env['stock.scrap'].create({
                'product_id': self.flock_id.product_id.id,
                'scrap_qty': self.mortality,
                'location_id': self.flock_id.pen_id.id,
                'origin': f"Mortality {self.flock_id.name} - Day {self.age_day}",
                'state': 'done'
            })
            scrap.action_validate()
            self.scrap_id = scrap.id

        # 2. HANDLE FEED (Create Consumption Move)
        if self.feed_consumed_kg > 0 and self.feed_product_id and not self.move_id:
            
            # Dynamic search for Production Location
            production_location = self.env['stock.location'].search([
                ('usage', '=', 'production'),
                ('company_id', '=', self.env.company.id)
            ], limit=1)
            
            # Dynamic search for Stock Location
            warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
            source_location = warehouse.lot_stock_id
            
            if not production_location or not source_location:
                raise UserError(_("Could not find a valid Stock or Production location. Please check your Warehouse configuration."))

            # --- CORRECTION: REMOVED 'name' FIELD ---
            move = self.env['stock.move'].create({
                # 'name': ... (Removed because Odoo 19 considers it invalid)
                'product_id': self.feed_product_id.id,
                'product_uom_qty': self.feed_consumed_kg,
                'product_uom': self.feed_product_id.uom_id.id,
                'location_id': source_location.id,
                'location_dest_id': production_location.id,
                # Optional: Add origin to track where this move came from
                'origin': f"Feed {self.flock_id.name} - Day {self.age_day}",
            })
            move._action_confirm()
            move._action_assign()
            move._action_done()
            self.move_id = move.id