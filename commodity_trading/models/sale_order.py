from odoo import models, fields, api
from odoo import exceptions

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    commodity_contract_id = fields.Many2one('commodity.contract', string='Commodity Contract', copy=False)


    @api.onchange('commodity_contract_id')
    def _onchange_commodity_contract_id(self):
        if self.commodity_contract_id:
            contract = self.commodity_contract_id
            
            # 1. Auto-fill the Customer (Partner) if it's empty
            if not self.partner_id:
                self.partner_id = contract.partner_id

            # 2. Check if a line with this product already exists to avoid duplicates
            existing_line = self.order_line.filtered(lambda l: l.product_id == contract.product_id)
            
            if not existing_line:
                # 3. Create a new Sales Order Line with the contract details
                line_vals = {
                    'product_id': contract.product_id.id,
                    'name': f"{contract.product_id.name} - Contract {contract.name}",
                    'product_uom_qty': contract.contract_qty,
                    'price_unit': contract.estimated_contract_price,
                    'product_uom_id': contract.product_id.uom_id.id,
                }
                # Odoo syntax to append a new line to a One2many field
                self.order_line = [(0, 0, line_vals)]
            else:
                # 4. If the line exists, just update its quantity and price
                existing_line.product_uom_qty = contract.contract_qty
                existing_line.price_unit = contract.estimated_contract_price

    def action_create_commodity_invoice(self):
        self.ensure_one()
        
        # Ensure there is a contract linked
        if not self.commodity_contract_id:
            raise exceptions.UserError("This Sales Order is not linked to a Commodity Contract.")
            
        contract = self.commodity_contract_id
        
        # 1. Find all completed deliveries for THIS Sales Order
        pickings = self.env['stock.picking'].search([
            ('sale_id', '=', self.id),
            ('state', '=', 'done'),
            ('is_invoiced', '=', False)
        ])
        
        if not pickings:
            raise exceptions.UserError("No un-invoiced, completed deliveries found for this Sale Order.")
            
        # 2. Prepare the Invoice header
        invoice_vals = {
            'move_type': 'out_invoice', 
            'partner_id': self.partner_id.id,
            'commodity_contract_id': contract.id,
            'currency_id': contract.sales_currency_id.id or self.env.company.currency_id.id,
            'invoice_origin': self.name, # Link back to the SO visually
            'invoice_line_ids': []
        }

        # 3. Loop through each delivery and create a SEPARATE invoice line
        for picking in pickings:
            if picking.payable_weight <= 0:
                continue
                
            # Descriptive line matching your document requirements
            line_name = f"Delivery: {picking.name} | Gross: {picking.gross_weight} MT | QC Discount: {picking.quality_discount_weight} MT"
            
            # Find the SO line to link it properly in Odoo's backend
            so_line = self.order_line.filtered(lambda l: l.product_id == contract.product_id)
            
            line_vals = (0, 0, {
                'name': line_name,
                'product_id': contract.product_id.id,
                'quantity': picking.payable_weight, 
                'price_unit': contract.estimated_contract_price, # Base price, user edits this based on fixation
                'product_uom_id': contract.product_id.uom_id.id,
                'sale_line_ids': [(6, 0, so_line.ids)] if so_line else []
            })
            invoice_vals['invoice_line_ids'].append(line_vals)
            
        if not invoice_vals['invoice_line_ids']:
            raise exceptions.UserError("Deliveries found, but total Payable Weight is 0.")

        # 4. Create the actual Invoice
        invoice = self.env['account.move'].create(invoice_vals)
        
        # 5. Mark these deliveries as invoiced
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


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.depends('move_ids.state', 'move_ids.picking_id.payable_weight')
    def _compute_qty_delivered(self):
        # 1. Let standard Odoo calculate delivered quantities normally first
        super()._compute_qty_delivered()
        
        # 2. Override the delivered quantity ONLY for Commodity Contracts
        for line in self:
            if line.order_id.commodity_contract_id and line.product_id == line.order_id.commodity_contract_id.product_id:
                total_payable = 0.0
                
                # FIX: Removed the 'scrapped' check. Just look for 'done' moves.
                done_moves = line.move_ids.filtered(lambda m: m.state == 'done')
                
                # Group by picking to avoid double counting if there are multiple moves in one ticket
                done_pickings = done_moves.mapped('picking_id')
                
                for picking in done_pickings:
                    total_payable += picking.payable_weight
                
                # Overwrite the standard delivered qty with our custom Financial Payable Weight
                line.qty_delivered = total_payable