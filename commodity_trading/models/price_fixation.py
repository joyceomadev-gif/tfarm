from odoo import models, fields, api, exceptions
from odoo.tools import float_compare

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

    # Mark if a provisional fixation has been converted to a final fixation
    is_converted = fields.Boolean(string='Is Converted', copy=False, default=False)

    # ==========================================
    # NEW: Link to a previous provisional fixation
    # ==========================================
    linked_provisional_id = fields.Many2one(
        'price.fixation', 
        string='Linked Provisional Fixation', 
        domain="[('contract_id', '=', contract_id), ('fixation_type', '=', 'provisional')]",
        help="Select the Provisional Fixation this Final/Part Fixation is replacing to calculate the difference."
    )
    # When a final fixation replaces only part of a provisional, store the replaced qty here
    linked_provisional_qty = fields.Float(string='Linked Provisional Qty (MT)', help='Quantity of the provisional fixation that this final fixation replaces')

    @api.depends('fixation_type', 'provisional_percentage', 'market_price_at_fixation', 'differential')
    def _compute_fixed_price(self):
        for record in self:
            # If Provisional, it acts as a stop-loss percentage
            if record.fixation_type == 'provisional':
                base_price = record.market_price_at_fixation
                record.final_fixed_price = base_price * (record.provisional_percentage / 100.0)
            else:
                base_price = record.market_price_at_fixation + record.differential
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
                # Use dedicated sequence for price fixations
                vals['name'] = self.env['ir.sequence'].next_by_code('price.fixation') or 'New'
        return super(PriceFixation, self).create(vals_list)

    def action_convert_to_final(self):
        """Open a small wizard to convert (possibly partially) a provisional fixation to a final one."""
        self.ensure_one()
        if self.fixation_type != 'provisional':
            raise exceptions.UserError('Only provisional fixations can be converted to final.')

        # Open the transient wizard with default values
        return {
            'name': 'Convert Provisional to Final',
            'type': 'ir.actions.act_window',
            'res_model': 'price.fixation.convert.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_provisional_id': self.id,
                'default_qty': self.fixed_qty,
            }
        }


class PriceFixationConvertWizard(models.TransientModel):
    _name = 'price.fixation.convert.wizard'
    _description = 'Convert Provisional Fixation to Final (Wizard)'

    provisional_id = fields.Many2one('price.fixation', string='Provisional Fixation', required=True, domain="[('fixation_type','=', 'provisional')]")
    qty = fields.Float(string='Quantity to Convert (MT)', required=True)

    def action_confirm(self):
        self.ensure_one()
        prov = self.provisional_id
        if self.qty <= 0 or self.qty > prov.fixed_qty:
            raise exceptions.UserError('Quantity must be greater than 0 and less than or equal to the provisional quantity.')

        contract = prov.contract_id
        market_price_for_final = contract.market_price or prov.market_price_at_fixation

        final_vals = {
            'contract_id': contract.id,
            'fixation_type': 'final',
            'date': fields.Date.context_today(self),
            'fixed_qty': self.qty,
            'provisional_percentage': 0.0,
            'market_price_at_fixation': market_price_for_final,
            'state': 'confirmed',
            'linked_provisional_id': prov.id,
            'linked_provisional_qty': self.qty,
        }

        final_fix = self.env['price.fixation'].create(final_vals)

        # If fully converted, mark provisional as converted for clarity
        if float_compare(self.qty, prov.fixed_qty, precision_digits=6) == 0:
            prov.is_converted = True

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'price.fixation',
            'res_id': final_fix.id,
            'view_mode': 'form',
            'target': 'current',
        }