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
        contract = self.commodity_contract_id
        
        # 1. Fetch un-invoiced Confirmed Fixations
        fixations = self.env['price.fixation'].search([
            ('contract_id', '=', contract.id),
            ('state', '=', 'confirmed')
        ])
        
        if not fixations:
            raise exceptions.UserError("No confirmed fixations found to invoice.")
            
        invoice_vals = {
            'move_type': 'out_invoice', 
            'partner_id': self.partner_id.id,
            'commodity_contract_id': contract.id,
            'currency_id': contract.sales_currency_id.id or self.env.company.currency_id.id,
            'invoice_origin': self.name, 
            'invoice_line_ids': []
        }

        so_line = self.order_line.filtered(lambda l: l.product_id == contract.product_id)

        # Identify any Provisional Fixations that are linked to Final ones in this batch
        linked_provisional_ids = fixations.mapped('linked_provisional_id.id')

        for fix in fixations:
            
            # Skip this loop if it's a Provisional Fixation that is already being handled by a True-Up!
            if fix.id in linked_provisional_ids:
                continue
            
            # ========================================================
            # SCENARIO A: TRUE-UP INVOICING (The Difference Method)
            # ========================================================
            if fix.linked_provisional_id:
                # 1. Identify the quantities and prices
                prov_qty = fix.linked_provisional_id.fixed_qty
                prov_price = fix.linked_provisional_id.final_fixed_price
                
                # 2. Calculate the unpaid difference for the old quantity
                price_difference = fix.final_fixed_price - prov_price
                
                # Line 1: The NEW quantity at the Final Price (e.g., 60 MT @ $5,000)
                invoice_vals['invoice_line_ids'].append((0, 0, {
                    'name': f"{contract.product_id.name} - Final Price Fixation",
                    'product_id': contract.product_id.id,
                    'quantity': fix.fixed_qty,
                    'price_unit': fix.final_fixed_price,
                    'product_uom_id': contract.product_id.uom_id.id,
                    'sale_line_ids': [(6, 0, so_line.ids)] if so_line else []
                }))
                
                # Line 2: The unpaid DIFFERENCE for the old Provisional quantity (e.g., 40 MT @ $1,500)
                if price_difference != 0:
                    invoice_vals['invoice_line_ids'].append((0, 0, {
                        'name': f"{contract.product_id.name} - Difference not paid for Provisional (Ref: {fix.linked_provisional_id.name})",
                        'product_id': contract.product_id.id,
                        'quantity': prov_qty,
                        'price_unit': price_difference, # This is just the positive difference
                        'product_uom_id': contract.product_id.uom_id.id,
                        'sale_line_ids': [(6, 0, so_line.ids)] if so_line else []
                    }))

            # ========================================================
            # SCENARIO B: STANDARD INVOICING (Not linked)
            # ========================================================
            else:
                fix_type_label = dict(fix._fields['fixation_type'].selection).get(fix.fixation_type)
                invoice_vals['invoice_line_ids'].append((0, 0, {
                    'name': f"{contract.product_id.name} - {fix_type_label} Fixation",
                    'product_id': contract.product_id.id,
                    'quantity': fix.fixed_qty,
                    'price_unit': fix.final_fixed_price,
                    'product_uom_id': contract.product_id.uom_id.id,
                    'sale_line_ids': [(6, 0, so_line.ids)] if so_line else []
                }))

        # Create Invoice
        invoice = self.env['account.move'].create(invoice_vals)
        
        # Mark fixations as invoiced
        for fix in fixations:
            fix.state = 'invoiced'
            fix.invoice_id = invoice.id
            
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }