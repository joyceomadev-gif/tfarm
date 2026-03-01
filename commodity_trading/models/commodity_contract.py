from odoo import models, fields, api
from odoo import exceptions

class CommodityContract(models.Model):
    _name = 'commodity.contract'
    _description = 'Commodity Customer Contract'

    name = fields.Char(string='Contract Reference', required=True, copy=False, default='New')
    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    product_id = fields.Many2one('product.product', string='Product', required=True)
    
    # Quantities
    contract_qty = fields.Float(string='Contract Quantity (MT)', required=True)
    delivered_qty = fields.Float(string='Delivered Quantity', compute='_compute_delivered_qty', store=True)
    
    # Tri-Currency Setup
    contract_currency_id = fields.Many2one('res.currency', string='Contract Currency (e.g., GBP)')
    sales_currency_id = fields.Many2one('res.currency', string='Sales/Payment Currency (e.g., USD)')
    procurement_currency_id = fields.Many2one('res.currency', string='Procurement Currency (e.g., NGN)')
    
    # Pricing Formula
    market_price = fields.Monetary(string='Market Price', currency_field='contract_currency_id')
    differential = fields.Float(string='Differential (+/-)')
    estimated_contract_price = fields.Monetary(
        string='Est. Contract Price', 
        compute='_compute_estimated_price',
        currency_field='contract_currency_id'
    )
    # Link to Price Fixations
    fixation_ids = fields.One2many('price.fixation', 'contract_id', string='Price Fixations')

    total_payable_delivered = fields.Float(string='Total Delivered (Payable MT)', compute='_compute_contract_ledger', store=True)
    total_fixed_qty = fields.Float(string='Total Fixed Qty (MT)', compute='_compute_contract_ledger', store=True)
    unpriced_qty = fields.Float(string='Unpriced Delivered Qty (MT)', compute='_compute_contract_ledger', store=True)

    contract_type = fields.Selection([
        ('sale', 'Customer Contract'),
        ('purchase', 'Purchase Contract')
    ], string='Contract Type', required=True, default='sale')

    @api.depends('fixation_ids.fixed_qty', 'fixation_ids.state',)
    def _compute_contract_ledger(self):
        for contract in self:
            # 1. Get total payable weight from all linked, completed deliveries
            deliveries = self.env['stock.picking'].search([
                ('commodity_contract_id', '=', contract.id),
                ('state', '=', 'done')
            ])
            contract.total_payable_delivered = sum(deliveries.mapped('payable_weight'))

            # 2. Get total quantity that has been priced (fixed)
            confirmed_fixations = contract.fixation_ids.filtered(lambda f: f.state in ['confirmed', 'invoiced'])
            contract.total_fixed_qty = sum(confirmed_fixations.mapped('fixed_qty'))

            # 3. Calculate Unpriced Quantity (Delivered but not yet fixed)
            contract.unpriced_qty = contract.total_payable_delivered - contract.total_fixed_qty

    @api.depends('market_price', 'differential')
    def _compute_estimated_price(self):
        for record in self:
            record.estimated_contract_price = record.market_price + record.differential

    def _compute_delivered_qty(self):
        # We will write the logic later to sum up linked deliveries
        for record in self:
            record.delivered_qty = 0.0
    
    def action_create_consolidated_invoice(self):
        self.ensure_one()
        
        # 1. Find all completed deliveries that have NOT been invoiced
        pickings = self.env['stock.picking'].search([
            ('commodity_contract_id', '=', self.id),
            ('state', '=', 'done'),
            ('is_invoiced', '=', False)
        ])
        
        if not pickings:
            raise exceptions.UserError("No un-invoiced, completed deliveries found for this contract.")
            
        # 2. Prepare the Invoice header
        invoice_vals = {
            'move_type': 'out_invoice', # Customer Invoice
            'partner_id': self.partner_id.id,
            'commodity_contract_id': self.id,
            'currency_id': self.sales_currency_id.id or self.env.company.currency_id.id,
            'invoice_line_ids': []
        }

        # 3. Loop through each delivery and create an invoice line based on PAYABLE WEIGHT
        for picking in pickings:
            # Skip if the payable weight is 0
            if picking.payable_weight <= 0:
                continue
                
            line_name = f"Delivery: {picking.name} | Gross: {picking.gross_weight} MT | QC Discount: {picking.quality_discount_weight} MT"
            
            line_vals = (0, 0, {
                'name': line_name,
                'product_id': self.product_id.id,
                'quantity': picking.payable_weight, # INVOICING BASED ON PAYABLE WEIGHT
                'price_unit': self.estimated_contract_price, # Defaults to contract est, user can adjust to specific fixation
                'product_uom_id': self.product_id.uom_id.id,
            })
            invoice_vals['invoice_line_ids'].append(line_vals)
            
        if not invoice_vals['invoice_line_ids']:
            raise exceptions.UserError("Deliveries found, but total Payable Weight is 0.")

        # 4. Create the actual Invoice in Odoo
        invoice = self.env['account.move'].create(invoice_vals)
        
        # 5. Mark these deliveries as invoiced so they aren't pulled again
        for picking in pickings:
            picking.commodity_invoice_id = invoice.id
            
        # 6. Open the newly created invoice on the screen
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }
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
            # If the name is still 'New', fetch the next sequence number
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('commodity.contract') or 'New'
                
        return super(CommodityContract, self).create(vals_list)