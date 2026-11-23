from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class BreederBatch(models.Model):
    _name = 'taghini.breeder.batch'
    _description = 'Breeder Stock Batch'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'

    name = fields.Char(string='Batch Reference', required=True, copy=False, readonly=True, default='New')
    date = fields.Date(string='Received Date', default=fields.Date.context_today, required=True)
    company_id = fields.Many2one('res.company', string='Farm / Branch', default=lambda self: self.env.company, required=True)

    source_type = fields.Selection([
        ('hatchery', 'Hatchery'),
        ('farm', 'Own Farm'),
    ], string='Source Type', default='hatchery', required=True, tracking=True)
    source_partner_id = fields.Many2one('res.partner', string='Source Hatchery / Farm', required=True)
    source_reference = fields.Char(string='Source Reference / Invoice')

    farm_id = fields.Many2one(
        'taghini.farm',
        string='Breeder Farm Site',
        domain="[('farm_type', 'in', ('breeder', 'mixed'))]",
        tracking=True,
        help="The destination breeder farm site receiving this parent stock."
    )
    picking_id = fields.Many2one(
        'stock.picking',
        string='Source Internal Transfer',
        readonly=True,
        help="The internal stock transfer from main warehouse to this breeding farm."
    )

    bird_variant_id = fields.Many2one(
        'product.template',
        string='Bird Variant',
        required=True,
        domain="[('bird_variant', '=', True)]",
        tracking=True,
    )
    standard_id = fields.Many2one(
        'taghini.farm.standard',
        string='Breed & Performance Standard',
        domain="[('standard_type', '=', 'breeder')]",
        required=True
    )

    # Batch Level Setup & Facility
    housing_system = fields.Selection([
        ('open', 'Open-sided, Deep Litter'),
        ('closed', 'Closed / Climate Controlled'),
        ('slats', 'Slats & Litter')
    ], default='open', string='Housing System')
    hatchery_partner_id = fields.Many2one('res.partner', string='Receiving Hatchery')
    senior_farm_officer = fields.Char(string='Senior Farm Officer')
    vet_id = fields.Many2one('res.users', string='Responsible Veterinarian')
    feed_bag_weight_kg = fields.Float(string='Feed Bag Weight (kg)', default=25.0)
    photostim_week = fields.Integer(string='Photostimulation Week', default=24)

    # 19 Configurable Alert Thresholds (from SETUP tab)
    t_mf_d = fields.Float('Female Daily Mort % (Wk 2+)', default=0.0003, digits=(16, 5))      # 0.03%
    t_mf_db = fields.Float('Female Daily Mort % (Wk 0-1)', default=0.003, digits=(16, 5))    # 0.30%
    t_mm_d = fields.Float('Male Daily Mort % (Wk 2+)', default=0.0001, digits=(16, 5))        # 0.01%
    t_mm_db = fields.Float('Male Daily Mort % (Wk 0-1)', default=0.003, digits=(16, 5))      # 0.30%
    t_mm_min = fields.Integer('Min Male Deaths Before Flag', default=2)
    t_feedvar = fields.Float('Feed Allocation Variance (±%)', default=0.03, digits=(16, 4))   # ±3%
    t_wf_lo = fields.Float('Water:Feed Ratio Low', default=1.5)
    t_wf_hi = fields.Float('Water:Feed Ratio High', default=2.5)
    t_wdrop = fields.Float('Day-on-Day Water Fall %', default=0.05, digits=(16, 4))           # 5% drop
    t_tmax = fields.Float('Max House Temp (°C)', default=30.0)
    t_tmin_brood = fields.Float('Min Brood Temp (°C)', default=26.0)
    t_litter = fields.Integer('Litter Score Alert (1-5)', default=3)
    t_light_tol = fields.Float('Photoperiod Drift Tolerance (Hrs)', default=0.25)
    t_mating_lo = fields.Float('Min Males per 100 Females', default=10.0)
    t_mating_hi = fields.Float('Max Males per 100 Females', default=12.0)
    t_bw_dev = fields.Float('Body Weight Dev Alert (±%)', default=0.05, digits=(16, 4))       # ±5%
    t_uniformity_min = fields.Float('Min Flock Uniformity %', default=80.0)
    t_egg_wt_dev = fields.Float('Egg Weight Dev Alert (±g)', default=2.0)
    t_dispatch_interval = fields.Integer('Max Days Between Dispatches', default=7)

    # DOC Intake Quantities
    female_order_qty = fields.Integer(string='Ordered Female DOCs', required=True, tracking=True)
    male_order_qty = fields.Integer(string='Ordered Male DOCs', compute='_compute_order_qty', store=True, readonly=False)
    gift_total_qty = fields.Integer(string='Gift Qty', compute='_compute_gift_qty', store=True)
    gift_male_qty = fields.Integer(string='Gift Male Qty')
    gift_female_qty = fields.Integer(string='Gift Female Qty')

    shipped_male_qty = fields.Integer(string='Shipped Male Qty', compute='_compute_shipped_qty', store=True)
    shipped_female_qty = fields.Integer(string='Shipped Female Qty', compute='_compute_shipped_qty', store=True)

    transit_male_mortality = fields.Integer(string='In-Transit Male Mortality')
    transit_female_mortality = fields.Integer(string='In-Transit Female Mortality')
    premise_male_mortality = fields.Integer(string='On-Premise Male Mortality')
    premise_female_mortality = fields.Integer(string='On-Premise Female Mortality')

    stocked_male_qty = fields.Integer(string='Final Stocked Male Qty', compute='_compute_stocked_qty', store=True)
    stocked_female_qty = fields.Integer(string='Final Stocked Female Qty', compute='_compute_stocked_qty', store=True)
    stocked_total_qty = fields.Integer(string='Final Day-One Qty', compute='_compute_stocked_qty', store=True)

    male_section_qty = fields.Integer(string='Male Section Qty')
    female_section_qty = fields.Integer(string='Female Section Qty')
    introduced_male_qty = fields.Integer(string='Introduced Male Qty')
    introduced_female_qty = fields.Integer(string='Introduced Female Qty')

    egg_production_qty = fields.Integer(string='Egg Production Qty')
    current_state_note = fields.Char(string='Current Stage Note')

    # Pen Allocations & Live Roll-up Statistics
    flock_ids = fields.One2many('taghini.breeder.flock', 'batch_id', string='Pen Allocations')
    flock_count = fields.Integer(compute='_compute_flock_count', string='Pen Series Count')
    allocated_female_qty = fields.Integer(string='Allocated Females', compute='_compute_allocations', store=True)
    remaining_female_qty = fields.Integer(string='Unallocated Females', compute='_compute_allocations', store=True)
    allocated_male_qty = fields.Integer(string='Allocated Males', compute='_compute_allocations', store=True)
    remaining_male_qty = fields.Integer(string='Unallocated Males', compute='_compute_allocations', store=True)

    # Roll-up Metrics across all constituent Pen Series
    total_current_females = fields.Integer(string='Current Live Females', compute='_compute_batch_flock_stats', store=True)
    total_current_males = fields.Integer(string='Current Live Males', compute='_compute_batch_flock_stats', store=True)
    total_current_birds = fields.Integer(string='Total Live Birds', compute='_compute_batch_flock_stats', store=True)
    total_mortality_female = fields.Integer(string='Female Mortality (Pens)', compute='_compute_batch_flock_stats', store=True)
    total_mortality_male = fields.Integer(string='Male Mortality (Pens)', compute='_compute_batch_flock_stats', store=True)
    total_mortality_birds = fields.Integer(string='Total Mortalities', compute='_compute_batch_flock_stats', store=True)
    mortality_rate = fields.Float(string='Mortality Rate %', compute='_compute_batch_flock_stats', store=True, digits=(16, 4))
    total_eggs_collected = fields.Integer(string='Total Eggs Harvested', compute='_compute_batch_flock_stats', store=True)
    pen_log_count = fields.Integer(string='Daily Pen Logs Count', compute='_compute_pen_log_count')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('received', 'Received'),
        ('sorted', 'Sorted'),
        ('mating', 'Mating / Introduced'),
        ('laying', 'Laying'),
        ('harvested', 'Harvested / Sent to Abattoir'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', required=True, tracking=True)

    @api.depends('female_order_qty')
    def _compute_order_qty(self):
        for record in self:
            if not record.male_order_qty:
                record.male_order_qty = int(round((record.female_order_qty or 0) * 0.12))

    @api.depends('male_order_qty', 'female_order_qty', 'gift_male_qty', 'gift_female_qty')
    def _compute_shipped_qty(self):
        for record in self:
            record.shipped_male_qty = (record.male_order_qty or 0) + (record.gift_male_qty or 0)
            record.shipped_female_qty = (record.female_order_qty or 0) + (record.gift_female_qty or 0)

    @api.depends('gift_male_qty', 'gift_female_qty')
    def _compute_gift_qty(self):
        for record in self:
            record.gift_total_qty = (record.gift_male_qty or 0) + (record.gift_female_qty or 0)

    @api.depends(
        'shipped_male_qty', 'shipped_female_qty',
        'transit_male_mortality', 'transit_female_mortality',
        'premise_male_mortality', 'premise_female_mortality',
    )
    def _compute_stocked_qty(self):
        for record in self:
            male_total = (record.shipped_male_qty or 0) - (record.transit_male_mortality or 0) - (record.premise_male_mortality or 0)
            female_total = (record.shipped_female_qty or 0) - (record.transit_female_mortality or 0) - (record.premise_female_mortality or 0)
            record.stocked_male_qty = max(male_total, 0)
            record.stocked_female_qty = max(female_total, 0)
            record.stocked_total_qty = record.stocked_male_qty + record.stocked_female_qty

    @api.depends('flock_ids', 'flock_ids.initial_females', 'flock_ids.initial_males', 'stocked_female_qty', 'stocked_male_qty')
    def _compute_allocations(self):
        for record in self:
            record.allocated_female_qty = sum(record.flock_ids.mapped('initial_females'))
            record.remaining_female_qty = (record.stocked_female_qty or 0) - record.allocated_female_qty
            record.allocated_male_qty = sum(record.flock_ids.mapped('initial_males'))
            record.remaining_male_qty = (record.stocked_male_qty or 0) - record.allocated_male_qty

    @api.depends('flock_ids')
    def _compute_flock_count(self):
        for record in self:
            record.flock_count = len(record.flock_ids)

    @api.depends(
        'flock_ids.current_females', 'flock_ids.current_males',
        'flock_ids.pen_log_ids.female_mortality', 'flock_ids.pen_log_ids.male_mortality',
        'flock_ids.pen_log_ids.total_eggs_collected', 'stocked_total_qty'
    )
    def _compute_batch_flock_stats(self):
        for record in self:
            live_f = sum(record.flock_ids.mapped('current_females'))
            live_m = sum(record.flock_ids.mapped('current_males'))
            record.total_current_females = live_f
            record.total_current_males = live_m
            record.total_current_birds = live_f + live_m

            logs = record.flock_ids.mapped('pen_log_ids')
            f_mort = sum(logs.mapped('female_mortality'))
            m_mort = sum(logs.mapped('male_mortality'))
            record.total_mortality_female = f_mort
            record.total_mortality_male = m_mort
            record.total_mortality_birds = f_mort + m_mort

            total_stocked = record.stocked_total_qty or 1
            record.mortality_rate = (record.total_mortality_birds / total_stocked) if total_stocked > 0 else 0.0
            record.total_eggs_collected = sum(logs.mapped('total_eggs_collected'))

    @api.depends('flock_ids.pen_log_ids')
    def _compute_pen_log_count(self):
        for record in self:
            record.pen_log_count = len(record.flock_ids.mapped('pen_log_ids'))

    def action_create_flock(self):
        self.ensure_one()
        if self.state in ('closed', 'cancelled'):
            raise UserError(_("Cannot allocate pen series from a closed or cancelled batch."))

        suggested_f = max(self.remaining_female_qty, 0)
        suggested_m = max(self.remaining_male_qty, 0)

        return {
            'name': _("Allocate Pen Series: %s") % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'taghini.breeder.flock',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
            'context': {
                'default_batch_id': self.id,
                'default_start_date': self.date or fields.Date.context_today(self),
                'default_initial_females': suggested_f,
                'default_initial_males': suggested_m,
            },
        }

    def action_export_111_col_excel(self):
        self.ensure_one()
        from ..wizard.breeder_excel_export_wizard import generate_111_col_excel_workbook
        import base64
        from datetime import datetime, date
        logs = self.flock_ids.mapped('pen_log_ids').sorted(key=lambda r: (r.date or date.min, r.id))
        if not logs:
            raise UserError(_("No daily operations logs found for Mother Batch %s.") % self.name)

        title = f"Mother Batch {self.name}"
        file_bytes = generate_111_col_excel_workbook(self.env, logs, title_prefix=title)
        b64_data = base64.b64encode(file_bytes)
        filename = f"Ledger_111Col_Batch_{self.name.replace('/', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'datas': b64_data,
            'type': 'binary',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    def action_view_flocks(self):
        self.ensure_one()
        return {
            'name': _("Pen Series: %s") % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'taghini.breeder.flock',
            'view_mode': 'list,form',
            'domain': [('batch_id', '=', self.id)],
            'context': {
                'default_batch_id': self.id,
                'default_farm_id': self.farm_id.id if self.farm_id else False,
            },
        }

    def action_view_pen_logs(self):
        self.ensure_one()
        flock_ids = self.flock_ids.ids
        return {
            'name': _("Daily Pen Logs: %s") % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'taghini.breeder.pen.log',
            'view_mode': 'list,form',
            'domain': [('flock_id', 'in', flock_ids)],
            'context': {
                'search_default_group_flock': 1,
            },
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('taghini.breeder.batch') or 'New'
        return super().create(vals_list)

    def action_mark_received(self):
        self.write({'state': 'received'})

    def action_mark_sorted(self):
        self.write({'state': 'sorted'})

    def action_mark_mating(self):
        self.write({'state': 'mating'})

    def action_mark_laying(self):
        self.write({'state': 'laying'})

    def action_mark_harvested(self):
        self.write({'state': 'harvested'})

    def action_close_batch(self):
        self.write({'state': 'closed'})

    def action_cancel_batch(self):
        self.write({'state': 'cancelled'})

