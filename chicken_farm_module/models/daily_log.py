from odoo import models, fields, api, _
from odoo.exceptions import UserError

class FarmDailyLog(models.Model):
    _name = 'taghini.daily.log'
    _description = 'Daily Farm Log'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Daily Log ID',
        readonly=True,
        copy=False,
        default='New',
        index=True,
        help="Unique system sequence generated log identifier (e.g. LOG/2026/00001)."
    )

    @api.model
    def _register_hook(self):
        super()._register_hook()
        # Fail-Safe Schema Protection: Ensure stored columns exist in PostgreSQL
        # Even if Odoo is started without -u or if migration is pending, this guarantees
        # that ORM queries will never crash with psycopg2.errors.UndefinedColumn.
        try:
            self.env.cr.execute("""
                ALTER TABLE taghini_daily_log 
                    ADD COLUMN IF NOT EXISTS feed_product_id integer REFERENCES product_product(id) ON DELETE SET NULL,
                    ADD COLUMN IF NOT EXISTS farm_id integer REFERENCES taghini_farm(id) ON DELETE SET NULL,
                    ADD COLUMN IF NOT EXISTS warehouse_id integer REFERENCES stock_warehouse(id) ON DELETE SET NULL,
                    ADD COLUMN IF NOT EXISTS name varchar,
                    ADD COLUMN IF NOT EXISTS has_escalated_remarks boolean DEFAULT false,
                    ADD COLUMN IF NOT EXISTS vet_notified boolean DEFAULT false;

                ALTER TABLE taghini_flock 
                    ADD COLUMN IF NOT EXISTS warehouse_id integer REFERENCES stock_warehouse(id) ON DELETE SET NULL,
                    ADD COLUMN IF NOT EXISTS pen_model_id integer REFERENCES taghini_pen(id) ON DELETE SET NULL,
                    ADD COLUMN IF NOT EXISTS batch_id integer REFERENCES taghini_chicken_batch(id) ON DELETE SET NULL;
            """)
        except Exception:
            pass

        # Auto-Migration Detection Rule:
        # Check if the installed version in DB is behind the manifest version
        try:
            self._check_and_trigger_migration_rule()
        except Exception:
            pass

    @api.model
    def _check_and_trigger_migration_rule(self):
        """
        Rule: If code version is newer than installed version in database,
        mark chicken_farm_module as 'to upgrade' so Odoo automatically performs
        the upgrade and migration scripts.
        """
        from odoo.tools.parse_version import parse_version
        import logging
        logger = logging.getLogger(__name__)

        self.env.cr.execute("""
            SELECT latest_version, state 
            FROM ir_module_module 
            WHERE name = 'chicken_farm_module' 
            LIMIT 1;
        """)
        row = self.env.cr.fetchone()
        if not row:
            return
        installed_ver, state = row
        manifest_ver = '19.0.1.6.2'
        if state == 'installed' and installed_ver and parse_version(installed_ver) < parse_version(manifest_ver):
            logger.warning(
                "[chicken_farm_module] AUTO-MIGRATION RULE: Installed DB version is '%s' but codebase is '%s'. "
                "Marking module 'to upgrade' to trigger migration scripts automatically.",
                installed_ver, manifest_ver
            )
            self.env.cr.execute("""
                UPDATE ir_module_module 
                SET state = 'to upgrade' 
                WHERE name = 'chicken_farm_module';
            """)
    flock_id = fields.Many2one('taghini.flock', string='Flock/Batch', required=True, ondelete='cascade')
    pen_id = fields.Many2one('stock.location', related='flock_id.pen_id', store=True, string="Pen Location", readonly=True)
    # === Farm & Warehouse chain (drives stock moves) ===
    farm_id = fields.Many2one('taghini.farm', related='flock_id.farm_id', store=True, string="Farm", readonly=True)
    warehouse_id = fields.Many2one('stock.warehouse', related='flock_id.warehouse_id', store=True, string="Warehouse", readonly=True)
    standard_id = fields.Many2one('taghini.farm.standard', related='flock_id.standard_id', store=True)
    company_id = fields.Many2one('res.company', string='Company', related='flock_id.company_id', store=True, readonly=True)
    date = fields.Date(string='Date', default=fields.Date.context_today, required=True)
    age_day = fields.Integer(string='Age', compute='_compute_age_day', store=True)
    state = fields.Selection([('draft', 'Draft'), ('done', 'Posted')], default='draft', string='Status')

    # --- 1. MORTALITY & BIRDS ---
    birds_count = fields.Integer(string='Start Birds', compute='_compute_daily_metrics', store=True, help="Birds alive at start of day")
    mortality = fields.Integer(string='Mortality', default=0)
    scrap_id = fields.Many2one('stock.scrap', string='Related Scrap', readonly=True)
    daily_mortality_percent = fields.Float(string='Daily Mort %', compute='_compute_daily_metrics', store=True, digits=(16, 2))
    cumm_mortality = fields.Integer(string='Cumm. Mortality', compute='_compute_cumulative_stats', store=True)
    cumm_mortality_percent = fields.Float(string='Cumm. Mort %', compute='_compute_cumulative_stats', store=True, digits=(16, 2))

    # --- 2. FEED SECTION ---
    feed_product_id = fields.Many2one('product.product', compute='_compute_expectations', store=True, string='Feed Type')
    feed_consumed_bags = fields.Integer(string='Bags')
    feed_consumed_g = fields.Float(string='Consumed (g)', compute='_compute_feed_g', store=True)
    move_id = fields.Many2one('stock.move', string='Feed Usage', readonly=True)
    feed_per_bird_g = fields.Float(string='Feed/Bird (g)', compute='_compute_daily_metrics', store=True)
    expected_feed_g = fields.Float(string='Exp. Feed (g)', compute='_compute_expectations', store=True)
    variance_feed_g = fields.Float(string='Feed Var (g)', compute='_compute_expectations', store=True)
    cumm_actual_feed_g = fields.Float(string='Cumm. Actual Feed', compute='_compute_cumulative_stats', store=True)
    cumm_expected_feed_g = fields.Float(string='Cumm. Exp. Feed', compute='_compute_cumulative_stats', store=True)

    # --- 3. WEIGHT & BIOMETRICS ---
    actual_avg_weight = fields.Float(string='Actual Avg Wgt (g)')
    expected_avg_weight = fields.Float(string='Exp. Avg Wgt (g)', compute='_compute_expectations', store=True)
    variance_weight = fields.Float(string='Wgt Variance', compute='_compute_expectations', store=True)
    light_hours = fields.Float(string='Light (Hrs)')
    light_period = fields.Char(string='Light Period')

    # --- 4. OTHER & HARVEST ---
    water_consumed = fields.Float(string='Water (L)')
    store_items_received = fields.Text(string='Items Received from Store')
    farm_observations = fields.Text(string='Farm Observations')
    farm_activities = fields.Text(string='Farm Activities')

    # === REQUIREMENT 8: MULTIPLE MEDICATIONS ===
    medication_line_ids = fields.One2many(
        'taghini.daily.log.medication', 'log_id',
        string='Medications Applied'
    )
    # Legacy fields retained for backwards compatibility
    medication_product_id = fields.Many2one('product.product', string='Primary Medication')
    medication_qty = fields.Float(string='Dose Quantity')
    medication_uom_id = fields.Many2one('uom.uom', string="Unit", related='medication_product_id.uom_id', readonly=True)
    medication_move_id = fields.Many2one('stock.move', string='Medication Usage', readonly=True)

    vaccine_name = fields.Char(string='Vaccine')

    # === REQUIREMENT 9: REMARKS AS MANY2MANY ===
    remark_ids = fields.Many2many(
        'taghini.farm.remark', 'taghini_daily_log_remark_rel', 'log_id', 'remark_id',
        string='Standard Remarks / Symptoms'
    )
    remarks = fields.Text(string='Additional Notes / Free Remarks')

    # Vet escalation tracking
    has_escalated_remarks = fields.Boolean(
        string='Has Escalated Remarks',
        compute='_compute_has_escalated_remarks',
        store=True
    )
    vet_notified = fields.Boolean(string='Veterinarian Notified', default=False, readonly=True)

    harvested_qty = fields.Integer(string='Harvested Qty')
    harvested_weight = fields.Float(string='Harvested Wgt')

    @api.depends('remark_ids', 'remark_ids.need_escalation')
    def _compute_has_escalated_remarks(self):
        for record in self:
            record.has_escalated_remarks = any(r.need_escalation for r in record.remark_ids)

    # --- COMPUTES ---
    @api.depends('flock_id.start_date', 'date')
    def _compute_age_day(self):
        for record in self:
            if record.flock_id.start_date and record.date:
                record.age_day = (record.date - record.flock_id.start_date).days
            else:
                record.age_day = 0

    @api.onchange('date', 'flock_id')
    def _on_date_change_set_standard(self):
        if self.flock_id and self.flock_id.standard_id and self.date:
            delta = self.date - self.flock_id.start_date
            current_age = delta.days
            rule = self.env['taghini.farm.standard.line'].search([
                ('standard_id', '=', self.flock_id.standard_id.id),
                ('age_min', '<=', current_age),
                ('age_max', '>=', current_age)
            ], limit=1)
            if rule:
                if not self.feed_product_id:
                    self.feed_product_id = rule.product_id
                # Auto-fill recommended medication line if configured and none exists yet
                if rule.medication_id and not self.medication_line_ids:
                    self.medication_line_ids = [(0, 0, {
                        'product_id': rule.medication_id.id,
                        'quantity': rule.medication_qty,
                    })]
                self.medication_product_id = rule.medication_id
                self.medication_qty = rule.medication_qty

    @api.depends('feed_consumed_bags')
    def _compute_feed_g(self):
        for record in self:
            record.feed_consumed_g = record.feed_consumed_bags * 25000.0

    @api.depends('flock_id', 'date', 'standard_id', 'age_day', 'feed_consumed_g', 'actual_avg_weight')
    def _compute_expectations(self):
        for record in self:
            exp_feed = 0.0
            exp_weight = 0.0
            exp_product = False
            if record.standard_id:
                rule = self.env['taghini.farm.standard.line'].search([
                    ('standard_id', '=', record.standard_id.id),
                    ('age_min', '<=', record.age_day),
                    ('age_max', '>=', record.age_day)
                ], limit=1)
                if rule:
                    birds = record.birds_count or record.flock_id.initial_birds
                    exp_feed = birds * rule.expected_feed_g
                    exp_weight = rule.expected_weight_g
                    exp_product = rule.product_id
            record.expected_feed_g = exp_feed
            record.variance_feed_g = record.feed_consumed_g - exp_feed
            record.feed_product_id = exp_product
            record.expected_avg_weight = exp_weight
            record.variance_weight = record.actual_avg_weight - exp_weight if record.actual_avg_weight else 0.0

    @api.depends('flock_id.log_ids.mortality', 'flock_id.log_ids.feed_consumed_g',
                 'flock_id.log_ids.expected_feed_g', 'date', 'flock_id.initial_birds')
    def _compute_cumulative_stats(self):
        flocks = self.mapped('flock_id')
        for flock in flocks:
            all_logs = flock.log_ids.sorted(key=lambda l: (l.date or fields.Date.today(), l.id or 0))
            running_mort = 0
            running_feed = 0.0
            running_exp_feed = 0.0
            initial = flock.initial_birds or 1
            
            for log in all_logs:
                running_mort += (log.mortality or 0)
                running_feed += (log.feed_consumed_g or 0.0)
                running_exp_feed += (log.expected_feed_g or 0.0)
                
                if log in self:
                    log.cumm_mortality = running_mort
                    log.cumm_actual_feed_g = running_feed
                    log.cumm_expected_feed_g = running_exp_feed
                    log.cumm_mortality_percent = (running_mort / initial)

        for record in self.filtered(lambda r: not r.flock_id):
            record.cumm_mortality = 0
            record.cumm_mortality_percent = 0.0
            record.cumm_actual_feed_g = 0.0
            record.cumm_expected_feed_g = 0.0

    @api.depends('flock_id.log_ids.mortality', 'flock_id.log_ids.harvested_qty',
                 'date', 'flock_id.initial_birds', 'mortality', 'feed_consumed_g')
    def _compute_daily_metrics(self):
        flocks = self.mapped('flock_id')
        for flock in flocks:
            all_logs = flock.log_ids.sorted(key=lambda l: (l.date or fields.Date.today(), l.id or 0))
            running_gone = 0
            initial = flock.initial_birds or 0

            for log in all_logs:
                if log in self:
                    current_birds = max(initial - running_gone, 0)
                    log.birds_count = current_birds
                    if current_birds > 0:
                        log.daily_mortality_percent = ((log.mortality or 0) / current_birds)
                        log.feed_per_bird_g = (log.feed_consumed_g or 0.0) / current_birds
                    else:
                        log.daily_mortality_percent = 0.0
                        log.feed_per_bird_g = 0.0
                running_gone += (log.mortality or 0) + (log.harvested_qty or 0)

        for record in self.filtered(lambda r: not r.flock_id):
            record.birds_count = 0
            record.daily_mortality_percent = 0.0
            record.feed_per_bird_g = 0.0

    # === REQUIREMENT 10: VET NOTIFICATIONS ===
    def _notify_veterinarian_if_needed(self):
        """
        Notify the assigned veterinary doctor if any selected remark needs escalation
        or abnormal mortality condition is present. Handles multiple remarks.
        """
        for record in self:
            vet_user = record.flock_id.pen_model_id.vet_id or record.flock_id.farm_id.vet_id
            if not vet_user:
                continue

            escalated_remarks = record.remark_ids.filtered(lambda r: r.need_escalation)
            # High mortality condition (>2% daily)
            high_mortality = (record.daily_mortality_percent or 0.0) >= 0.02 and record.mortality > 10

            if not escalated_remarks and not high_mortality:
                continue

            # Build alert message detailing all remarks
            remarks_list_html = "".join([f"<li><b>[{r.category.upper() if r.category else 'ALERT'}]</b> {r.name}</li>" for r in escalated_remarks])
            mortality_html = f"<p><b>Mortality:</b> {record.mortality} birds ({round((record.daily_mortality_percent or 0.0) * 100, 2)}% of start flock)</p>" if high_mortality else ""
            notes_html = f"<p><b>Notes:</b> {record.remarks}</p>" if record.remarks else ""

            body = _(
                "<div style='color: #b71c1c;'>"
                "<h4>⚠️ URGENT: Health Alert & Escalation for Pen %s (Flock: %s)</h4>"
                "<p><b>Date:</b> %s | <b>Age:</b> Day %s</p>"
                "%s"
                "<p><b>Conditions / Remarks requiring attention (%s):</b></p>"
                "<ul>%s</ul>"
                "%s"
                "</div>"
            ) % (
                record.flock_id.pen_model_id.name,
                record.flock_id.name,
                record.date,
                record.age_day,
                mortality_html,
                len(escalated_remarks),
                remarks_list_html,
                notes_html
            )

            # Post on chatter of daily log and flock
            partners = [vet_user.partner_id.id]
            if record.flock_id.pen_model_id.manager_id:
                partners.append(record.flock_id.pen_model_id.manager_id.partner_id.id)

            record.message_post(body=body, partner_ids=partners, subtype_xmlid='mail.mt_comment')
            record.flock_id.message_post(body=body, partner_ids=partners, subtype_xmlid='mail.mt_comment')

            # Schedule to-do activity for the vet
            summary_remarks = ", ".join(escalated_remarks.mapped('name')[:3])
            record.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=vet_user.id,
                summary=_("Vet Attention Required: %s") % (summary_remarks or "High Mortality"),
                note=_("Please inspect flock %s in pen %s due to reported conditions: %s") % (
                    record.flock_id.name,
                    record.flock_id.pen_model_id.name,
                    ", ".join(escalated_remarks.mapped('name'))
                )
            )
            record.vet_notified = True

    def _compute_display_name(self):
        for record in self:
            flock_str = record.flock_id.name or ''
            date_str = str(record.date) if record.date else ''
            ref = record.name
            if ref and ref != 'New':
                record.display_name = f"[{ref}] {flock_str} ({date_str})"
            else:
                record.display_name = f"{flock_str} ({date_str})"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New' or not vals.get('name'):
                vals['name'] = self.env['ir.sequence'].next_by_code('taghini.daily.log') or 'New'
        records = super().create(vals_list)
        for record in records:
            record._notify_veterinarian_if_needed()
        return records

    def init(self):
        super().init()
        # Backfill sequence numbers for daily logs that don't have one
        logs_without_name = self.search([
            '|', ('name', '=', False), ('name', '=', 'New')
        ], order='id asc')
        for log in logs_without_name:
            seq_val = self.env['ir.sequence'].next_by_code('taghini.daily.log')
            log.name = seq_val or f"LOG/{log.id:05d}"

    def write(self, vals):
        res = super().write(vals)
        if 'remark_ids' in vals or 'mortality' in vals:
            self._notify_veterinarian_if_needed()
        return res

    # -------------------------------------------------------------------------
    # POST LOG ACTION
    # -------------------------------------------------------------------------
    def action_post_log(self):
        """Posts mortality scraps and stock moves for feed & medications."""
        for record in self:
            if record.state == 'done':
                continue

            # 1. Mortality → scrap
            if record.mortality > 0 and not record.scrap_id:
                if not record.flock_id.pen_id:
                    raise UserError(_("Please set a Pen Location on the Flock."))
                scrap = self.env['stock.scrap'].create({
                    'product_id': record.flock_id.product_id.id,
                    'scrap_qty': record.mortality,
                    'location_id': record.flock_id.pen_id.id,
                    'origin': f"Mortality {record.flock_id.name} - Day {record.age_day}",
                    'state': 'done'
                })
                scrap.action_validate()
                record.scrap_id = scrap.id

            # Resolve warehouse from farm
            farm = record.flock_id.pen_model_id.farm_id
            if not farm or not farm.warehouse_id:
                raise UserError(_(
                    "Cannot post log: the flock's pen has no farm assigned, or the farm "
                    "has no warehouse linked.\n\nPlease open the Pen → set its Farm → "
                    "ensure the Farm has a Warehouse."
                ))
            warehouse = farm.warehouse_id

            production_location = self.env['stock.location'].search([
                ('usage', '=', 'production'),
                ('company_id', 'in', [record.company_id.id, False])
            ], limit=1)
            if not production_location:
                raise UserError(_(
                    "Could not find a Virtual Production Location for this company. "
                    "Please contact your administrator."
                ))

            # 2. Feed → stock move
            if record.feed_consumed_g > 0 and record.feed_product_id and not record.move_id:
                move = self.env['stock.move'].create({
                    'product_id': record.feed_product_id.id,
                    'product_uom_qty': record.feed_consumed_g,
                    'product_uom': record.feed_product_id.uom_id.id,
                    'location_id': warehouse.lot_stock_id.id,
                    'location_dest_id': production_location.id,
                    'origin': f"Feed {record.flock_id.name} - Day {record.age_day}",
                    'state': 'draft',
                })
                move._action_confirm()
                move._action_assign()
                for line in move.move_line_ids:
                    line.quantity = line.quantity_product_uom
                if not move.move_line_ids:
                    self.env['stock.move.line'].create({
                        'move_id': move.id,
                        'product_id': move.product_id.id,
                        'product_uom_id': move.product_uom.id,
                        'location_id': move.location_id.id,
                        'location_dest_id': move.location_dest_id.id,
                        'quantity': record.feed_consumed_g,
                    })
                move.picked = True
                move._action_done()
                record.move_id = move.id

            # 3. Medications (Multiple Lines Support - Req 8)
            for med_line in record.medication_line_ids.filtered(lambda l: l.quantity > 0 and not l.move_id):
                med_move = self.env['stock.move'].create({
                    'product_id': med_line.product_id.id,
                    'product_uom_qty': med_line.quantity,
                    'product_uom': med_line.uom_id.id or med_line.product_id.uom_id.id,
                    'location_id': warehouse.lot_stock_id.id,
                    'location_dest_id': production_location.id,
                    'origin': f"Meds ({med_line.product_id.name}) {record.flock_id.name} - Day {record.age_day}",
                    'state': 'draft',
                })
                med_move._action_confirm()
                med_move._action_assign()
                for line in med_move.move_line_ids:
                    line.quantity = line.quantity_product_uom
                if not med_move.move_line_ids:
                    self.env['stock.move.line'].create({
                        'move_id': med_move.id,
                        'product_id': med_move.product_id.id,
                        'product_uom_id': med_move.product_uom.id,
                        'location_id': med_move.location_id.id,
                        'location_dest_id': med_move.location_dest_id.id,
                        'quantity': med_line.quantity,
                    })
                med_move.picked = True
                med_move._action_done()
                med_line.move_id = med_move.id

            # Legacy single medication fallback (if entered in legacy fields and not in lines)
            if record.medication_qty > 0 and record.medication_product_id and not record.medication_move_id and not record.medication_line_ids:
                med_move = self.env['stock.move'].create({
                    'product_id': record.medication_product_id.id,
                    'product_uom_qty': record.medication_qty,
                    'product_uom': record.medication_uom_id.id or record.medication_product_id.uom_id.id,
                    'location_id': warehouse.lot_stock_id.id,
                    'location_dest_id': production_location.id,
                    'origin': f"Meds {record.flock_id.name} - Day {record.age_day}",
                    'state': 'draft',
                })
                med_move._action_confirm()
                med_move._action_assign()
                for line in med_move.move_line_ids:
                    line.quantity = line.quantity_product_uom
                if not med_move.move_line_ids:
                    self.env['stock.move.line'].create({
                        'move_id': med_move.id,
                        'product_id': med_move.product_id.id,
                        'product_uom_id': med_move.product_uom.id,
                        'location_id': med_move.location_id.id,
                        'location_dest_id': med_move.location_dest_id.id,
                        'quantity': record.medication_qty,
                    })
                med_move.picked = True
                med_move._action_done()
                record.medication_move_id = med_move.id

            # Ensure notifications are delivered on posting
            record._notify_veterinarian_if_needed()
            record.state = 'done'

    def unlink(self):
        """Prevent deleting posted logs to protect data integrity."""
        for record in self:
            if record.state == 'done':
                raise UserError(_(
                    "You cannot delete a Posted log line because it has already created Stock Moves.\n\n"
                    "To correct this, please create a new line with negative values or consult your manager."
                ))
        return super(FarmDailyLog, self).unlink()


class FarmDailyLogMedication(models.Model):
    _name = 'taghini.daily.log.medication'
    _description = 'Daily Log Medication Line'

    log_id = fields.Many2one('taghini.daily.log', string='Daily Log', required=True, ondelete='cascade')
    product_id = fields.Many2one(
        'product.product', string='Medication / Supplement',
        required=True
    )
    quantity = fields.Float(string='Dose Quantity', required=True, default=1.0)
    uom_id = fields.Many2one('uom.uom', string='Unit', related='product_id.uom_id', readonly=True)
    administration_route = fields.Selection([
        ('water', 'Drinking Water'),
        ('feed', 'In Feed'),
        ('injection', 'Injection'),
        ('spray', 'Spray / Aerosol'),
        ('oral', 'Direct Oral'),
        ('other', 'Other')
    ], string='Route', default='water')
    notes = fields.Char(string='Notes / Indication')
    move_id = fields.Many2one('stock.move', string='Stock Move', readonly=True)
