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
    
    # The total birds bought / transferred
    total_quantity = fields.Integer(string='Total Purchased Qty', required=True, tracking=True)

    # Link back to stock picking if generated from an internal transfer
    picking_id = fields.Many2one('stock.picking', string='Source Internal Transfer', readonly=True)
    
    # Smart fields to track usage across pens
    series_ids = fields.One2many('taghini.flock', 'batch_id', string='Pen Series')
    allocated_quantity = fields.Integer(string='Allocated Qty', compute='_compute_allocation', store=True)
    remaining_quantity = fields.Integer(string='Remaining Qty', compute='_compute_allocation', store=True)
    allocation_status = fields.Selection([
        ('unallocated', 'Unallocated'),
        ('partial', 'Partially Allocated'),
        ('full', 'Fully Allocated'),
        ('over', 'Over Allocated'),
    ], string='Allocation Status', compute='_compute_allocation', store=True, default='unallocated')

    farm_id = fields.Many2one('taghini.farm', string='Farm', compute='_compute_batch_stats', store=True)
    flock_count = fields.Integer(string='Flocks / Pens', compute='_compute_batch_stats', store=True)
    current_live_birds = fields.Integer(string='Current Live', compute='_compute_batch_stats', store=True)
    mortality_birds = fields.Integer(string='Dead Birds', compute='_compute_batch_stats', store=True)
    mortality_rate = fields.Float(string='Mortality %', compute='_compute_batch_stats', store=True)

    @api.depends('total_quantity', 'series_ids.quantity_placed')
    def _compute_allocation(self):
        for record in self:
            allocated = sum(record.series_ids.mapped('quantity_placed'))
            record.allocated_quantity = allocated
            record.remaining_quantity = record.total_quantity - allocated
            if record.total_quantity <= 0 or allocated <= 0:
                record.allocation_status = 'unallocated'
            elif allocated < record.total_quantity:
                record.allocation_status = 'partial'
            elif allocated == record.total_quantity:
                record.allocation_status = 'full'
            else:
                record.allocation_status = 'over'

    @api.depends('series_ids', 'series_ids.farm_id', 'series_ids.current_birds', 'series_ids.total_mortality', 'allocated_quantity', 'picking_id')
    def _compute_batch_stats(self):
        for record in self:
            farm = False
            if record.series_ids:
                farm = record.series_ids[0].farm_id
            elif record.picking_id:
                wh = record.picking_id.picking_type_id.warehouse_id or record.picking_id.location_dest_id.warehouse_id
                if wh:
                    farm = self.env['taghini.farm'].search([('warehouse_id', '=', wh.id)], limit=1)
            record.farm_id = farm
            record.flock_count = len(record.series_ids)
            live = sum(record.series_ids.mapped('current_birds'))
            dead = sum(record.series_ids.mapped('total_mortality'))
            record.current_live_birds = live
            record.mortality_birds = dead
            placed = record.allocated_quantity
            record.mortality_rate = (dead / placed) if placed > 0 else 0.0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('taghini.chicken.batch') or 'New'
        return super().create(vals_list)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    chicken_batch_ids = fields.One2many(
        'taghini.chicken.batch', 'picking_id',
        string='Purchased Batches',
        readonly=True
    )
    chicken_batch_count = fields.Integer(
        string='Chicken Batches Count',
        compute='_compute_chicken_batch_count'
    )
    breeder_batch_ids = fields.One2many(
        'taghini.breeder.batch', 'picking_id',
        string='Breeder Batches',
        readonly=True
    )
    breeder_batch_count = fields.Integer(
        string='Breeder Batches Count',
        compute='_compute_breeder_batch_count'
    )

    @api.depends('chicken_batch_ids')
    def _compute_chicken_batch_count(self):
        for picking in self:
            picking.chicken_batch_count = len(picking.chicken_batch_ids)

    @api.depends('breeder_batch_ids')
    def _compute_breeder_batch_count(self):
        for picking in self:
            picking.breeder_batch_count = len(picking.breeder_batch_ids)

    def _action_done(self):
        """
        When an internal transfer (picking_type_code == 'internal') is validated:
        - If products are breeder birds or destination is a breeding farm:
          create taghini.breeder.batch in DRAFT state so bonus/gift quantities can be adjusted.
        - If products are commercial broilers:
          create taghini.chicken.batch (standard broiler purchase batch).
        """
        res = super()._action_done()

        for picking in self:
            # Check if this is an internal transfer or direct intake (vendor receipt / inventory)
            is_intake = (
                picking.picking_type_code in ('internal', 'incoming') or
                (picking.location_dest_id.usage == 'internal')
            )
            if not is_intake:
                continue

            # Identify destination warehouse & farm
            dest_wh = picking.picking_type_id.warehouse_id or picking.location_dest_id.warehouse_id
            dest_farm = self.env['taghini.farm'].search([('warehouse_id', '=', dest_wh.id)], limit=1) if dest_wh else False

            # Check for bird variant moves
            bird_moves = picking.move_ids.filtered(
                lambda m: m.state == 'done' and (
                    m.product_id.product_tmpl_id.bird_variant or
                    m.product_id.bird_variant
                )
            )
            if not bird_moves:
                continue

            # Determine supplier or fallback partner
            supplier = picking.partner_id
            if not supplier:
                supplier = picking.company_id.partner_id or self.env.user.company_id.partner_id

            # Discriminate Breeder moves vs Broiler moves
            breeder_moves = bird_moves.filtered(
                lambda m: (
                    getattr(m.product_id.product_tmpl_id, 'bird_flow', False) == 'breeder' or
                    (dest_farm and dest_farm.farm_type == 'breeder')
                )
            )
            broiler_moves = bird_moves - breeder_moves

            # 1. Handle Breeder Stock Transfer -> Create Breeder Batch in DRAFT
            if breeder_moves and not picking.breeder_batch_ids:
                female_moves = breeder_moves.filtered(
                    lambda m: getattr(m.product_id.product_tmpl_id, 'bird_sex', False) == 'female'
                )
                male_moves = breeder_moves.filtered(
                    lambda m: getattr(m.product_id.product_tmpl_id, 'bird_sex', False) == 'male'
                )

                if female_moves or male_moves:
                    female_qty = sum(
                        (m.quantity if hasattr(m, 'quantity') else m.quantity_done) or m.product_uom_qty
                        for m in female_moves
                    )
                    male_qty = sum(
                        (m.quantity if hasattr(m, 'quantity') else m.quantity_done) or m.product_uom_qty
                        for m in male_moves
                    )
                    primary_prod = female_moves[0].product_id if female_moves else male_moves[0].product_id
                else:
                    total_breeder_qty = sum(
                        (m.quantity if hasattr(m, 'quantity') else m.quantity_done) or m.product_uom_qty
                        for m in breeder_moves
                    )
                    female_qty = total_breeder_qty
                    male_qty = 0
                    primary_prod = breeder_moves[0].product_id

                if (female_qty + male_qty) > 0:
                    breeder_std = self.env['taghini.farm.standard'].search([('standard_type', '=', 'breeder')], limit=1)

                    batch_vals = {
                        'date': picking.date_done.date() if picking.date_done else fields.Date.context_today(picking),
                        'farm_id': dest_farm.id if dest_farm else False,
                        'source_type': 'farm' if picking.location_id.usage == 'internal' else 'hatchery',
                        'source_partner_id': supplier.id,
                        'source_reference': picking.name,
                        'bird_variant_id': primary_prod.product_tmpl_id.id,
                        'standard_id': breeder_std.id if breeder_std else False,
                        'female_order_qty': int(female_qty),
                        'gift_male_qty': 0,
                        'gift_female_qty': 0,
                        'picking_id': picking.id,
                        'state': 'draft',
                    }
                    if male_qty > 0:
                        batch_vals['male_order_qty'] = int(male_qty)

                    self.env['taghini.breeder.batch'].create(batch_vals)

            # 2. Handle Broiler Stock Transfer -> Create Broiler Batch
            if broiler_moves and not picking.chicken_batch_ids:
                total_broiler_qty = sum(
                    (m.quantity if hasattr(m, 'quantity') else m.quantity_done) or m.product_uom_qty
                    for m in broiler_moves
                )
                if total_broiler_qty > 0:
                    self.env['taghini.chicken.batch'].create({
                        'date': picking.date_done.date() if picking.date_done else fields.Date.context_today(picking),
                        'supplier_id': supplier.id,
                        'total_quantity': int(total_broiler_qty),
                        'picking_id': picking.id,
                    })

        return res
