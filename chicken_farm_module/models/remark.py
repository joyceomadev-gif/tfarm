from odoo import models, fields, api, _

class FarmRemark(models.Model):
    _name = 'taghini.farm.remark'
    _description = 'Farm Remark and Observation'
    _order = 'name asc'

    name = fields.Char(string='Remark', required=True)
    code = fields.Char(string='Code')
    category = fields.Selection([
        ('health', 'Health & Disease'),
        ('mortality', 'Abnormal Mortality'),
        ('behavior', 'Bird Behavior / Activity'),
        ('feed_water', 'Feed & Water Issue'),
        ('environment', 'Environment / Ventilation / Heat'),
        ('general', 'General Observation')
    ], string='Category', default='health', required=True)
    remark_scope = fields.Selection([
        ('broiler', 'Broiler'),
        ('breeder', 'Breeder'),
        ('both', 'Both')
    ], string='Remark Scope', default='both', required=True)
    need_escalation = fields.Boolean(
        string='Needs Vet Attention / Escalation',
        default=False,
        help='Check if this condition or symptom requires immediate notification to the veterinarian.'
    )
    color = fields.Integer(string='Color Index', default=0)
    description = fields.Text(string='Guidance / Instructions')
    active = fields.Boolean(default=True)

    @api.onchange('need_escalation')
    def _onchange_need_escalation(self):
        if self.need_escalation and not self.color:
            self.color = 1

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('need_escalation') and not vals.get('color'):
                vals['color'] = 1
        return super().create(vals_list)
