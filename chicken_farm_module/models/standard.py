from odoo import models, fields, api
from odoo.exceptions import UserError

class FarmStandard(models.Model):
    _name = 'taghini.farm.standard'
    _description = 'Breed Standard / Farm Profile'

    name = fields.Char(string='Standard Name', required=True, default='Ross 308 Standard')
    breed = fields.Char(string='Breed')
    abattoir_location_id = fields.Many2one(
        'stock.location', 
        string='Abattoir Location',
        domain="[('usage', '=', 'internal')]", # <--- Now allows Internal locations
        check_company=False, # <--- THIS FIXES THE EMPTY LIST
        help="The destination location when harvesting."
    )
    storage_location_id = fields.Many2one(
        'stock.location', 
        string='Target Freezer/Store', 
        domain="[('usage', '=', 'internal')]", # <--- Now allows Internal locations
        check_company=False, # <--- THIS FIXES THE EMPTY LIST
        help="The destination location when harvesting."
    )
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
    medication_id = fields.Many2one('product.product', string='Recommended Medication')
    medication_qty = fields.Float(string='Medication Quantity', help="Quantity to apply per bird or per batch")
    
    # Automatically show the Unit of Measure of the selected medication product
    medication_uom_id = fields.Many2one(
        'uom.uom', 
        related='medication_id.uom_id', 
        string="Medication Unit", 
        readonly=True,
        store=True
    )