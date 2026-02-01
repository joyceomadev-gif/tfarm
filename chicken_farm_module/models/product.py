from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    abattoir_type = fields.Selection([
        ('whole', 'Whole Series'),
        ('cut', 'Cut / Part'),
        ('offal', 'By-Product (Offal)'),
        ('other', 'Other')
    ], string='Abattoir Category', default='other', help="Classification for Abattoir Reports")