from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class TaghiniAbattoir(models.Model):
    _name = 'taghini.abattoir'
    _description = 'Abattoir Site'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name asc'

    name = fields.Char(string='Abattoir Name', required=True, tracking=True)
    code = fields.Char(
        string='Abattoir Code / ID',
        copy=False,
        default='New',
        help="Unique identifier or short code, e.g. ABT/2026/001."
    )
    active = fields.Boolean(default=True)

    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company, tracking=True
    )

    warehouse_id = fields.Many2one(
        'stock.warehouse', string='Warehouse',
        domain="[('company_id', '=', company_id)]",
        required=True, tracking=True,
        help="The warehouse that represents this abattoir. Drives intake, production, and cold-room stock moves."
    )

    stock_location_id = fields.Many2one(
        'stock.location', string='Main Stock Location',
        related='warehouse_id.lot_stock_id', store=True, readonly=True,
        help="Automatically set from the abattoir warehouse."
    )

    abattoir_location_id = fields.Many2one(
        'stock.location', string='Live Bird Intake Location',
        domain="[('usage', '=', 'internal')]", check_company=False,
        tracking=True,
        help="Where live birds are transferred on harvest."
    )
    storage_location_id = fields.Many2one(
        'stock.location', string='Storage / Freezer Location',
        domain="[('usage', '=', 'internal')]", check_company=False,
        tracking=True,
        help="Default destination where finished meat products are posted after abattoir processing."
    )
    cold_room_location_id = fields.Many2one(
        'stock.location', string='Cold Room Location',
        domain="[('usage', '=', 'internal')]", check_company=False,
        tracking=True,
        help="Selling-point cold room location."
    )
    freezer_location_id = fields.Many2one(
        'stock.location', string='Freezer Location',
        domain="[('usage', '=', 'internal')]", check_company=False,
        tracking=True,
        help="Deep freezer location for long-term storage."
    )

    manager_id = fields.Many2one(
        'res.users', string='Abattoir Manager', tracking=True,
        domain="[('company_ids', 'in', company_id)]"
    )
    user_ids = fields.Many2many(
        'res.users', 'taghini_abattoir_user_rel', 'abattoir_id', 'user_id',
        string='Assigned Users',
        help="Users permitted to operate at this abattoir."
    )

    notes = fields.Text(string='Notes')

    @api.constrains('code')
    def _check_unique_code(self):
        for rec in self:
            if rec.code and rec.code != 'New':
                dup = self.search_count([('id', '!=', rec.id), ('code', '=', rec.code)])
                if dup:
                    raise ValidationError(_("Abattoir Code '%s' must be unique.") % rec.code)

    @api.onchange('warehouse_id')
    def _onchange_warehouse_id(self):
        if self.warehouse_id and self.warehouse_id.lot_stock_id:
            if not self.abattoir_location_id:
                self.abattoir_location_id = self.warehouse_id.lot_stock_id
            if not self.storage_location_id:
                self.storage_location_id = self.warehouse_id.lot_stock_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', 'New') == 'New':
                vals['code'] = self.env['ir.sequence'].next_by_code('taghini.abattoir.site') or 'New'
        return super().create(vals_list)
