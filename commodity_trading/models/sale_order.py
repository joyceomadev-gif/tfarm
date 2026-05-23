from odoo import models, fields, api
from odoo.fields import Command
from odoo import exceptions


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    commodity_contract_id = fields.Many2one('commodity.contract', string='Commodity Contract', copy=False)

    # Exchange rate from the order currency to the company currency (as used by Odoo on the order date)
    exchange_rate_to_company = fields.Float(
        string='Exchange Rate (to Company Currency)',
        compute='_compute_exchange_rate_to_company',
        digits=(12, 6),
        store=False,
    )

    # Compute relevant currency rates to display in the form
    related_currency_rate_ids = fields.Many2many(
        'res.currency.rate',
        string='Exchange Rates',
        compute='_compute_related_currency_rates',
        store=False,
    )

    def _compute_exchange_rate_to_company(self):
        for order in self:
            # Default to 1.0 when currencies are identical or missing
            rate = 1.0
            if order.currency_id and order.company_id and order.company_id.currency_id and order.currency_id != order.company_id.currency_id:
                # Use Odoo's conversion utility to get the rate used on the order date
                # The env helper `_get_conversion_rate` returns the multiplier from from_currency -> to_currency
                try:
                    date = order.date_order or fields.Date.context_today(order)
                    rate = self.env['res.currency']._get_conversion_rate(
                        order.currency_id, order.company_id.currency_id, order.company_id, date
                    )
                except Exception:
                    # Fallback: keep rate = 1.0 if conversion isn't available for some reason
                    rate = 1.0
            order.exchange_rate_to_company = rate

    def _compute_related_currency_rates(self):
        """Fetch all currency rates for the order currency and company currency up to the order date."""
        for order in self:
            rates = self.env['res.currency.rate']
            currencies = []
            
            # Collect the relevant currencies
            if order.currency_id:
                currencies.append(order.currency_id.id)
            if order.company_id and order.company_id.currency_id:
                currencies.append(order.company_id.currency_id.id)
            
            # Remove duplicates
            currencies = list(set(currencies))
            
            if currencies:
                domain = [('currency_id', 'in', currencies)]
                # If the order has a date, prefer showing rates up to that date
                if order.date_order:
                    domain.append(('name', '<=', order.date_order))
                
                rates = self.env['res.currency.rate'].search(domain, order='name desc')
            
            order.related_currency_rate_ids = rates

    def _convert_amount_between_currencies(self, amount, from_currency, to_currency, date=None):
        """Convert amount from one currency to another using Odoo currency conversion utilities.

        If either currency is missing, returns the original amount.
        """
        if not from_currency or not to_currency:
            return amount
        if from_currency == to_currency:
            return amount
        company = self.company_id or self.env.company
        conv_date = date or self.date_order or fields.Date.context_today(self)
        try:
            return from_currency._convert(amount, to_currency, company, conv_date)
        except Exception:
            # Fallback to _get_conversion_rate when _convert isn't available
            rate = self.env['res.currency']._get_conversion_rate(from_currency, to_currency, company, conv_date)
            return amount * (rate or 1.0)

    currency_rate_line_ids = fields.One2many(
        'commodity_trading.currency_rate_line', 'sale_order_id', string='Currency Rate Lines')

    def refresh_currency_rate_lines(self):
        """Populate `commodity_trading.currency_rate_line` with the latest rate per active currency."""
        for order in self:
            # remove existing lines
            if order.currency_rate_line_ids:
                order.currency_rate_line_ids.unlink()

            # get active currencies
            currencies = self.env['res.currency'].search([('active', '=', True)])
            lines = []
            for curr in currencies:
                last = self.env['res.currency.rate'].search([('currency_id', '=', curr.id)], order='name desc', limit=1)
                vals = {
                    'sale_order_id': order.id,
                    'currency_id': curr.id,
                    'last_rate': last.rate if last else 1.0,
                    'last_update': last.name if last else False,
                }
                lines.append(vals)
            if lines:
                self.env['commodity_trading.currency_rate_line'].create(lines)

    def _prepare_currency_rate_line_commands(self):
        """Prepare virtual x2many commands for onchange usage without writing to the database."""
        self.ensure_one()
        currencies = self.env['res.currency'].search([('active', '=', True)])
        commands = [Command.clear()]
        for curr in currencies:
            last = self.env['res.currency.rate'].search([('currency_id', '=', curr.id)], order='name desc', limit=1)
            commands.append(Command.create({
                'currency_id': curr.id,
                'last_rate': last.rate if last else 1.0,
                'last_update': last.name if last else False,
            }))
        return commands

    def compute_related_rates(self):
        """Public method called from the view to refresh per-order currency rate snapshot lines and reload the view."""
        for order in self:
            order.refresh_currency_rate_lines()
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_create_exchange_rate(self):
        """Open a form to create a new exchange rate for the currencies in this sale order."""
        self.ensure_one()
        
        # Pre-fill the currency with the order currency if available
        default_currency = self.currency_id.id if self.currency_id else False
        
        return {
            'name': 'Create Exchange Rate',
            'type': 'ir.actions.act_window',
            'res_model': 'res.currency.rate',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_currency_id': default_currency,
                'default_name': self.date_order or fields.Date.today(),
            },
        }

    def _convert_fixation_amount_to_sales_currency(self, fixation, amount_contract_currency):
        """Convert an amount from fixation contract currency to sales currency using fixation snapshot."""
        from_currency = fixation.currency_id or fixation.contract_id.contract_currency_id
        to_currency = fixation.sales_currency_id or fixation.contract_id.sales_currency_id or self.env.company.currency_id
        if not from_currency or not to_currency:
            return amount_contract_currency
        if from_currency == to_currency:
            return amount_contract_currency

        if fixation.fx_rate:
            return amount_contract_currency * fixation.fx_rate

        company = self.company_id or self.env.company
        conversion_date = fixation.fx_date or fixation.date or fields.Date.context_today(self)
        return from_currency._convert(amount_contract_currency, to_currency, company, conversion_date)


    @api.onchange('commodity_contract_id')
    def _onchange_commodity_contract_id(self):
        if self.commodity_contract_id:
            contract = self.commodity_contract_id
            
            # 1. Auto-fill the Customer (Partner) if it's empty
            if not self.partner_id:
                self.partner_id = contract.partner_id

            # 2. Check if a line with this product already exists to avoid duplicates
            existing_line = self.order_line.filtered(lambda l: l.product_id == contract.product_id)
            
            # compute price_unit converted from contract currency -> order currency
            contract_price_cc = contract.estimated_contract_price
            order_currency = self.currency_id or self.env.company.currency_id
            contract_currency = contract.contract_currency_id
            converted_price = self._convert_amount_between_currencies(contract_price_cc or 0.0, contract_currency, order_currency)

            if not existing_line:
                # 3. Create a new Sales Order Line with the contract details
                line_vals = {
                    'product_id': contract.product_id.id,
                    'name': f"{contract.product_id.name} - Contract {contract.name}",
                    'product_uom_qty': contract.contract_qty,
                    'price_unit': converted_price,
                    'product_uom_id': contract.product_id.uom_id.id,
                }
                # Use x2many commands so onchange keeps virtual records instead of raw ints
                self.order_line = [Command.create(line_vals)]
            else:
                # 4. If the line exists, just update its quantity and price
                existing_line.product_uom_qty = contract.contract_qty
                existing_line.price_unit = self._convert_amount_between_currencies(contract.estimated_contract_price or 0.0, contract.contract_currency_id, self.currency_id or self.env.company.currency_id)

    @api.onchange('currency_id')
    def _onchange_currency_id_refresh_rates(self):
        # When the order currency changes, refresh the displayed last-rates
        if self.currency_id:
            try:
                self.currency_rate_line_ids = self._prepare_currency_rate_line_commands()
            except Exception:
                # Avoid breaking the form if refresh fails
                pass

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
                prov_qty = fix.linked_provisional_qty or fix.linked_provisional_id.fixed_qty
                prov_price_cc = fix.linked_provisional_id.final_fixed_price
                final_price_cc = fix.final_fixed_price
                final_price_sc = fix.final_fixed_price_sales or self._convert_fixation_amount_to_sales_currency(fix, final_price_cc)
                
                # 2. Calculate the unpaid difference for the old quantity
                price_difference_cc = final_price_cc - prov_price_cc
                price_difference_sc = self._convert_fixation_amount_to_sales_currency(fix, price_difference_cc)
                
                # Line 1: The NEW quantity at the Final Price (e.g., 60 MT @ $5,000)
                invoice_vals['invoice_line_ids'].append((0, 0, {
                    'name': f"{contract.product_id.name} - Final Price Fixation",
                    'product_id': contract.product_id.id,
                    'quantity': fix.fixed_qty,
                    'price_unit': final_price_sc,
                    'product_uom_id': contract.product_id.uom_id.id,
                    'sale_line_ids': [(6, 0, so_line.ids)] if so_line else []
                }))
                
                # Line 2: The unpaid DIFFERENCE for the old Provisional quantity (e.g., 40 MT @ $1,500)
                if price_difference_sc != 0:
                    invoice_vals['invoice_line_ids'].append((0, 0, {
                        'name': f"{contract.product_id.name} - Difference not paid for Provisional (Ref: {fix.linked_provisional_id.name})",
                        'product_id': contract.product_id.id,
                        'quantity': prov_qty,
                        'price_unit': price_difference_sc,
                        'product_uom_id': contract.product_id.uom_id.id,
                        'sale_line_ids': [(6, 0, so_line.ids)] if so_line else []
                    }))

            # ========================================================
            # SCENARIO B: STANDARD INVOICING (Not linked)
            # ========================================================
            else:
                fix_type_label = dict(fix._fields['fixation_type'].selection).get(fix.fixation_type)
                unit_price_sc = fix.final_fixed_price_sales or self._convert_fixation_amount_to_sales_currency(fix, fix.final_fixed_price)
                invoice_vals['invoice_line_ids'].append((0, 0, {
                    'name': f"{contract.product_id.name} - {fix_type_label} Fixation",
                    'product_id': contract.product_id.id,
                    'quantity': fix.fixed_qty,
                    'price_unit': unit_price_sc,
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
    def action_print_consolidated_invoice(self):
        self.ensure_one()
        
        if not self.commodity_contract_id:
            raise exceptions.UserError("This order is not linked to a Commodity Contract.")
            
        # 1. Check if there are ANY fixations
        if not self.commodity_contract_id.fixation_ids:
            raise exceptions.UserError("There are no price fixations on this contract to print.")
            
        # 2. VERIFICATION: Ensure all confirmed fixations have been fully invoiced
        pending_fixations = self.commodity_contract_id.fixation_ids.filtered(
            lambda f: f.state in ['draft', 'confirmed']
        )
        if pending_fixations:
            raise exceptions.UserError(
                "Cannot generate the Consolidated PDF. "
                "All Price Fixations must be finalized and Invoiced first."
            )
            
        # 3. Trigger the PDF Report download
        return self.env.ref('commodity_trading.action_report_consolidated_invoice').report_action(self)