from odoo import models, fields


class CommodityCurrencyRateLine(models.Model):
    _name = 'commodity_trading.currency_rate_line'
    _description = 'Commodity: Currency Rate Line'

    sale_order_id = fields.Many2one('sale.order', string='Sale Order', ondelete='cascade', index=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True)
    last_rate = fields.Float(string='Last Rate', digits=(12, 6))
    last_update = fields.Date(string='Last Update')

    _sql_constraints = [
        ('sale_currency_uniq', 'unique(sale_order_id, currency_id)', 'Currency line already exists for this sale order.')
    ]
