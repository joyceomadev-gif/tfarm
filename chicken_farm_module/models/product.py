from odoo import models, fields, api

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    bird_variant = fields.Boolean(string='Bird Variant', help='Mark products that represent birds or chicks.')
    bird_flow = fields.Selection([
        ('broiler', 'Commercial Broiler'),
        ('breeder', 'Breeder Stock'),
    ], string='Bird Workflow', default='broiler', help='Used to distinguish commercial broilers from breeder stock.')
    bird_sex = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('both', 'Both Sexes'),
    ], string='Sex Applicability', default='both', help='Defines whether the bird variant is male, female, or mixed.')

    abattoir_type = fields.Selection([
        ('series', 'Whole Series'),
        ('cuts', 'Chicken Cuts'),
        ('parts', 'Chicken parts'),
        ('residuals', 'Residuals'),
        ('other', 'Other'),
    ], string='Abattoir Category', default='other', help="Classification for Abattoir Reports")

    grading_line_id = fields.Many2one(
        'taghini.grading.checklist.line',
        string='Grading Series Spec',
        help="Links this product / SKU to its standard in the Taghini Grading Checklist."
    )
