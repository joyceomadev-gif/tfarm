from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class BreederPenLog(models.Model):
    _name = 'taghini.breeder.pen.log'
    _description = 'Breeder Pen Daily Operations Ledger (111 Columns)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    # =========================================================================
    # SECTION 1: HEADER & TIMING (Cols 1-4)
    # =========================================================================
    name = fields.Char(string='Log Reference', readonly=True, copy=False, default='New')
    flock_id = fields.Many2one('taghini.breeder.flock', string='Breeder Pen Series', required=True, ondelete='cascade', tracking=True)
    batch_id = fields.Many2one('taghini.breeder.batch', related='flock_id.batch_id', store=True, readonly=True)
    pen_id = fields.Many2one('taghini.pen', related='flock_id.pen_id', store=True, readonly=True)
    farm_id = fields.Many2one('taghini.farm', related='flock_id.farm_id', store=True, readonly=True)
    company_id = fields.Many2one('res.company', related='flock_id.company_id', store=True, readonly=True)

    date = fields.Date(string='Date', default=fields.Date.context_today, required=True, tracking=True)
    age_day = fields.Integer(string='Age (days)', compute='_compute_timing', store=True)
    age_week = fields.Integer(string='Age (week)', compute='_compute_timing', store=True)
    phase = fields.Selection([
        ('brooding', 'Brooding (Wk 0-3)'),
        ('rearing', 'Rearing (Wk 4-20)'),
        ('pre_lay', 'Pre-Lay (Wk 21-23)'),
        ('lay', 'Laying (Wk 24-64+)'),
    ], string='Phase', compute='_compute_timing', store=True)

    # =========================================================================
    # SECTION 2: FEMALES POPULATION (Cols 5-15)
    # =========================================================================
    opening_females = fields.Integer(string='Opening Females', compute='_compute_balances', store=True)
    female_mortality = fields.Integer(string='Female Mortality', default=0, tracking=True)
    female_culls = fields.Integer(string='Female Culls', default=0)
    sex_error_removals = fields.Integer(string='Sex-Error Removals', default=0)
    females_in = fields.Integer(string='Females Transferred IN', default=0)
    females_out = fields.Integer(string='Females Transferred OUT', default=0)
    closing_females = fields.Integer(string='Closing Females', compute='_compute_balances', store=True)
    female_daily_mort_pct = fields.Float(string='Female Daily Mort. %', compute='_compute_rates', store=True, digits=(16, 5))
    female_cum_mortality = fields.Integer(string='Female Cum. Mortality', compute='_compute_balances', store=True)
    female_cum_mort_pct_placed = fields.Float(string='Female Cum. Mort. % Placed', compute='_compute_rates', store=True, digits=(16, 4))
    female_cum_culls_sex_errors = fields.Integer(string='Female Cum. Culls + Sex Errors', compute='_compute_balances', store=True)

    # =========================================================================
    # SECTION 3: MALES POPULATION (Cols 16-27)
    # =========================================================================
    opening_males = fields.Integer(string='Opening Males', compute='_compute_balances', store=True)
    male_mortality = fields.Integer(string='Male Mortality', default=0, tracking=True)
    male_culls = fields.Integer(string='Male Culls', default=0)
    males_in = fields.Integer(string='Males Transferred IN', default=0)
    males_out = fields.Integer(string='Males Transferred OUT', default=0)
    closing_males = fields.Integer(string='Closing Males', compute='_compute_balances', store=True)
    male_daily_mort_pct = fields.Float(string='Male Daily Mort. %', compute='_compute_rates', store=True, digits=(16, 5))
    male_cum_mortality = fields.Integer(string='Male Cum. Mortality', compute='_compute_balances', store=True)
    male_cum_mort_pct_placed = fields.Float(string='Male Cum. Mort. % Placed', compute='_compute_rates', store=True, digits=(16, 4))
    males_per_100_females = fields.Float(string='Males per 100 Females', compute='_compute_rates', store=True, digits=(16, 2))
    main_cause_of_death = fields.Char(string='Main Cause of Death')
    post_mortem_done = fields.Boolean(string='Post-Mortem Done (Y/N)', default=False)

    # =========================================================================
    # SECTION 4: FEED (SEX-SEPARATE) (Cols 28-40)
    # =========================================================================
    feed_product_id = fields.Many2one('product.product', string='Feed Type', domain="[('purchase_ok', '=', True)]")
    feed_batch_no = fields.Char(string='Feed Batch / Delivery No.')
    female_feed_kg = fields.Float(string='Female Feed (kg)', default=0.0)
    male_feed_kg = fields.Float(string='Male Feed (kg)', default=0.0)
    planned_nil_feed_day = fields.Boolean(string='Planned Nil-Feed Day (Y/N)', default=False)

    female_feed_g_per_bird = fields.Float(string='Female Feed g/bird/day', compute='_compute_feed_metrics', store=True, digits=(16, 1))
    aa_female_feed_g = fields.Float(string='AA Female Feed g/bird/day', compute='_compute_standards', store=True)
    female_feed_var_pct = fields.Float(string='Female Feed Var. %', compute='_compute_feed_metrics', store=True, digits=(16, 4))

    male_feed_g_per_bird = fields.Float(string='Male Feed g/bird/day', compute='_compute_feed_metrics', store=True, digits=(16, 1))
    aa_male_feed_g = fields.Float(string='AA Male Feed g/bird/day', compute='_compute_standards', store=True)
    male_feed_var_pct = fields.Float(string='Male Feed Var. %', compute='_compute_feed_metrics', store=True, digits=(16, 4))

    female_cleanup_hours = fields.Float(string='Female Feed Clean-Up Time (hrs)')
    sex_separate_feeding_ok = fields.Boolean(string='Sex-Separate Feeding Checked OK', default=True)

    # =========================================================================
    # SECTION 5: WATER & HOUSE ENVIRONMENT (Cols 41-49)
    # =========================================================================
    water_consumed_l = fields.Float(string='Water Consumed (litres)', default=0.0)
    water_ml_per_bird = fields.Float(string='Water ml/bird/day', compute='_compute_water_metrics', store=True, digits=(16, 1))
    water_feed_ratio = fields.Float(string='Water:Feed Ratio', compute='_compute_water_metrics', store=True, digits=(16, 2))
    min_temp = fields.Float(string='Min. Temp (°C)')
    max_temp = fields.Float(string='Max. Temp (°C)')
    max_rh = fields.Float(string='Max. RH (%)')
    litter_score = fields.Integer(string='Litter Score (1–5)', default=1)
    curtain_position = fields.Selection([
        ('open', 'Open'),
        ('partly', 'Partly Open'),
        ('closed', 'Closed'),
    ], string='Curtains', default='partly')
    footbath_changed = fields.Boolean(string='Footbath Changed (Y/N)', default=True)

    # =========================================================================
    # SECTION 6: LIGHTING (Cols 50-53)
    # =========================================================================
    light_on_time = fields.Float(string='Light ON (hh:mm)')
    light_off_time = fields.Float(string='Light OFF (hh:mm)')
    light_hours = fields.Float(string='Light Hours', compute='_compute_light_hours', store=True)
    light_intensity_lux = fields.Float(string='Light Intensity (lux) – Weekly')

    # =========================================================================
    # SECTION 7: WEEKLY WEIGHING (Cols 54-65)
    # =========================================================================
    female_sample_n = fields.Integer(string='Female Sample (n)')
    female_avg_bw_g = fields.Float(string='Female Av. BW (g)')
    female_cv_pct = fields.Float(string='Female CV %', digits=(16, 4))
    female_uniformity_pct = fields.Float(string='Female Uniformity % (±10%)', digits=(16, 4))
    aa_female_bw_g = fields.Float(string='AA Female BW at Age (g)', compute='_compute_standards', store=True)
    female_bw_dev_pct = fields.Float(string='Female BW Dev. %', compute='_compute_bw_dev', store=True, digits=(16, 4))

    male_sample_n = fields.Integer(string='Male Sample (n)')
    male_avg_bw_g = fields.Float(string='Male Av. BW (g)')
    male_cv_pct = fields.Float(string='Male CV %', digits=(16, 4))
    male_uniformity_pct = fields.Float(string='Male Uniformity % (±10%)', digits=(16, 4))
    aa_male_bw_g = fields.Float(string='AA Male BW at Age (g)', compute='_compute_standards', store=True)
    male_bw_dev_pct = fields.Float(string='Male BW Dev. %', compute='_compute_bw_dev', store=True, digits=(16, 4))

    # =========================================================================
    # SECTION 8: DAILY EGG COLLECTION (Cols 66-85)
    # =========================================================================
    is_laying = fields.Boolean(
        string='Laying Active',
        compute='_compute_is_laying',
        store=True,
        help="Controls visibility of the Egg Collection & Grading tab. Automatically active once the flock enters the laying phase."
    )
    total_eggs_collected = fields.Integer(string='Total Eggs Collected', compute='_compute_egg_totals', store=True)
    hatching_eggs = fields.Integer(string='Hatching (Settable) Eggs', default=0)
    floor_eggs = fields.Integer(string='Floor Eggs (incl. in total)', default=0)
    double_yolk_eggs = fields.Integer(string='Double-Yolk', default=0)
    cracked_eggs = fields.Integer(string='Cracked / Broken', default=0)
    dirty_eggs = fields.Integer(string='Dirty', default=0)
    small_eggs = fields.Integer(string='Small / Undersize', default=0)
    misshapen_eggs = fields.Integer(string='Misshapen / Thin-Shell', default=0)
    total_rejects = fields.Integer(string='Total Rejects', compute='_compute_egg_totals', store=True)

    avg_egg_weight_g = fields.Float(string='Av. Egg Weight (g) – Weekly')
    hen_day_pct = fields.Float(string='Hen-Day %', compute='_compute_egg_rates', store=True, digits=(16, 4))
    aa_hen_week_pct = fields.Float(string='AA Hen-Week %', compute='_compute_standards', store=True, digits=(16, 4))
    hen_day_var_pts = fields.Float(string='Hen-Day Var. (pts)', compute='_compute_egg_rates', store=True, digits=(16, 2))
    hatching_egg_pct = fields.Float(string='Hatching-Egg %', compute='_compute_egg_rates', store=True, digits=(16, 4))
    aa_hatching_egg_pct = fields.Float(string='AA Hatching-Egg %', compute='_compute_standards', store=True, digits=(16, 4))
    floor_egg_pct = fields.Float(string='Floor Eggs %', compute='_compute_egg_rates', store=True, digits=(16, 4))
    reject_pct = fields.Float(string='Reject %', compute='_compute_egg_rates', store=True, digits=(16, 4))
    aa_egg_weight_g = fields.Float(string='AA Egg Weight (g)', compute='_compute_standards', store=True)
    cum_eggs_per_hen = fields.Float(string='Cum. Eggs per Hen Housed', compute='_compute_cum_eggs', store=True, digits=(16, 2))
    cum_hatching_eggs_per_hen = fields.Float(string='Cum. Hatching Eggs per Hen', compute='_compute_cum_eggs', store=True, digits=(16, 2))

    # =========================================================================
    # SECTION 9: HEALTH & ADMIN (Cols 86-92)
    # =========================================================================
    medication_product_id = fields.Many2one('product.product', string='Medication (Product)', domain="[('purchase_ok', '=', True)]")
    vet_prescription_no = fields.Char(string='Vet Prescription No.')
    vaccine_name = fields.Char(string='Vaccine')
    vaccine_batch_no = fields.Char(string='Vaccine Batch No.')
    vaccine_route = fields.Selection([
        ('water', 'Drinking Water'),
        ('spray', 'Aerosol Spray'),
        ('wing_web', 'Wing Web Stab'),
        ('eye_drop', 'Intraocular / Eye Drop'),
        ('injection', 'Intramuscular Injection'),
    ], string='Vaccine Route')
    clinical_remarks = fields.Text(string='Clinical Signs / Remarks')
    recorded_by = fields.Char(string='Recorded By (Initials)', default=lambda self: self.env.user.name)

    # =========================================================================
    # SECTION 10: AUTOMATED AUDIT & FLAG ENGINE (Cols 93-97)
    # =========================================================================
    danger_flags = fields.Text(string='DANGER FLAGS', compute='_compute_flags', store=True)
    data_errors = fields.Text(string='DATA ERRORS', compute='_compute_flags', store=True)
    danger_count = fields.Integer(string='No. Danger', compute='_compute_flags', store=True)
    error_count = fields.Integer(string='No. Errors', compute='_compute_flags', store=True)
    row_status = fields.Selection([
        ('ok', 'OK'),
        ('fix_errors', 'FIX ERRORS'),
        ('danger', 'DANGER'),
    ], string='Row Status', compute='_compute_flags', store=True, default='ok')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted / Locked'),
    ], default='draft', required=True, tracking=True)

    # =========================================================================
    # COMPUTE METHODS
    # =========================================================================

    @api.depends('date', 'flock_id.start_date')
    def _compute_timing(self):
        for rec in self:
            if not rec.flock_id or not rec.flock_id.start_date or not rec.date:
                rec.age_day = 0
                rec.age_week = 0
                rec.phase = 'brooding'
                continue
            delta = (rec.date - rec.flock_id.start_date).days
            rec.age_day = max(delta, 0)
            rec.age_week = rec.age_day // 7
            if rec.age_week <= 3:
                rec.phase = 'brooding'
            elif rec.age_week <= 20:
                rec.phase = 'rearing'
            elif rec.age_week <= 23:
                rec.phase = 'pre_lay'
            else:
                rec.phase = 'lay'

    @api.depends(
        'flock_id', 'date',
        'female_mortality', 'female_culls', 'sex_error_removals', 'females_in', 'females_out',
        'male_mortality', 'male_culls', 'males_in', 'males_out'
    )
    def _compute_balances(self):
        for rec in self:
            if not rec.flock_id:
                rec.opening_females = 0
                rec.closing_females = 0
                rec.female_cum_mortality = 0
                rec.female_cum_culls_sex_errors = 0
                rec.opening_males = 0
                rec.closing_males = 0
                rec.male_cum_mortality = 0
                continue

            # Prior logs for this flock ordered by date
            prior_logs = self.search([
                ('flock_id', '=', rec.flock_id.id),
                ('date', '<', rec.date),
                ('id', '!=', rec.id or 0)
            ], order='date desc, id desc')

            if prior_logs:
                last_log = prior_logs[0]
                rec.opening_females = last_log.closing_females
                rec.opening_males = last_log.closing_males
                cum_f_mort = sum(prior_logs.mapped('female_mortality')) + rec.female_mortality
                cum_m_mort = sum(prior_logs.mapped('male_mortality')) + rec.male_mortality
                cum_f_culls = sum(prior_logs.mapped('female_culls')) + sum(prior_logs.mapped('sex_error_removals')) + rec.female_culls + rec.sex_error_removals
            else:
                rec.opening_females = rec.flock_id.initial_females
                rec.opening_males = rec.flock_id.initial_males
                cum_f_mort = rec.female_mortality
                cum_m_mort = rec.male_mortality
                cum_f_culls = rec.female_culls + rec.sex_error_removals

            rec.closing_females = rec.opening_females - rec.female_mortality - rec.female_culls - rec.sex_error_removals + rec.females_in - rec.females_out
            rec.female_cum_mortality = cum_f_mort
            rec.female_cum_culls_sex_errors = cum_f_culls

            rec.closing_males = rec.opening_males - rec.male_mortality - rec.male_culls + rec.males_in - rec.males_out
            rec.male_cum_mortality = cum_m_mort

    @api.depends('female_mortality', 'opening_females', 'female_cum_mortality', 'male_mortality', 'opening_males', 'male_cum_mortality', 'closing_females', 'closing_males', 'flock_id.initial_females', 'flock_id.initial_males')
    def _compute_rates(self):
        for rec in self:
            rec.female_daily_mort_pct = (rec.female_mortality / rec.opening_females) if rec.opening_females > 0 else 0.0
            init_f = rec.flock_id.initial_females if rec.flock_id else 0
            rec.female_cum_mort_pct_placed = (rec.female_cum_mortality / init_f) if init_f > 0 else 0.0

            rec.male_daily_mort_pct = (rec.male_mortality / rec.opening_males) if rec.opening_males > 0 else 0.0
            init_m = rec.flock_id.initial_males if rec.flock_id else 0
            rec.male_cum_mort_pct_placed = (rec.male_cum_mortality / init_m) if init_m > 0 else 0.0

            if rec.closing_females > 0:
                rec.males_per_100_females = round((rec.closing_males / rec.closing_females) * 100.0, 2)
            else:
                rec.males_per_100_females = 0.0

    @api.depends('batch_id.standard_id', 'age_week')
    def _compute_standards(self):
        for rec in self:
            std = rec.batch_id.standard_id if rec.batch_id else False
            if not std:
                rec.aa_female_feed_g = 0.0
                rec.aa_male_feed_g = 0.0
                rec.aa_female_bw_g = 0.0
                rec.aa_male_bw_g = 0.0
                rec.aa_hen_week_pct = 0.0
                rec.aa_hatching_egg_pct = 0.0
                rec.aa_egg_weight_g = 0.0
                continue
            line = std.line_ids.filtered(lambda l: l.week == rec.age_week)
            if line:
                target = line[0]
                rec.aa_female_feed_g = target.aa_female_feed_g or 0.0
                rec.aa_male_feed_g = target.aa_male_feed_g or 0.0
                rec.aa_female_bw_g = target.aa_female_bw_g or 0.0
                rec.aa_male_bw_g = target.aa_male_bw_g or 0.0
                rec.aa_hen_week_pct = target.aa_hen_week_pct or 0.0
                rec.aa_hatching_egg_pct = target.aa_hatching_egg_pct or 0.0
                rec.aa_egg_weight_g = target.aa_egg_weight_g or 0.0
            else:
                rec.aa_female_feed_g = 0.0
                rec.aa_male_feed_g = 0.0
                rec.aa_female_bw_g = 0.0
                rec.aa_male_bw_g = 0.0
                rec.aa_hen_week_pct = 0.0
                rec.aa_hatching_egg_pct = 0.0
                rec.aa_egg_weight_g = 0.0

    @api.depends('female_feed_kg', 'male_feed_kg', 'opening_females', 'opening_males', 'aa_female_feed_g', 'aa_male_feed_g')
    def _compute_feed_metrics(self):
        for rec in self:
            if rec.opening_females > 0:
                rec.female_feed_g_per_bird = round((rec.female_feed_kg * 1000.0) / rec.opening_females, 1)
            else:
                rec.female_feed_g_per_bird = 0.0

            if rec.aa_female_feed_g > 0:
                rec.female_feed_var_pct = (rec.female_feed_g_per_bird - rec.aa_female_feed_g) / rec.aa_female_feed_g
            else:
                rec.female_feed_var_pct = 0.0

            if rec.opening_males > 0:
                rec.male_feed_g_per_bird = round((rec.male_feed_kg * 1000.0) / rec.opening_males, 1)
            else:
                rec.male_feed_g_per_bird = 0.0

            if rec.aa_male_feed_g > 0:
                rec.male_feed_var_pct = (rec.male_feed_g_per_bird - rec.aa_male_feed_g) / rec.aa_male_feed_g
            else:
                rec.male_feed_var_pct = 0.0

    @api.depends('water_consumed_l', 'opening_females', 'opening_males', 'female_feed_kg', 'male_feed_kg')
    def _compute_water_metrics(self):
        for rec in self:
            total_birds = rec.opening_females + rec.opening_males
            if total_birds > 0:
                rec.water_ml_per_bird = round((rec.water_consumed_l * 1000.0) / total_birds, 1)
            else:
                rec.water_ml_per_bird = 0.0

            total_feed = rec.female_feed_kg + rec.male_feed_kg
            if total_feed > 0:
                rec.water_feed_ratio = round(rec.water_consumed_l / total_feed, 2)
            else:
                rec.water_feed_ratio = 0.0

    @api.depends('light_on_time', 'light_off_time')
    def _compute_light_hours(self):
        for rec in self:
            if rec.light_off_time is not False and rec.light_on_time is not False:
                diff = rec.light_off_time - rec.light_on_time
                if diff < 0:
                    diff += 24.0
                rec.light_hours = round(diff, 2)
            else:
                rec.light_hours = 0.0

    @api.depends('female_avg_bw_g', 'aa_female_bw_g', 'male_avg_bw_g', 'aa_male_bw_g')
    def _compute_bw_dev(self):
        for rec in self:
            if rec.female_avg_bw_g and rec.aa_female_bw_g > 0:
                rec.female_bw_dev_pct = (rec.female_avg_bw_g - rec.aa_female_bw_g) / rec.aa_female_bw_g
            else:
                rec.female_bw_dev_pct = 0.0

            if rec.male_avg_bw_g and rec.aa_male_bw_g > 0:
                rec.male_bw_dev_pct = (rec.male_avg_bw_g - rec.aa_male_bw_g) / rec.aa_male_bw_g
            else:
                rec.male_bw_dev_pct = 0.0

    @api.depends('phase', 'age_week', 'flock_id.laying_started')
    def _compute_is_laying(self):
        for rec in self:
            rec.is_laying = bool(
                rec.phase == 'lay'
                or rec.age_week >= 24
                or (rec.flock_id and rec.flock_id.laying_started)
            )

    @api.depends('hatching_eggs', 'floor_eggs', 'double_yolk_eggs', 'cracked_eggs', 'dirty_eggs', 'small_eggs', 'misshapen_eggs')
    def _compute_egg_totals(self):
        for rec in self:
            rec.total_rejects = (
                rec.double_yolk_eggs +
                rec.cracked_eggs +
                rec.dirty_eggs +
                rec.small_eggs +
                rec.misshapen_eggs +
                rec.floor_eggs
            )
            rec.total_eggs_collected = rec.hatching_eggs + rec.total_rejects

    @api.depends('total_eggs_collected', 'hatching_eggs', 'floor_eggs', 'total_rejects', 'closing_females', 'aa_hen_week_pct')
    def _compute_egg_rates(self):
        for rec in self:
            if rec.closing_females > 0:
                rec.hen_day_pct = rec.total_eggs_collected / rec.closing_females
            else:
                rec.hen_day_pct = 0.0

            rec.hen_day_var_pts = round((rec.hen_day_pct - (rec.aa_hen_week_pct or 0.0)) * 100.0, 2)

            if rec.total_eggs_collected > 0:
                rec.hatching_egg_pct = rec.hatching_eggs / rec.total_eggs_collected
                rec.floor_egg_pct = rec.floor_eggs / rec.total_eggs_collected
                rec.reject_pct = rec.total_rejects / rec.total_eggs_collected
            else:
                rec.hatching_egg_pct = 0.0
                rec.floor_egg_pct = 0.0
                rec.reject_pct = 0.0

    @api.depends('flock_id', 'date', 'total_eggs_collected', 'hatching_eggs')
    def _compute_cum_eggs(self):
        for rec in self:
            init_f = rec.flock_id.initial_females if rec.flock_id else 0
            if not rec.flock_id or init_f <= 0:
                rec.cum_eggs_per_hen = 0.0
                rec.cum_hatching_eggs_per_hen = 0.0
                continue

            all_prior = self.search([
                ('flock_id', '=', rec.flock_id.id),
                ('date', '<=', rec.date),
                ('id', '!=', rec.id or 0)
            ])
            tot_eggs = sum(all_prior.mapped('total_eggs_collected')) + rec.total_eggs_collected
            tot_hatch = sum(all_prior.mapped('hatching_eggs')) + rec.hatching_eggs
            rec.cum_eggs_per_hen = round(tot_eggs / init_f, 2)
            rec.cum_hatching_eggs_per_hen = round(tot_hatch / init_f, 2)

    # =========================================================================
    # SECTION 10: AUTOMATED DANGER FLAGS & DATA ERRORS EVALUATION ENGINE
    # =========================================================================
    @api.depends(
        'female_daily_mort_pct', 'male_daily_mort_pct', 'female_mortality', 'male_mortality',
        'age_week', 'batch_id', 'female_feed_var_pct', 'male_feed_var_pct',
        'female_feed_kg', 'planned_nil_feed_day', 'water_feed_ratio',
        'min_temp', 'max_temp', 'litter_score', 'female_bw_dev_pct', 'male_bw_dev_pct',
        'female_cv_pct', 'female_uniformity_pct', 'males_per_100_females',
        'female_cleanup_hours', 'sex_separate_feeding_ok', 'footbath_changed',
        'light_intensity_lux', 'hatching_egg_pct', 'floor_egg_pct', 'cracked_eggs', 'total_eggs_collected',
        'hen_day_var_pts', 'opening_females', 'opening_males', 'closing_females', 'closing_males'
    )
    def _compute_flags(self):
        for rec in self:
            batch = rec.batch_id
            if not batch:
                rec.danger_flags = False
                rec.data_errors = False
                rec.danger_count = 0
                rec.error_count = 0
                rec.row_status = 'ok'
                continue

            dangers = []
            errors = []

            # --- DANGER FLAGS (D01-D27) ---
            # D01: Female mortality
            t_mf = batch.t_mf_db if rec.age_week < 2 else batch.t_mf_d
            if rec.female_daily_mort_pct > t_mf:
                dangers.append("D01 Female mortality above threshold")

            # D02: Male mortality
            t_mm = batch.t_mm_db if rec.age_week < 2 else batch.t_mm_d
            if rec.male_mortality >= batch.t_mm_min and rec.male_daily_mort_pct > t_mm:
                dangers.append("D02 Male mortality above threshold")

            # D03 / D04: Feed deviation
            if rec.female_feed_var_pct and abs(rec.female_feed_var_pct) > batch.t_feedvar:
                dangers.append("D03 Female feed off AA allocation")
            if rec.male_feed_var_pct and abs(rec.male_feed_var_pct) > batch.t_feedvar:
                dangers.append("D04 Male feed off AA allocation")

            # D05: Nil feed day unplanned
            if rec.opening_females > 0 and rec.age_week >= 1 and rec.female_feed_kg == 0 and not rec.planned_nil_feed_day:
                dangers.append("D05 No female feed and not a planned nil-feed day")

            # D06: Water:feed ratio
            if rec.water_feed_ratio and (rec.water_feed_ratio < batch.t_wf_lo or rec.water_feed_ratio > batch.t_wf_hi):
                dangers.append("D06 Water:feed ratio out of range")

            # Prior day log comparison for day-on-day drops
            prior = self.search([
                ('flock_id', '=', rec.flock_id.id),
                ('date', '<', rec.date),
                ('id', '!=', rec.id or 0)
            ], order='date desc, id desc', limit=1) if rec.flock_id and rec.date else False

            # D07: Day-on-day water drop (t_wdrop)
            if prior and prior.water_consumed_l > 0 and rec.water_consumed_l > 0:
                drop_pct = (prior.water_consumed_l - rec.water_consumed_l) / prior.water_consumed_l
                t_wdrop = batch.t_wdrop or 0.05
                if drop_pct > t_wdrop:
                    dangers.append(f"D07 Day-on-day water drop >{int(t_wdrop * 100)}%")

            # D08 / D09: Temperature
            if rec.age_week >= 3 and rec.max_temp and rec.max_temp >= batch.t_tmax:
                dangers.append("D08 Heat stress temperature (from Wk 3)")
            if rec.age_week <= 2 and rec.min_temp and rec.min_temp < batch.t_tmin_brood:
                dangers.append("D09 Brooding temperature too low")

            # D10: Litter score
            if rec.litter_score >= batch.t_litter:
                dangers.append("D10 Wet / caked litter")

            # D11: Photoperiod drift (t_light_tol)
            if prior and prior.light_hours > 0 and rec.light_hours > 0:
                t_ltol = batch.t_light_tol or 0.25
                if abs(rec.light_hours - prior.light_hours) > t_ltol:
                    dangers.append(f"D11 Photoperiod drift >{t_ltol}h vs previous day")

            # D13 / D14: Body weight deviation
            if rec.female_bw_dev_pct and abs(rec.female_bw_dev_pct) > batch.t_bw_dev:
                dangers.append("D13 Female BW off AA standard")
            if rec.male_bw_dev_pct and abs(rec.male_bw_dev_pct) > batch.t_bw_dev:
                dangers.append("D14 Male BW off AA standard")

            # D15 / D16: Uniformity (normalized to fraction if entered as whole percentage)
            t_uni_min = batch.t_uniformity_min / 100.0 if batch.t_uniformity_min > 1.0 else batch.t_uniformity_min
            if (rec.female_uniformity_pct and rec.female_uniformity_pct < t_uni_min) or (rec.female_cv_pct and rec.female_cv_pct > 0.12):
                dangers.append("D15 Female uniformity poor")
            if (rec.male_uniformity_pct and rec.male_uniformity_pct < t_uni_min) or (rec.male_cv_pct and rec.male_cv_pct > 0.12):
                dangers.append("D16 Male uniformity poor")

            # D19: Egg weight deviation (t_egg_wt_dev)
            if rec.avg_egg_weight_g > 0 and rec.aa_egg_weight_g > 0:
                t_egg_dev = batch.t_egg_wt_dev or 2.0
                if abs(rec.avg_egg_weight_g - rec.aa_egg_weight_g) > t_egg_dev:
                    dangers.append(f"D19 Egg weight dev >{t_egg_dev}g vs AA standard")

            # D20: Floor eggs high (>2%)
            if rec.floor_egg_pct > 0.02:
                dangers.append("D20 Floor eggs high (>2%)")

            # D21: Cracked eggs high (>1%)
            if rec.total_eggs_collected > 0 and (rec.cracked_eggs / rec.total_eggs_collected) > 0.01:
                dangers.append("D21 Cracked / broken eggs high (>1%)")

            # D23: Mating ratio
            if rec.age_week >= 24 and rec.closing_females > 0 and rec.males_per_100_females > 0:
                if rec.males_per_100_females < batch.t_mating_lo or rec.males_per_100_females > batch.t_mating_hi:
                    dangers.append("D23 Mating ratio out of range")

            # D25: Sex-separate feeding
            if not rec.sex_separate_feeding_ok:
                dangers.append("D25 Sex-separate feeding failed")

            # D26: Footbath changed
            if not rec.footbath_changed:
                dangers.append("D26 Footbath not changed")

            # --- DATA INCONSISTENCIES / ERRORS (E01-E20) ---
            missing = []
            if rec.opening_females > 0 and rec.female_mortality < 0:
                missing.append("F-mortality negative")
            if rec.opening_females > 0 and not rec.planned_nil_feed_day and rec.female_feed_kg == 0:
                missing.append("F-feed")
            if rec.water_consumed_l == 0:
                missing.append("water")
            if not rec.min_temp:
                missing.append("min temp")
            if not rec.max_temp:
                missing.append("max temp")
            if missing:
                errors.append("E01 Missing: " + ", ".join(missing))

            if rec.closing_females < 0 or rec.closing_males < 0:
                errors.append("E02 Closing population negative")

            if (rec.female_mortality + rec.female_culls + rec.sex_error_removals + rec.females_out) > (rec.opening_females + rec.females_in):
                errors.append("E03 Removals exceed birds present")

            if rec.total_eggs_collected > 0 and rec.age_week < 20:
                errors.append("E04 Eggs recorded before laying age")

            if rec.min_temp and rec.max_temp and rec.min_temp > rec.max_temp:
                errors.append("E14 Min. temp above max. temp")

            if (rec.female_mortality + rec.male_mortality) > 0 and not rec.main_cause_of_death:
                errors.append("E15 Mortality without cause of death")

            if rec.medication_product_id and not rec.vet_prescription_no:
                errors.append("E16 Medication without vet prescription no.")

            if rec.vaccine_name and (not rec.vaccine_batch_no or not rec.vaccine_route):
                errors.append("E17 Vaccine without batch no. / route")

            # Aggregates
            rec.danger_flags = "; ".join(dangers) if dangers else False
            rec.data_errors = "; ".join(errors) if errors else False
            rec.danger_count = len(dangers)
            rec.error_count = len(errors)

            if rec.error_count > 0:
                rec.row_status = 'fix_errors'
            elif rec.danger_count > 0:
                rec.row_status = 'danger'
            else:
                rec.row_status = 'ok'

    # =========================================================================
    # ACTIONS & INVENTORY MOVES
    # =========================================================================
    @api.constrains('flock_id')
    def _check_flock_active(self):
        for rec in self:
            if rec.flock_id and rec.flock_id.state != 'active':
                raise ValidationError(_("Daily operations can only be recorded on an Active Breeder Pen Series. Flock '%s' is in status '%s'. Please activate it first.") % (rec.flock_id.name, rec.flock_id.state))

    @api.onchange('flock_id')
    def _onchange_flock_id(self):
        if self.flock_id:
            latest = self.search([('flock_id', '=', self.flock_id.id)], order='date desc, id desc', limit=1)
            if latest and latest.feed_product_id and not self.feed_product_id:
                self.feed_product_id = latest.feed_product_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New' or not vals.get('name'):
                vals['name'] = self.env['ir.sequence'].next_by_code('taghini.breeder.pen.log') or 'New'
        return super().create(vals_list)

    def action_post_log(self):
        """
        Post log:
        1. Create stock move for feed consumption from farm warehouse to virtual production.
        2. Create stock scrap for bird mortalities.
        3. Post vet alert chatter message if danger flags are triggered.
        4. Lock record into 'posted'.
        """
        for rec in self:
            if rec.state == 'posted':
                continue

            # 1. Feed Stock Move
            total_feed_kg = (rec.female_feed_kg or 0.0) + (rec.male_feed_kg or 0.0)
            if total_feed_kg > 0 and rec.feed_product_id and rec.farm_id.warehouse_id:
                src_loc = rec.farm_id.warehouse_id.lot_stock_id
                dest_loc = self.env['stock.location'].search([('usage', '=', 'production')], limit=1)
                if not dest_loc:
                    dest_loc = self.env.ref('stock.location_production', raise_if_not_found=False)

                if src_loc and dest_loc:
                    move = self.env['stock.move'].create({
                        'product_id': rec.feed_product_id.id,
                        'description_picking': f"Breeder Feed Consumption: {rec.flock_id.name} on {rec.date}",
                        'product_uom_qty': total_feed_kg,
                        'product_uom': rec.feed_product_id.uom_id.id,
                        'location_id': src_loc.id,
                        'location_dest_id': dest_loc.id,
                    })
                    move._action_confirm()
                    move._action_assign()
                    move.quantity = total_feed_kg
                    move.picked = True
                    move._action_done()

            # 2. Mortality Scraps
            total_mort = (rec.female_mortality or 0) + (rec.male_mortality or 0)
            if total_mort > 0 and rec.batch_id.bird_variant_id:
                bird_prod = self.env['product.product'].search([
                    ('product_tmpl_id', '=', rec.batch_id.bird_variant_id.id)
                ], limit=1)
                if bird_prod and rec.pen_id.location_id:
                    self.env['stock.scrap'].create({
                        'product_id': bird_prod.id,
                        'scrap_qty': total_mort,
                        'product_uom_id': bird_prod.uom_id.id,
                        'location_id': rec.pen_id.location_id.id,
                        'origin': f"Breeder Mortality: {rec.name} ({rec.date})",
                    }).action_validate()

            # 3. Vet Chatter Notification
            if rec.danger_count > 0 and rec.batch_id.vet_id:
                rec.message_post(
                    partner_ids=[rec.batch_id.vet_id.partner_id.id],
                    subject=_("BREEDER ALERT: Danger Flags Triggered in %s (%s)") % (rec.pen_id.name, rec.flock_id.name),
                    body=_(
                        "<p>The following <b>critical alerts</b> were triggered on <b>%s</b>:</p>"
                        "<p style='color:red;'><b>%s</b></p>"
                    ) % (rec.date, rec.danger_flags),
                )

            rec.write({'state': 'posted'})

    def action_export_111_col_excel(self):
        from ..wizard.breeder_excel_export_wizard import generate_111_col_excel_workbook
        import base64
        from datetime import datetime, date
        logs = self.sorted(key=lambda r: (r.date or date.min, r.id))
        if not logs:
            raise UserError(_("No daily operations logs selected for Excel export."))

        title = "Selected Breeder Daily Logs"
        if len(self) == 1:
            title = f"{self.name} ({self.flock_id.name})"

        file_bytes = generate_111_col_excel_workbook(self.env, logs, title_prefix=title)
        b64_data = base64.b64encode(file_bytes)
        filename = f"Breeder_Ledger_111Col_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
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

    def write(self, vals):
        res = super().write(vals)
        cascade_fields = {
            'date', 'female_mortality', 'female_culls', 'sex_error_removals',
            'females_in', 'females_out', 'male_mortality', 'male_culls',
            'males_in', 'males_out', 'total_eggs_collected', 'hatching_eggs'
        }
        if any(f in vals for f in cascade_fields):
            self._recompute_subsequent_pen_logs()
        return res

    def unlink(self):
        for rec in self:
            if rec.state == 'posted':
                raise UserError(_("You cannot delete a Posted Breeder Daily Pen Log."))
        flocks = self.mapped('flock_id')
        dates = [d for d in self.mapped('date') if d]
        min_date = min(dates) if dates else False
        res = super().unlink()
        if flocks and min_date:
            subsequent = self.search([
                ('flock_id', 'in', flocks.ids),
                ('date', '>=', min_date),
            ], order='date asc, id asc')
            if subsequent:
                subsequent._compute_balances()
                subsequent._compute_rates()
                subsequent._compute_cum_eggs()
        return res

    def _recompute_subsequent_pen_logs(self):
        for rec in self:
            if rec.flock_id and rec.date:
                subsequent = self.search([
                    ('flock_id', '=', rec.flock_id.id),
                    ('date', '>=', rec.date),
                    ('id', '!=', rec.id)
                ], order='date asc, id asc')
                if subsequent:
                    subsequent._compute_balances()
                    subsequent._compute_rates()
                    subsequent._compute_cum_eggs()
