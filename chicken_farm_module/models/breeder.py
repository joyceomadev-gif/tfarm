from odoo import api, fields, models, _
from odoo.exceptions import UserError


class BreederBatch(models.Model):
    _name = 'taghini.breeder.batch'
    _description = 'Breeder Stock Batch'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'

    name = fields.Char(string='Batch Reference', required=True, copy=False, readonly=True, default='New')
    date = fields.Date(string='Received Date', default=fields.Date.context_today, required=True)
    company_id = fields.Many2one('res.company', string='Farm / Branch', default=lambda self: self.env.company, required=True)

    source_type = fields.Selection([
        ('hatchery', 'Hatchery'),
        ('farm', 'Own Farm'),
    ], string='Source Type', default='hatchery', required=True, tracking=True)
    source_partner_id = fields.Many2one('res.partner', string='Source Hatchery / Farm', required=True)
    source_reference = fields.Char(string='Source Reference / Invoice')

    bird_variant_id = fields.Many2one(
        'product.template',
        string='Bird Variant',
        required=True,
        domain="[('bird_variant', '=', True)]",
        tracking=True,
    )
    standard_id = fields.Many2one('taghini.farm.standard', string='Growth Profile', required=True)

    female_order_qty = fields.Integer(string='Ordered Female DOCs', required=True, tracking=True)
    male_order_qty = fields.Integer(string='Ordered Male DOCs', compute='_compute_order_qty', store=True)
    gift_total_qty = fields.Integer(string='Gift Qty', compute='_compute_gift_qty', store=True)
    gift_male_qty = fields.Integer(string='Gift Male Qty')
    gift_female_qty = fields.Integer(string='Gift Female Qty')

    shipped_male_qty = fields.Integer(string='Shipped Male Qty', compute='_compute_shipped_qty', store=True)
    shipped_female_qty = fields.Integer(string='Shipped Female Qty', compute='_compute_shipped_qty', store=True)

    transit_male_mortality = fields.Integer(string='In-Transit Male Mortality')
    transit_female_mortality = fields.Integer(string='In-Transit Female Mortality')
    premise_male_mortality = fields.Integer(string='On-Premise Male Mortality')
    premise_female_mortality = fields.Integer(string='On-Premise Female Mortality')

    stocked_male_qty = fields.Integer(string='Final Stocked Male Qty', compute='_compute_stocked_qty', store=True)
    stocked_female_qty = fields.Integer(string='Final Stocked Female Qty', compute='_compute_stocked_qty', store=True)
    stocked_total_qty = fields.Integer(string='Final Day-One Qty', compute='_compute_stocked_qty', store=True)

    male_section_qty = fields.Integer(string='Male Section Qty')
    female_section_qty = fields.Integer(string='Female Section Qty')
    introduced_male_qty = fields.Integer(string='Introduced Male Qty')
    introduced_female_qty = fields.Integer(string='Introduced Female Qty')

    egg_production_qty = fields.Integer(string='Egg Production Qty')
    current_state_note = fields.Char(string='Current Stage Note')

    log_ids = fields.One2many('taghini.breeder.daily.log', 'batch_id', string='Daily Logs')
    log_count = fields.Integer(compute='_compute_log_count', string='Log Count')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('received', 'Received'),
        ('sorted', 'Sorted'),
        ('mating', 'Mating / Introduced'),
        ('laying', 'Laying'),
        ('harvested', 'Harvested / Sent to Abattoir'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', required=True, tracking=True)

    @api.depends('female_order_qty')
    def _compute_order_qty(self):
        for record in self:
            record.male_order_qty = int(round((record.female_order_qty or 0) * 0.12))

    @api.depends('male_order_qty', 'female_order_qty', 'gift_male_qty', 'gift_female_qty')
    def _compute_shipped_qty(self):
        for record in self:
            record.shipped_male_qty = (record.male_order_qty or 0) + (record.gift_male_qty or 0)
            record.shipped_female_qty = (record.female_order_qty or 0) + (record.gift_female_qty or 0)

    @api.depends('gift_male_qty', 'gift_female_qty')
    def _compute_gift_qty(self):
        for record in self:
            record.gift_total_qty = (record.gift_male_qty or 0) + (record.gift_female_qty or 0)

    @api.depends(
        'shipped_male_qty', 'shipped_female_qty',
        'transit_male_mortality', 'transit_female_mortality',
        'premise_male_mortality', 'premise_female_mortality',
    )
    def _compute_stocked_qty(self):
        for record in self:
            male_total = (record.shipped_male_qty or 0) - (record.transit_male_mortality or 0) - (record.premise_male_mortality or 0)
            female_total = (record.shipped_female_qty or 0) - (record.transit_female_mortality or 0) - (record.premise_female_mortality or 0)
            record.stocked_male_qty = max(male_total, 0)
            record.stocked_female_qty = max(female_total, 0)
            record.stocked_total_qty = record.stocked_male_qty + record.stocked_female_qty

    @api.depends('log_ids')
    def _compute_log_count(self):
        for record in self:
            record.log_count = len(record.log_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('taghini.breeder.batch') or 'New'
        return super().create(vals_list)

    def action_mark_received(self):
        self.write({'state': 'received'})

    def action_mark_sorted(self):
        self.write({'state': 'sorted'})

    def action_mark_mating(self):
        self.write({'state': 'mating'})

    def action_mark_laying(self):
        self.write({'state': 'laying'})

    def action_mark_harvested(self):
        self.write({'state': 'harvested'})

    def action_close_batch(self):
        self.write({'state': 'closed'})

    def action_cancel_batch(self):
        self.write({'state': 'cancelled'})


class BreederDailyLog(models.Model):
    _name = 'taghini.breeder.daily.log'
    _description = 'Breeder Daily Log'
    _order = 'date desc'

    batch_id = fields.Many2one('taghini.breeder.batch', string='Breeder Batch', required=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', string='Farm / Branch', related='batch_id.company_id', store=True, readonly=True)
    date = fields.Date(string='Date', default=fields.Date.context_today, required=True)
    activity_type = fields.Selection([
        ('receipt', 'Store Receipt'),
        ('sorting', 'Sorting / Separation'),
        ('mating', 'Male Introduction'),
        ('laying', 'Laying'),
        ('health', 'Health / Vet'),
        ('harvest', 'Harvest / Transfer'),
        ('general', 'General Farm Activity'),
    ], string='Activity Type', default='general', required=True)

    male_mortality_transit = fields.Integer(string='Male Transit Mortality')
    female_mortality_transit = fields.Integer(string='Female Transit Mortality')
    male_mortality_premise = fields.Integer(string='Male On-Premise Mortality')
    female_mortality_premise = fields.Integer(string='Female On-Premise Mortality')

    birds_received_male = fields.Integer(string='Male Received')
    birds_received_female = fields.Integer(string='Female Received')
    males_sorted = fields.Integer(string='Males Sorted')
    females_sorted = fields.Integer(string='Females Sorted')
    males_introduced = fields.Integer(string='Males Introduced')
    females_placed = fields.Integer(string='Females Placed')
    eggs_collected = fields.Integer(string='Eggs Collected')
    eggs_sent_to_hatchery = fields.Integer(string='Eggs Sent to Hatchery')

    store_items_received = fields.Text(string='Items Received from Store')
    observations = fields.Text(string='Observations')
    activities = fields.Text(string='Activities')
    remarks = fields.Text(string='Remarks')

    state = fields.Selection([('draft', 'Draft'), ('done', 'Posted')], default='draft', string='Status')

    def action_post_log(self):
        for record in self:
            record.state = 'done'

    def unlink(self):
        for record in self:
            if record.state == 'done':
                raise UserError(_("You cannot delete a Posted breeder log line."))
        return super().unlink()