from odoo import models, fields, api

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'


    state = fields.Selection(selection_add=[
        ('approved', 'Approved'),
        ('purchase',)
    ], ondelete={'approved': 'set default'})
    # Link only to Purchase Contracts
    commodity_contract_id = fields.Many2one(
        'commodity.contract', 
        string='Commodity Contract', 
        copy=False
    )
    

    @api.model_create_multi
    def create(self, vals_list):
        orders = super(PurchaseOrder, self).create(vals_list)
        
        # When a PO is created, automatically notify everyone in the Approver group
        approver_group = self.env.ref('commodity_trading.group_commodity_po_approver', raise_if_not_found=False)
        
        # FIXED FOR ODOO 19: Changed .users to .user_ids
        if approver_group and approver_group.user_ids:
            for order in orders:
                for user in approver_group.user_ids:
                    # This schedules a native Odoo "To-Do" Activity in their top-right notification bell!
                    order.activity_schedule(
                        'mail.mail_activity_data_todo',
                        summary='Approve New Purchase Request',
                        note=f'A new Purchase Request ({order.name}) has been created and requires your approval.',
                        user_id=user.id
                    )
        return orders

    def action_approve_po(self):
        """ Custom button action to approve the PO """
        for order in self:
            order.state = 'approved'
            # Optional: Mark the scheduled To-Do activities as "Done" automatically
            order.activity_feedback(['mail.mail_activity_data_todo'])

    def button_confirm(self):
        """ Override standard confirm to enforce our new Approved state """
        for order in self:
            if order.state in ['draft', 'sent']:
                raise exceptions.UserError("You must Approve the Purchase Request before confirming the order.")
            
            if order.state == 'approved':
                # Temporarily revert to draft so standard Odoo confirmation logic works perfectly behind the scenes
                order.state = 'draft'
                
        return super(PurchaseOrder, self).button_confirm()

    @api.onchange('commodity_contract_id')
    def _onchange_commodity_contract_id(self):
        if self.commodity_contract_id:
            contract = self.commodity_contract_id
            
            # 1. Auto-fill the Vendor
            if not self.partner_id:
                self.partner_id = contract.partner_id

            # 2. Check for existing product line
            existing_line = self.order_line.filtered(lambda l: l.product_id == contract.product_id)
            
            if not existing_line:
                # 3. Create a new Purchase Order Line
                line_vals = {
                    'product_id': contract.product_id.id,
                    'name': f"{contract.product_id.name} - Contract {contract.name}",
                    'product_qty': contract.contract_qty,
                    'price_unit': contract.estimated_contract_price,
                    'product_uom_id': contract.product_id.uom_id.id,
                }
                self.order_line = [(0, 0, line_vals)]
            else:
                existing_line.product_qty = contract.contract_qty
                existing_line.price_unit = contract.estimated_contract_price
    
    def action_create_commodity_bill(self):
        self.ensure_one()
        
        # Find all completed receipts for this PO that haven't been billed
        pickings = self.env['stock.picking'].search([
            ('purchase_id', '=', self.id),
            ('state', '=', 'done'),
            ('commodity_invoice_id', '=', False) 
        ])
        
        if not pickings:
            raise exceptions.UserError("No unbilled receipts found for this Purchase Order.")

        invoice_vals = {
            'move_type': 'in_invoice', # Vendor Bill
            'partner_id': self.partner_id.id,
            'purchase_id': self.id,
            'currency_id': self.currency_id.id,
            'invoice_origin': self.name,
            'invoice_line_ids': []
        }

        po_line = self.order_line[0] if self.order_line else False

        for picking in pickings:
            # Line 1: Payable Weight at the PO Price
            if picking.payable_weight > 0:
                invoice_vals['invoice_line_ids'].append((0, 0, {
                    'name': f"Delivery Ref: {picking.name} - Payable Weight",
                    'product_id': self.product_id.id if hasattr(self, 'product_id') else po_line.product_id.id,
                    'quantity': picking.payable_weight/1000,
                    'price_unit': po_line.price_unit if po_line else 0.0,
                    'product_uom_id': po_line.product_id.uom_id.id if po_line else False,
                    'purchase_line_id': po_line.id if po_line else False,
                }))
            
            # Line 2: Quality Discount at $0.00
            if picking.quality_discount_weight > 0:
                invoice_vals['invoice_line_ids'].append((0, 0, {
                    'name': f"Quality Discount Penalty (Ref: {picking.name})",
                    'product_id': self.product_id.id if hasattr(self, 'product_id') else po_line.product_id.id,
                    'quantity': (picking.quality_discount_weight*picking.net_weight)/1000,
                    'price_unit': 0.0, # ZERO PRICE
                    'product_uom_id': po_line.product_id.uom_id.id if po_line else False,
                    'purchase_line_id': po_line.id if po_line else False,
                }))
                
        bill = self.env['account.move'].create(invoice_vals)
        
        for picking in pickings:
            picking.commodity_invoice_id = bill.id
            
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': bill.id,
            'view_mode': 'form',
            'target': 'current',
        }


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    @api.depends('move_ids.state', 'move_ids.picking_id.net_weight')
    def _compute_qty_received(self):
        super()._compute_qty_received()
        for line in self:
            if line.order_id.commodity_contract_id and line.product_id == line.order_id.commodity_contract_id.product_id:
                total_net = 0.0
                done_moves = line.move_ids.filtered(lambda m: m.state == 'done')
                done_pickings = done_moves.mapped('picking_id')
                for picking in done_pickings:
                    total_net += picking.net_weight/1000 # Changed to Net Weight
                line.qty_received = total_net