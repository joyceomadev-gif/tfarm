from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ChickenBatch(models.Model):
    _name = 'taghini.chicken.batch'
    _description = 'Purchased Chicken Batch (Source)'
    _inherit = ['mail.thread']
    _order = 'date desc'

    name = fields.Char(string='Batch Reference', required=True, copy=False, default='New')
    date = fields.Date(string='Received Date', default=fields.Date.context_today, required=True)
    supplier_id = fields.Many2one('res.partner', string='Supplier', required=True)
    
    # The total birds bought
    total_quantity = fields.Integer(string='Total Purchased Qty', required=True, tracking=True)
    
    # Smart fields to track usage across pens
    series_ids = fields.One2many('taghini.flock', 'batch_id', string='Pen Series')
    allocated_quantity = fields.Integer(string='Allocated Qty', compute='_compute_allocation', store=True)
    remaining_quantity = fields.Integer(string='Remaining Qty', compute='_compute_allocation', store=True)

    @api.depends('total_quantity', 'series_ids.quantity_placed')
    def _compute_allocation(self):
        for record in self:
            allocated = sum(record.series_ids.mapped('quantity_placed'))
            record.allocated_quantity = allocated
            record.remaining_quantity = record.total_quantity - allocated

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('taghini.chicken.batch') or 'New'
        return super().create(vals_list)