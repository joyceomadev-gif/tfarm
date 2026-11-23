from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class BreederFlock(models.Model):
    _name = 'taghini.breeder.flock'
    _description = 'Breeder Pen Series'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc, start_date desc'

    name = fields.Char(
        string='Pen Series ID',
        readonly=True,
        copy=False,
        default='New',
        index=True,
        help="Unique sequence-generated breeder flock identifier."
    )
    batch_id = fields.Many2one(
        'taghini.breeder.batch',
        string='Mother Batch',
        required=True,
        ondelete='restrict',
        tracking=True
    )
    pen_id = fields.Many2one(
        'taghini.pen',
        string='Pen / House',
        required=True,
        ondelete='restrict',
        tracking=True
    )
    farm_id = fields.Many2one(
        'taghini.farm',
        string='Farm',
        related='pen_id.farm_id',
        store=True,
        readonly=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='batch_id.company_id',
        store=True,
        readonly=True
    )

    start_date = fields.Date(
        string='Placement Date',
        default=fields.Date.context_today,
        required=True,
        tracking=True
    )
    batch_farm_id = fields.Many2one('taghini.farm', related='batch_id.farm_id', string='Batch Farm', readonly=True)
    available_batch_females = fields.Integer(related='batch_id.remaining_female_qty', string='Available Batch Females', readonly=True)
    available_batch_males = fields.Integer(related='batch_id.remaining_male_qty', string='Available Batch Males', readonly=True)
    initial_females = fields.Integer(string='Initial Females Placed', required=True, default=0, tracking=True)
    initial_males = fields.Integer(string='Initial Males Placed', required=True, default=0, tracking=True)
    total_initial_placed = fields.Integer(
        string='Total Chicks Placed',
        compute='_compute_total_initial_placed',
        store=True,
        help="Total chicks (females + males) allocated to this pen."
    )
    pen_capacity = fields.Integer(
        related='pen_id.capacity',
        string='Pen Capacity',
        readonly=True,
        help="Accommodation limit of the assigned pen."
    )
    laying_started = fields.Boolean(
        string='Laying Phase Active',
        default=False,
        tracking=True,
        help="Indicates whether egg production has commenced for this flock. Automatically enabled when age reaches 24 weeks or can be manually toggled."
    )

    current_females = fields.Integer(string='Current Females Alive', compute='_compute_counts', store=True)
    current_males = fields.Integer(string='Current Males Alive', compute='_compute_counts', store=True)
    males_per_100_females = fields.Float(string='Males per 100 Females', compute='_compute_counts', store=True)

    lifecycle_phase = fields.Selection([
        ('brooding', 'Brooding (Wk 0-3)'),
        ('rearing', 'Rearing (Wk 4-20)'),
        ('pre_lay', 'Pre-Lay (Wk 21-23)'),
        ('lay', 'Laying (Wk 24-64+)'),
    ], string='Lifecycle Phase', compute='_compute_phase', store=True)

    # Housing & Equipment Specifications (Inherited from Pen)
    housing_system = fields.Selection(related='pen_id.housing_system', string='Housing System', readonly=True)
    floor_area_m2 = fields.Float(related='pen_id.floor_area_m2', string='Floor Area (m²)', readonly=True)
    female_feeder_space_cm = fields.Float(related='pen_id.female_feeder_space_cm', string='Female Feeder Space (cm)', readonly=True)
    male_feeder_count = fields.Integer(related='pen_id.male_feeder_count', string='Male Feeders', readonly=True)
    drinker_count = fields.Integer(related='pen_id.drinker_count', string='Drinkers', readonly=True)
    nest_holes = fields.Integer(related='pen_id.nest_holes', string='Nest Holes', readonly=True)

    # Cumulative Production & Performance Totals
    total_mortality_female = fields.Integer(string='Total Female Mortality', compute='_compute_production_totals', store=True)
    total_mortality_male = fields.Integer(string='Total Male Mortality', compute='_compute_production_totals', store=True)
    total_mortality = fields.Integer(string='Total Mortality', compute='_compute_production_totals', store=True)
    total_eggs_collected = fields.Integer(string='Total Eggs Collected', compute='_compute_production_totals', store=True)
    total_hatching_eggs = fields.Integer(string='Total Hatching Eggs', compute='_compute_production_totals', store=True)
    hatching_egg_pct = fields.Float(string='Hatching Egg %', compute='_compute_production_totals', store=True, digits=(16, 4))

    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('closed', 'Closed / Depopulated'),
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True, tracking=True)

    pen_log_ids = fields.One2many('taghini.breeder.pen.log', 'flock_id', string='Pen Daily Logs')
    pen_log_count = fields.Integer(string='Daily Logs Count', compute='_compute_pen_log_count')

    @api.depends('pen_log_ids')
    def _compute_pen_log_count(self):
        for rec in self:
            rec.pen_log_count = len(rec.pen_log_ids)

    def action_export_111_col_excel(self):
        self.ensure_one()
        from ..wizard.breeder_excel_export_wizard import generate_111_col_excel_workbook
        import base64
        from datetime import datetime, date
        logs = self.pen_log_ids.sorted(key=lambda r: (r.date or date.min, r.id))
        if not logs:
            raise UserError(_("No daily operations logs found for flock %s.") % self.name)

        title = f"{self.name} - {self.pen_id.name}"
        file_bytes = generate_111_col_excel_workbook(self.env, logs, title_prefix=title)
        b64_data = base64.b64encode(file_bytes)
        filename = f"Ledger_111Col_{self.name.replace('/', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
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

    def action_view_pen_logs(self):
        self.ensure_one()
        return {
            'name': _("Daily Logs: %s") % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'taghini.breeder.pen.log',
            'view_mode': 'list,form',
            'domain': [('flock_id', '=', self.id)],
            'context': {
                'default_flock_id': self.id,
            },
        }

    def action_create_daily_log(self):
        self.ensure_one()
        if self.state != 'active':
            raise ValidationError(_("Daily operations can only be recorded on an Active Breeder Pen Series. Flock '%s' is in status '%s'. Please activate it first.") % (self.name, self.state))

        from datetime import timedelta
        latest_log = self.pen_log_ids.sorted('date', reverse=True)
        today = fields.Date.context_today(self)
        if latest_log:
            next_date = latest_log[0].date + timedelta(days=1)
        else:
            next_date = self.start_date or today

        return {
            'name': _("Log Daily Operations: %s") % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'taghini.breeder.pen.log',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
            'context': {
                'default_flock_id': self.id,
                'default_date': next_date,
            },
        }

    @api.depends(
        'pen_log_ids.female_mortality', 'pen_log_ids.male_mortality',
        'pen_log_ids.total_eggs_collected', 'pen_log_ids.hatching_eggs'
    )
    def _compute_production_totals(self):
        for rec in self:
            rec.total_mortality_female = sum(rec.pen_log_ids.mapped('female_mortality'))
            rec.total_mortality_male = sum(rec.pen_log_ids.mapped('male_mortality'))
            rec.total_mortality = rec.total_mortality_female + rec.total_mortality_male
            rec.total_eggs_collected = sum(rec.pen_log_ids.mapped('total_eggs_collected'))
            rec.total_hatching_eggs = sum(rec.pen_log_ids.mapped('hatching_eggs'))
            if rec.total_eggs_collected > 0:
                rec.hatching_egg_pct = (rec.total_hatching_eggs / rec.total_eggs_collected)
            else:
                rec.hatching_egg_pct = 0.0

    @api.onchange('batch_id')
    def _onchange_batch_id(self):
        if self.batch_id:
            if not self.start_date and self.batch_id.date:
                self.start_date = self.batch_id.date
            if not self.initial_females and self.batch_id.remaining_female_qty > 0:
                self.initial_females = self.batch_id.remaining_female_qty
            if not self.initial_males and self.batch_id.remaining_male_qty > 0:
                self.initial_males = self.batch_id.remaining_male_qty

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New' or not vals.get('name'):
                vals['name'] = self.env['ir.sequence'].next_by_code('taghini.breeder.flock') or 'New'
        return super().create(vals_list)

    @api.depends('initial_females', 'initial_males', 'pen_log_ids.closing_females', 'pen_log_ids.closing_males')
    def _compute_counts(self):
        for rec in self:
            latest_log = rec.pen_log_ids.sorted('date', reverse=True)
            if latest_log:
                rec.current_females = latest_log[0].closing_females
                rec.current_males = latest_log[0].closing_males
            else:
                rec.current_females = rec.initial_females
                rec.current_males = rec.initial_males

            if rec.current_females > 0:
                rec.males_per_100_females = round((rec.current_males / rec.current_females) * 100.0, 2)
            else:
                rec.males_per_100_females = 0.0

    @api.depends('initial_females', 'initial_males')
    def _compute_total_initial_placed(self):
        for rec in self:
            rec.total_initial_placed = rec.initial_females + rec.initial_males

    @api.depends('start_date', 'pen_log_ids.date')
    def _compute_phase(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if not rec.start_date:
                rec.lifecycle_phase = 'brooding'
                continue
            last_date = max(rec.pen_log_ids.mapped('date')) if rec.pen_log_ids else today
            ref_date = max(today, last_date)
            days = (ref_date - rec.start_date).days
            weeks = max(days // 7, 0)
            if weeks <= 3:
                rec.lifecycle_phase = 'brooding'
            elif weeks <= 20:
                rec.lifecycle_phase = 'rearing'
            elif weeks <= 23:
                rec.lifecycle_phase = 'pre_lay'
            else:
                rec.lifecycle_phase = 'lay'
                if not rec.laying_started:
                    rec.laying_started = True

    @api.onchange('pen_id', 'initial_females', 'initial_males')
    def _onchange_check_pen_capacity_warning(self):
        if self.pen_id and self.pen_id.capacity > 0:
            total = (self.initial_females or 0) + (self.initial_males or 0)
            if total > self.pen_id.capacity:
                return {
                    'warning': {
                        'title': _("Over-Capacity Warning"),
                        'message': _(
                            "Pen '%(pen)s' has a maximum accommodation capacity of %(cap)s chicks.\n"
                            "Current allocation is %(total)s (%(excess)s over capacity)."
                        ) % {
                            'pen': self.pen_id.name,
                            'cap': f"{self.pen_id.capacity:,}",
                            'total': f"{total:,}",
                            'excess': f"{(total - self.pen_id.capacity):,}",
                        }
                    }
                }

    @api.constrains('initial_females', 'initial_males', 'pen_id')
    def _check_pen_capacity(self):
        for rec in self:
            if rec.pen_id and rec.pen_id.capacity > 0:
                total = rec.initial_females + rec.initial_males
                if total > rec.pen_id.capacity:
                    raise ValidationError(_(
                        "Allocation Exceeds Pen Accommodation Capacity!\n\n"
                        "Pen '%(pen)s' can accommodate at most %(cap)s chicks.\n"
                        "You are attempting to allocate %(total)s chicks (%(females)s females + %(males)s males).\n"
                        "This exceeds pen capacity by %(excess)s birds."
                    ) % {
                        'pen': rec.pen_id.display_name or rec.pen_id.name,
                        'cap': f"{rec.pen_id.capacity:,}",
                        'total': f"{total:,}",
                        'females': f"{rec.initial_females:,}",
                        'males': f"{rec.initial_males:,}",
                        'excess': f"{(total - rec.pen_id.capacity):,}",
                    })

    @api.constrains('initial_females', 'initial_males', 'batch_id')
    def _check_batch_quantities(self):
        for rec in self:
            if not rec.batch_id:
                continue
            other_flocks = self.search([
                ('batch_id', '=', rec.batch_id.id),
                ('id', '!=', rec.id)
            ])
            total_f = sum(other_flocks.mapped('initial_females')) + rec.initial_females
            total_m = sum(other_flocks.mapped('initial_males')) + rec.initial_males
            if rec.batch_id.stocked_female_qty and total_f > rec.batch_id.stocked_female_qty:
                raise ValidationError(
                    _("Total allocated females (%d) exceed Mother Batch stocked females (%d).")
                    % (total_f, rec.batch_id.stocked_female_qty)
                )
            if rec.batch_id.stocked_male_qty and total_m > rec.batch_id.stocked_male_qty:
                raise ValidationError(
                    _("Total allocated males (%d) exceed Mother Batch stocked males (%d).")
                    % (total_m, rec.batch_id.stocked_male_qty)
                )

    @api.constrains('pen_id', 'state')
    def _check_pen_occupancy(self):
        for rec in self:
            if rec.state == 'active':
                conflict_breeder = self.search([
                    ('pen_id', '=', rec.pen_id.id),
                    ('state', '=', 'active'),
                    ('id', '!=', rec.id)
                ], limit=1)
                conflict_broiler = self.env['taghini.flock'].search([
                    ('pen_model_id', '=', rec.pen_id.id),
                    ('state', '=', 'active')
                ], limit=1)
                if conflict_breeder or conflict_broiler:
                    raise ValidationError(_("Pen '%s' is already occupied by an active flock.") % rec.pen_id.name)

    def action_activate(self):
        self._check_pen_occupancy()
        self.write({'state': 'active'})

    def action_close(self):
        self.write({'state': 'closed'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})
