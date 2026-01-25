from odoo import models, fields, api, _
from odoo.exceptions import UserError

class FarmHarvest(models.Model):
    _name = 'taghini.harvest'
    _description = 'Abattoir / Harvest Batch'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'

    name = fields.Char(string='Harvest Reference', required=True, copy=False, readonly=True, default='New')
    date = fields.Date(string='Harvest Date', default=fields.Date.context_today, required=True)
    company_id = fields.Many2one('res.company', string='Farm/Branch', related='flock_id.company_id', store=True, readonly=True)
    # Link to Farm
    flock_id = fields.Many2one('taghini.flock', string='Source Batch', required=True, domain=[('state', '=', 'active')])
    pen_id = fields.Many2one('taghini.pen', related='flock_id.pen_model_id', string='Source Pen', store=True)

    # --- INPUT METRICS (At the Gate) ---
    birds_received = fields.Integer(string='Birds Received (Head)', help="Number of birds arrived alive at abattoir")
    total_live_weight = fields.Float(string='Total Live Weight (Kg)', help="Total weight of truck/crates")
    
    avg_harvest_weight_g = fields.Float(string='Avg Body Weight (g)', compute='_compute_avg_weight', store=True)

    # --- QUALITY SCORES (The "Look and Feel") ---
    feather_condition = fields.Selection([
        ('excellent', 'Excellent (Clean/Full)'),
        ('good', 'Good'),
        ('fair', 'Fair (Some dirt/patches)'),
        ('poor', 'Poor (Dirty/Bare)')
    ], string='Feather Condition', default='good', tracking=True)
    
    visual_quality = fields.Selection([
        ('premium', 'Premium (Uniform/Healthy)'),
        ('standard', 'Standard'),
        ('irregular', 'Irregular Sizes'),
        ('rejected', 'Many Rejects')
    ], string='Visual Look & Feel', default='standard', tracking=True)
    
    notes = fields.Text(string='Abattoir Notes')

    # --- PERFORMANCE SUMMARY (Auto-Calculated from Log) ---
    total_feed_consumed_kg = fields.Float(string='Total Feed Consumed (Kg)', compute='_compute_performance', store=True)
    total_meds_count = fields.Integer(string='Medication Days', compute='_compute_performance', help="Count of days meds were applied")
    
    # THE GOLDEN METRIC: Feed Conversion Ratio (FCR)
    fcr = fields.Float(string='FCR (Conversion)', compute='_compute_performance', store=True, 
                       help="Feed Conversion Ratio: Kg of Feed needed to produce 1 Kg of Meat. Lower is better.")

    state = fields.Selection([
        ('draft', 'Draft'),
        ('processing', 'Processing'),
        ('done', 'Completed')
    ], string='Status', default='draft', tracking=True)

    move_id = fields.Many2one('stock.move', string='Stock Move', readonly=True)

    # --- COMPUTATIONS ---
    @api.depends('birds_received', 'total_live_weight')
    def _compute_avg_weight(self):
        for record in self:
            if record.birds_received > 0:
                # Result in Grams
                record.avg_harvest_weight_g = (record.total_live_weight * 1000) / record.birds_received
            else:
                record.avg_harvest_weight_g = 0.0

    @api.depends('flock_id', 'total_live_weight')
    def _compute_performance(self):
        for record in self:
            if record.flock_id:
                # 1. Sum Feed from Logs (Stored in Grams, convert to Kg)
                total_feed_g = sum(record.flock_id.log_ids.mapped('feed_consumed_g'))
                record.total_feed_consumed_kg = total_feed_g / 1000.0
                
                # 2. Count Meds
                med_logs = record.flock_id.log_ids.filtered(lambda l: l.medication_name or l.vaccine_name)
                record.total_meds_count = len(med_logs)

                # 3. Calculate FCR (Total Feed Kg / Total Live Weight Kg)
                if record.total_live_weight > 0:
                    record.fcr = record.total_feed_consumed_kg / record.total_live_weight
                else:
                    record.fcr = 0.0
            else:
                record.total_feed_consumed_kg = 0.0
                record.total_meds_count = 0
                record.fcr = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        """ Overridden to generate Sequence Number for every record in the list """
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('taghini.harvest') or 'New'
        return super(FarmHarvest, self).create(vals_list)

    def action_confirm_harvest(self):
        """ 
        1. Creates Internal Transfer.
        2. UPDATES existing Daily Log OR Creates new one.
        3. Updates Flock Status.
        """
        self.ensure_one()
        
        # ... (Keep your existing Validation Checks here) ...
        if not self.flock_id.product_id:
            raise UserError(_("The Flock does not have a Product defined."))

        # 1. CREATE STOCK MOVE (Keep existing logic)
        move_vals = {
            'product_id': self.flock_id.product_id.id,
            'product_uom_qty': self.birds_received,
            'product_uom': self.flock_id.product_id.uom_id.id,
            'location_id': self.pen_id.location_id.id,
            'location_dest_id': self.pen_id.abattoir_location_id.id,
            'date': self.date,
            'company_id': self.company_id.id,
            'origin': self.name,
        }
        move = self.env['stock.move'].create(move_vals)
        move._action_confirm()
        move._action_assign()
        move.quantity = self.birds_received
        move._action_done()
        self.move_id = move.id

        # 2. UPDATE OR CREATE DAILY LOG (The Fix)
        # Search for an existing log for this Flock + Date
        existing_log = self.env['taghini.daily.log'].search([
            ('flock_id', '=', self.flock_id.id),
            ('date', '=', self.date)
        ], limit=1)

        if existing_log:
            # UPDATE existing record
            existing_log.write({
                'harvested_qty': existing_log.harvested_qty + self.birds_received,
                'harvested_weight': existing_log.harvested_weight + self.total_live_weight,
                'state': 'done', # Ensure it's posted
                # Optional: Append to remarks so we know a harvest happened
                'remarks': f"{existing_log.remarks or ''}\nHarvest: {self.name} ({self.birds_received} birds)"
            })
        else:
            # CREATE new record
            self.env['taghini.daily.log'].create({
                'flock_id': self.flock_id.id,
                'date': self.date,
                'harvested_qty': self.birds_received,
                'harvested_weight': self.total_live_weight,
                'state': 'done',
                'remarks': f"Harvest Reference: {self.name}"
            })

        # 3. UPDATE FLOCK STATUS (Keep existing logic)
        self.state = 'done'
        self.flock_id._compute_current_birds() 
        if self.flock_id.current_birds <= 0:
             self.flock_id.write({'state': 'closed'})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Harvest Confirmed'),
                'message': f'{self.birds_received} birds transferred to Abattoir.',
                'type': 'success',
                'sticky': False,
            }
        }