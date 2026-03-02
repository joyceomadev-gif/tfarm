from odoo import models, fields, api

class CommodityContract(models.Model):
    _name = 'commodity.contract'
    _description = 'Commodity Customer Contract'

    name = fields.Char(string='Contract Reference', required=True, copy=False, default='New')
    partner_id = fields.Many2one('res.partner', string='Customer/Vendor', required=True)
    product_id = fields.Many2one('product.product', string='Product', required=True)
    
    contract_type = fields.Selection([
        ('sale', 'Customer Contract'),
        ('purchase', 'Purchase Contract')
    ], string='Contract Type', required=True, default='sale')

    # Quantities
    contract_qty = fields.Float(string='Contract Quantity (MT)', required=True)
    
    # Currency Setup
    contract_currency_id = fields.Many2one('res.currency', string='Contract Currency (GBP)')
    sales_currency_id = fields.Many2one('res.currency', string='Sales Currency (USD)')
    procurement_currency_id = fields.Many2one('res.currency', string='Procurement Currency (NGN)')
    
    # Pricing Formula & Percentages
    market_price = fields.Monetary(string='Market Price', currency_field='contract_currency_id')
    differential = fields.Float(string='Differential (+/-)')
    estimated_contract_price = fields.Monetary(
        string='Est. Contract Price', 
        compute='_compute_estimated_price',
        currency_field='contract_currency_id'
    )
    
    # NEW: Default Provisional Percentage on the Contract
    provisional_percentage = fields.Float(string='Default Provisional %', default=70.0, help="E.g., 70 for 70%")

    fixation_ids = fields.One2many('price.fixation', 'contract_id', string='Price Fixations')

    # Ledger Balances
    total_payable_delivered = fields.Float(string='Total Delivered (Payable MT)', compute='_compute_contract_ledger', store=True)
    total_fixed_qty = fields.Float(string='Total Fixed Qty (MT)', compute='_compute_contract_ledger', store=True)
    unpriced_qty = fields.Float(string='Unpriced Delivered Qty (MT)', compute='_compute_contract_ledger', store=True)

    @api.depends('fixation_ids.fixed_qty', 'fixation_ids.state')
    def _compute_contract_ledger(self):
        for contract in self:
            deliveries = self.env['stock.picking'].search([
                ('commodity_contract_id', '=', contract.id),
                ('state', '=', 'done')
            ])
            contract.total_payable_delivered = sum(deliveries.mapped('payable_weight'))

            confirmed_fixations = contract.fixation_ids.filtered(lambda f: f.state in ['confirmed', 'invoiced'])
            contract.total_fixed_qty = sum(confirmed_fixations.mapped('fixed_qty'))

            contract.unpriced_qty = contract.total_payable_delivered - contract.total_fixed_qty

    @api.depends('market_price', 'differential')
    def _compute_estimated_price(self):
        for record in self:
            record.estimated_contract_price = record.market_price + record.differential

    def action_view_sales_orders(self):
        return {
            'name': 'Sales Orders',
            'view_mode': 'list,form',
            'res_model': 'sale.order',
            'domain': [('commodity_contract_id', '=', self.id)],
            'context': {'default_commodity_contract_id': self.id, 'default_partner_id': self.partner_id.id},
            'type': 'ir.actions.act_window',
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('commodity.contract') or 'New'
        return super(CommodityContract, self).create(vals_list)