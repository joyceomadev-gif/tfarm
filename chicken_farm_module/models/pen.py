from odoo import models, fields, api, _

class FarmPen(models.Model):
    _name = 'taghini.pen'
    _description = 'Farm Pen / House'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Pen Name', required=True, help="e.g. Pen 01")
    
    # Link to physical Inventory Location
    location_id = fields.Many2one('stock.location', string='Stock Location', 
                                  domain=[('usage', '=', 'internal')], required=True,
                                  help="The physical location in the warehouse where birds are counted.")
    
    # Staff Assignments
    manager_id = fields.Many2one('res.users', string='Farm Manager', required=True, tracking=True)
    vet_id = fields.Many2one('res.users', string='Veterinary Doctor', required=True, tracking=True)
    
    # Smart Button Logic
    flock_ids = fields.One2many('taghini.flock', 'pen_model_id', string='Flocks')
    flock_count = fields.Integer(compute='_compute_flock_count')

    @api.depends('flock_ids')
    def _compute_flock_count(self):
        for record in self:
            record.flock_count = len(record.flock_ids)

    def action_view_flocks(self):
        """ Smart Button to open related Flocks """
        self.ensure_one()
        return {
            'name': _('Flocks in %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'taghini.flock',
            'view_mode': 'list,form',
            'domain': [('pen_model_id', '=', self.id)],
            'context': {'default_pen_model_id': self.id, 'default_pen_id': self.location_id.id},
        }

    def action_create_batch(self):
        """ Shortcut button to create a new Batch in this Pen """
        self.ensure_one()
        return {
            'name': _('New Batch'),
            'type': 'ir.actions.act_window',
            'res_model': 'taghini.flock',
            'view_mode': 'form',
            'context': {
                'default_pen_model_id': self.id,
                'default_pen_id': self.location_id.id,
                'default_name': f"Batch - {self.name} - {fields.Date.today()}"
            },
        }