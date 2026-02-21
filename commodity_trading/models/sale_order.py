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
        
        if not self.commodity_contract_id:
            raise exceptions.UserError("This Sales Order is not linked to a Commodity Contract.")
            
        contract = self.commodity_contract_id
        
        # 1. Find all CONFIRMED but UN-INVOICED fixations for this contract
        fixations = self.env['price.fixation'].search([
            ('contract_id', '=', contract.id),
            ('state', '=', 'confirmed') # Must be confirmed by trader to invoice
        ])
        
        if not fixations:
            raise exceptions.UserError("No confirmed, un-invoiced price fixations found. Please create and confirm a Price Fixation on the contract first.")
            
        # 2. Prepare the Invoice header
        invoice_vals = {
            'move_type': 'out_invoice', 
            'partner_id': self.partner_id.id,
            'commodity_contract_id': contract.id,
            'currency_id': contract.sales_currency_id.id or self.env.company.currency_id.id,
            'invoice_origin': self.name, 
            'invoice_line_ids': []
        }

        # 3. Loop through each FIXATION and create a SEPARATE invoice line
        for fix in fixations:
            
            # Create a clean description based on the Fixation type (e.g. "Provisional Fixation")
            fix_type_label = dict(fix._fields['fixation_type'].selection).get(fix.fixation_type)
            line_name = f"{contract.product_id.name} - {fix_type_label} Fixation ({fix.fixed_qty} MT)"
            
            so_line = self.order_line.filtered(lambda l: l.product_id == contract.product_id)
            
            line_vals = (0, 0, {
                'name': line_name,
                'product_id': contract.product_id.id,
                'quantity': fix.fixed_qty,              # QTY comes from the Fixation
                'price_unit': fix.final_fixed_price,    # PRICE comes from the Fixation
                'product_uom_id': contract.product_id.uom_id.id,
                'sale_line_ids': [(6, 0, so_line.ids)] if so_line else []
            })
            invoice_vals['invoice_line_ids'].append(line_vals)

        # 4. Create the Invoice
        invoice = self.env['account.move'].create(invoice_vals)
        
        # 5. Mark these fixations as INVOICED and link them
        for fix in fixations:
            fix.state = 'invoiced'
            fix.invoice_id = invoice.id
            
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