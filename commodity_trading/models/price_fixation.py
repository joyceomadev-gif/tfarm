from odoo import models, fields, api, exceptions

class PriceFixation(models.Model):
    _name = 'price.fixation'
    _description = 'Commodity Price Fixation'
    _order = 'date desc, id desc'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default='New')
    contract_id = fields.Many2one('commodity.contract', string='Contract', required=True, ondelete='cascade')
    date = fields.Date(string='Fixation Date', default=fields.Date.context_today, required=True)
    
    # The 3 Scenarios from your document
    fixation_type = fields.Selection([
        ('provisional', 'Provisional (Percentage)'),
        ('part', 'Part Fixation'),
        ('final', 'Final Price Fixation')
    ], string='Fixation Type', required=True, default='provisional')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('invoiced', 'Invoiced')
    ], string='Status', default='draft', required=True)

    # Quantity & Pricing
    fixed_qty = fields.Float(string='Fixed Quantity (MT)', required=True)
    
    # Only applies if 'provisional' is selected
    provisional_percentage = fields.Float(string='Provisional %', help='Enter 70 for 70%')
    
    # Financial fields
    currency_id = fields.Many2one(related='contract_id.contract_currency_id', depends=['contract_id'])
    market_price_at_fixation = fields.Monetary(string='Current Market Price', currency_field='currency_id', required=True)
    differential = fields.Float(string='Contract Differential', related='contract_id.differential', store=True)
    
    final_fixed_price = fields.Monetary(
        string='Calculated Fixation Price', 
        compute='_compute_fixed_price', 
        store=True, 
        currency_field='currency_id'
    )

    @api.depends('fixation_type', 'provisional_percentage', 'market_price_at_fixation', 'differential')
    def _compute_fixed_price(self):
        for record in self:
            # Base logic: Market Price +/- Differential
            base_price = record.market_price_at_fixation + record.differential
            
            # If Provisional, it acts as a stop-loss percentage
            if record.fixation_type == 'provisional':
                record.final_fixed_price = base_price * (record.provisional_percentage / 100.0)
            else:
                # For Part or Final, apply the absolute adjusted market price
                record.final_fixed_price = base_price

    @api.constrains('fixed_qty')
    def _check_quantity(self):
        for record in self:
            if record.fixed_qty <= 0:
                raise exceptions.ValidationError("Fixed Quantity must be greater than zero.")