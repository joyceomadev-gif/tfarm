from odoo import models, fields, api, _
from odoo.exceptions import UserError


class TaghiniFarm(models.Model):
    _name = 'taghini.farm'
    _description = 'Farm Site'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name asc'

    name = fields.Char(string='Farm Name', required=True, tracking=True)
    code = fields.Char(string='Farm Code / ID', copy=False, default='New', help="Unique identifier or short code for reports, e.g. FRM/2026/001.")
    farm_type = fields.Selection([
        ('broiler', 'Broiler'),
        ('breeder', 'Breeder'),
        ('mixed', 'Mixed'),
    ], string='Farm Type', default='broiler', required=True, tracking=True)
    active = fields.Boolean(default=True)

    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company, tracking=True
    )

    # === THE CORE LINK: Farm → Warehouse ===
    warehouse_id = fields.Many2one(
        'stock.warehouse', string='Warehouse',
        domain="[('company_id', '=', company_id)]",
        required=True, tracking=True,
        help="The warehouse that represents this farm. All feed and medication "
             "stock moves will draw from this warehouse's main stock location."
    )

    # Auto-derived locations from warehouse (no manual entry needed)
    stock_location_id = fields.Many2one(
        'stock.location', string='Main Stock Location',
        related='warehouse_id.lot_stock_id', store=True, readonly=True,
        help="Automatically set from the warehouse. Feed and meds are drawn from here."
    )

    default_abattoir_id = fields.Many2one(
        'taghini.abattoir', string='Default Abattoir',
        check_company=False, tracking=True,
        help="Default abattoir this farm dispatches harvested birds to."
    )

    # Farm-level destination locations (moved from taghini.farm.standard)
    abattoir_location_id = fields.Many2one(
        'stock.location', string='Abattoir Location',
        domain="[('usage', '=', 'internal')]", check_company=False,
        tracking=True,
        help="Where live birds are transferred to on harvest."
    )
    storage_location_id = fields.Many2one(
        'stock.location', string='Storage / Freezer Location',
        domain="[('usage', '=', 'internal')]", check_company=False,
        tracking=True,
        help="Where finished meat products are posted after abattoir processing."
    )
    # === TASK B2: Cold Room / Freezer section locations ===
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

    # Staff
    manager_id = fields.Many2one(
        'res.users', string='Farm Manager', tracking=True,
        domain="[('company_ids', 'in', company_id)]"
    )
    vet_id = fields.Many2one(
        'res.users', string='Veterinary Doctor', tracking=True,
        domain="[('company_ids', 'in', company_id)]"
    )
    # === TASK C5: MD (Managing Director) for alerts ===
    md_user_id = fields.Many2one(
        'res.users', string='Managing Director (MD)',
        tracking=True,
        domain="[('company_ids', 'in', company_id)]",
        help="Receives automatic alerts for unrecorded birds and abattoir discrepancies."
    )

    # === REQUIREMENT 5 & 6: Assign users to farms for access restriction ===
    user_ids = fields.Many2many(
        'res.users', 'taghini_farm_user_rel', 'farm_id', 'user_id',
        string='Assigned Employees / Users',
        help="Users listed here are allowed to perform operations on this farm. "
             "Farm managers and system admins bypass this restriction."
    )

    # Related pens
    pen_ids = fields.One2many('taghini.pen', 'farm_id', string='Pens / Houses')
    pen_count = fields.Integer(compute='_compute_counts', string='Pens')
    active_flock_count = fields.Integer(compute='_compute_counts', string='Active Flocks')
    total_birds = fields.Integer(compute='_compute_counts', string='Live Birds')

    notes = fields.Text(string='Notes')

    # -----------------------------------------------------------------------
    # Computed
    # -----------------------------------------------------------------------
    @api.depends('pen_ids', 'pen_ids.flock_ids', 'pen_ids.flock_ids.state',
                 'pen_ids.flock_ids.current_birds')
    def _compute_counts(self):
        for farm in self:
            farm.pen_count = len(farm.pen_ids)
            active_flocks = farm.pen_ids.flock_ids.filtered(lambda f: f.state == 'active')
            farm.active_flock_count = len(active_flocks)
            farm.total_birds = sum(active_flocks.mapped('current_birds'))

    # -----------------------------------------------------------------------
    # Smart-button actions
    # -----------------------------------------------------------------------
    def action_view_pens(self):
        self.ensure_one()
        return {
            'name': _('Pens in %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'taghini.pen',
            'view_mode': 'list,form',
            'domain': [('farm_id', '=', self.id)],
            'context': {'default_farm_id': self.id},
        }

    def action_view_flocks(self):
        self.ensure_one()
        flock_ids = self.pen_ids.flock_ids.ids
        return {
            'name': _('Flocks in %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'taghini.flock',
            'view_mode': 'list,form',
            'domain': [('id', 'in', flock_ids)],
            'context': {},
        }

    # --- UNIQUE SEQUENCE ID & DISPLAY NAME ---
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code') or vals.get('code') == 'New':
                vals['code'] = self.env['ir.sequence'].next_by_code('taghini.farm') or 'New'
        return super().create(vals_list)

    def _compute_display_name(self):
        for record in self:
            code = record.code
            name = record.name
            if code and code != 'New' and name and name != code:
                record.display_name = f"[{code}] {name}"
            else:
                record.display_name = name or code or _('New')

    def init(self):
        super().init()
        farms_without_code = self.search([
            '|', ('code', '=', False), ('code', '=', 'New')
        ], order='id asc')
        for farm in farms_without_code:
            seq_val = self.env['ir.sequence'].next_by_code('taghini.farm')
            farm.code = seq_val or f"FRM/{farm.id:03d}"
