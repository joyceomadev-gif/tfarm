from odoo import models, fields, api
from odoo.exceptions import UserError

class FarmStandard(models.Model):
    _name = 'taghini.farm.standard'
    _description = 'Breed & Performance Standard'

    name = fields.Char(string='Standard Name', required=True, default='Ross 308 Standard')
    breed = fields.Char(string='Breed')
    standard_type = fields.Selection([
        ('broiler', 'Commercial Broiler Growth Profile'),
        ('breeder', 'Breeder Parent Stock Performance Objectives'),
    ], string='Standard Type', default='broiler', required=True)

    abattoir_location_id = fields.Many2one(
        'stock.location', 
        string='Abattoir Location',
        domain="[('usage', '=', 'internal')]",
        check_company=False,
        help="The destination location when harvesting."
    )
    storage_location_id = fields.Many2one(
        'stock.location', 
        string='Target Freezer/Store', 
        domain="[('usage', '=', 'internal')]",
        check_company=False,
        help="The destination location when harvesting."
    )
    line_ids = fields.One2many('taghini.farm.standard.line', 'standard_id', string='Rules')

class FarmStandardLine(models.Model):
    _name = 'taghini.farm.standard.line'
    _description = 'Standard Line (Age Rule / Benchmark)'
    _order = 'week asc, age_min asc, id asc'

    standard_id = fields.Many2one('taghini.farm.standard', string='Standard', ondelete='cascade')
    standard_type = fields.Selection(
        related='standard_id.standard_type',
        store=True,
        readonly=True,
        string='Standard Type'
    )
    
    # Range configuration (Broiler & Breeder common)
    age_min = fields.Integer(string='Min Age (Days)', required=False, default=0)
    age_max = fields.Integer(string='Max Age (Days)', required=False, default=0)
    
    # Broiler specific
    product_id = fields.Many2one('product.product', string='Recommended Feed', required=False)
    expected_feed_g = fields.Float(string='Expected Feed (g/bird)', help="Grams per bird per day")
    expected_weight_g = fields.Float(string='Target Weight (g)', help="Target body weight at end of this range")
    medication_id = fields.Many2one('product.product', string='Recommended Medication')
    medication_qty = fields.Float(string='Medication Quantity', help="Quantity to apply per bird or per batch")
    medication_uom_id = fields.Many2one(
        'uom.uom', 
        related='medication_id.uom_id', 
        string="Medication Unit", 
        readonly=True,
        store=True
    )

    # Breeder specific (Arbor Acres Plus Parent Stock Objectives)
    week = fields.Integer(string='Age (Week)', default=0, index=True)
    aa_female_bw_g = fields.Float(string='Target Female BW (g)')
    aa_male_bw_g = fields.Float(string='Target Male BW (g)')
    aa_female_feed_g = fields.Float(string='Female Feed (g/bird/day)')
    aa_male_feed_g = fields.Float(string='Male Feed (g/bird/day)')
    aa_hen_week_pct = fields.Float(string='Hen-Week Lay %', digits=(16, 4))
    aa_hatching_egg_pct = fields.Float(string='Hatching-Egg Util %', digits=(16, 4))
    aa_hatchability_pct = fields.Float(string='Hatchability %', digits=(16, 4))
    aa_egg_weight_g = fields.Float(string='Target Egg Weight (g)')
    max_weekly_mort_pct = fields.Float(string='Max Weekly Mort %', digits=(16, 4))
    cumulative_mort_target_pct = fields.Float(string='Cum. Mort Target %', digits=(16, 4))
    female_weekly_gain_g = fields.Float(string='Female Wk Gain (g)')
    male_weekly_gain_g = fields.Float(string='Male Wk Gain (g)')

    @api.onchange('week', 'standard_type')
    def _onchange_week(self):
        for rec in self:
            if rec.standard_type == 'breeder':
                rec.age_min = (rec.week or 0) * 7
                rec.age_max = ((rec.week or 0) * 7) + 6
