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

    invoice_id = fields.Many2one('account.move', string='Linked Invoice', readonly=True, copy=False)

    # ==========================================
    # NEW: Link to a previous provisional fixation
    # ==========================================
    linked_provisional_id = fields.Many2one(
        'price.fixation', 
        string='Linked Provisional Fixation', 
        domain="[('contract_id', '=', contract_id), ('fixation_type', '=', 'provisional')]",
        help="Select the Provisional Fixation this Final/Part Fixation is replacing to calculate the difference."
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
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                # Reusing the standard Odoo sequence logic, or you can create a custom one later
                vals['name'] = self.env['ir.sequence'].next_by_code('sale.order') or 'New'
        return super(PriceFixation, self).create(vals_list)