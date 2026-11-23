from odoo import models, fields, api, _
from odoo.exceptions import UserError


class FarmPen(models.Model):
    _name = 'taghini.pen'
    _description = 'Farm Pen / House'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'pen_code desc, name asc'

    pen_code = fields.Char(
        string='Pen ID',
        readonly=True,
        copy=False,
        default='New',
        index=True,
        help="Unique system sequence generated pen identifier (e.g. PEN/2026/001)."
    )
    name = fields.Char(string='Pen Name', required=True, help="e.g. Pen 01")

    # === LINK TO FARM (replaces direct company_id input) ===
    farm_id = fields.Many2one(
        'taghini.farm', string='Farm', required=True,
        tracking=True,
        help="The farm this pen belongs to. The farm's warehouse drives all stock moves."
    )

    # Derived from farm — stored so other models can relate to them
    company_id = fields.Many2one(
        'res.company', string='Company',
        related='farm_id.company_id', store=True, readonly=True
    )
    warehouse_id = fields.Many2one(
        'stock.warehouse', string='Warehouse',
        related='farm_id.warehouse_id', store=True, readonly=True,
        help="Automatically set from the farm. Drives feed and medication stock moves."
    )

    # Staff — inherited from farm but overridable at pen level
    manager_id = fields.Many2one(
        'res.users', string='Farm Manager', tracking=True,
        domain="[('company_ids', 'in', company_id)]"
    )
    vet_id = fields.Many2one(
        'res.users', string='Veterinary Doctor', tracking=True,
        domain="[('company_ids', 'in', company_id)]"
    )

    # Specific pen location within the farm (e.g. House A, Block 2)
    location_id = fields.Many2one(
        'stock.location',
        string='Pen Stock Location',
        domain="[('usage', '=', 'internal')]",
        check_company=True,
        required=True,
        help="The specific inventory location for this pen (where birds live)."
    )

    # Housing & Equipment Specifications (Parent Stock & Broiler)
    housing_system = fields.Selection([
        ('open', 'Open-sided, Deep Litter'),
        ('closed', 'Closed / Climate Controlled'),
        ('slats', 'Slats & Litter'),
    ], default='open', string='Housing System', tracking=True)
    floor_area_m2 = fields.Float(string='Floor Area (m²)', default=1000.0)
    capacity = fields.Integer(
        string='Chicks Capacity (Max)',
        default=0,
        tracking=True,
        help="Maximum number of chicks / birds this pen can accommodate."
    )
    stocking_density = fields.Float(
        string='Stocking Density (birds/m²)',
        compute='_compute_stocking_density',
        store=True,
        digits=(16, 2),
        help="Estimated maximum bird stocking density per square meter."
    )
    female_feeder_space_cm = fields.Float(string='Female Feeder Space (cm/bird)', default=45.0)
    male_feeder_count = fields.Integer(string='Male Feeders (Qty)', default=30)
    drinker_count = fields.Integer(string='Drinkers (Qty)', default=78)
    nest_holes = fields.Integer(string='Nest Holes (Qty)', default=20)

    # Smart Button
    flock_ids = fields.One2many('taghini.flock', 'pen_model_id', string='Flocks')
    series_count = fields.Integer(compute='_compute_series_count')

    @api.depends('capacity', 'floor_area_m2')
    def _compute_stocking_density(self):
        for record in self:
            if record.floor_area_m2 and record.floor_area_m2 > 0 and record.capacity:
                record.stocking_density = record.capacity / record.floor_area_m2
            else:
                record.stocking_density = 0.0

    @api.depends('flock_ids')
    def _compute_series_count(self):
        for record in self:
            record.series_count = len(record.flock_ids)

    @api.onchange('farm_id')
    def _onchange_farm_id(self):
        """Auto-fill staff from farm when farm changes."""
        if self.farm_id:
            if not self.manager_id:
                self.manager_id = self.farm_id.manager_id
            if not self.vet_id:
                self.vet_id = self.farm_id.vet_id

    def action_view_flocks(self):
        """Smart Button to open related Flocks"""
        self.ensure_one()
        return {
            'name': _('Series in %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'taghini.flock',
            'view_mode': 'list,form',
            'domain': [('pen_model_id', '=', self.id)],
            'context': {
                'default_pen_model_id': self.id,
                'default_pen_id': self.location_id.id,
            },
        }

    def action_create_batch(self):
        """Shortcut button to create a new Batch in this Pen"""
        active_batch = self.env['taghini.flock'].search([
            ('pen_model_id', '=', self.id),
            ('state', '=', 'active')
        ], limit=1)

        if active_batch:
            raise UserError(_(
                "This Pen is already occupied!\n"
                "There is an active batch '%s' in this pen. "
                "You must close the current batch (Harvest/Finish) before starting a new one."
            ) % active_batch.name)

        self.ensure_one()
        return {
            'name': _('New Batch'),
            'type': 'ir.actions.act_window',
            'res_model': 'taghini.flock',
            'view_mode': 'form',
            'context': {
                'default_pen_model_id': self.id,
                'default_pen_id': self.location_id.id,
                'default_name': f"Batch - {self.name} - {fields.Date.today()}",
            },
        }

    # --- UNIQUE SEQUENCE ID & DISPLAY NAME ---
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('pen_code', 'New') == 'New' or not vals.get('pen_code'):
                vals['pen_code'] = self.env['ir.sequence'].next_by_code('taghini.pen') or 'New'
        return super().create(vals_list)

    def _compute_display_name(self):
        for record in self:
            code = record.pen_code
            name = record.name
            if code and code != 'New' and name and name != code:
                record.display_name = f"[{code}] {name}"
            else:
                record.display_name = name or code or _('New')

    def init(self):
        super().init()
        # Backfill farm_id on legacy pens so PostgreSQL NOT NULL constraint succeeds
        self.env.cr.execute("""
            UPDATE taghini_pen
            SET farm_id = (SELECT id FROM taghini_farm ORDER BY id LIMIT 1)
            WHERE farm_id IS NULL AND EXISTS (SELECT 1 FROM taghini_farm);
        """)
        pens_without_code = self.search([
            '|', ('pen_code', '=', False), ('pen_code', '=', 'New')
        ], order='id asc')
        for pen in pens_without_code:
            seq_val = self.env['ir.sequence'].next_by_code('taghini.pen')
            pen.pen_code = seq_val or f"PEN/{pen.id:03d}"
