from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    abattoir_type = fields.Selection([
        ('series', 'Whole Series'),
        ('cuts', 'Chicken Cuts'),
        ('parts', 'Chicken parts'),
        ('residuals', 'Residuals')
    ], string='Abattoir Category', default='other', help="Classification for Abattoir Reports")