from odoo import models, fields

class AccountMove(models.Model):
    _inherit = 'account.move'

    commodity_contract_id = fields.Many2one('commodity.contract', string='Commodity Contract', readonly=True)