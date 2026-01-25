from odoo import models, fields, api

class FarmStandard(models.Model):
    _name = 'taghini.farm.standard'
    _description = 'Breed Standard / Farm Profile'

    name = fields.Char(string='Standard Name', required=True, default='Ross 308 Standard')
    breed = fields.Char(string='Breed')
    line_ids = fields.One2many('taghini.farm.standard.line', 'standard_id', string='Rules')

class FarmStandardLine(models.Model):
    _name = 'taghini.farm.standard.line'
    _description = 'Standard Line (Age Rule)'
    _order = 'age_min asc'

    standard_id = fields.Many2one('taghini.farm.standard', string='Standard', ondelete='cascade')
    
    # Range configuration
    age_min = fields.Integer(string='Min Age (Days)', required=True)
    age_max = fields.Integer(string='Max Age (Days)', required=True)
    
    # What should happen in this range?
    product_id = fields.Many2one('product.product', string='Recommended Feed', required=True)
    expected_feed_g = fields.Float(string='Expected Feed (g/bird)', help="Grams per bird per day")
    expected_weight_g = fields.Float(string='Target Weight (g)', help="Target body weight at end of this range")