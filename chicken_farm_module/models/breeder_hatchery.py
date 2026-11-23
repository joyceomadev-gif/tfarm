from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class BreederHatcheryDispatch(models.Model):
    _name = 'taghini.breeder.hatchery.dispatch'
    _description = 'Hatchery Candling, Breakout & Hatch Results'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'dispatch_date desc, id desc'

    name = fields.Char(string='Hatch Batch Ref', readonly=True, copy=False, default='New')
    egg_room_id = fields.Many2one('taghini.breeder.egg.room', string='Egg Room Dispatch Source', tracking=True)
    batch_id = fields.Many2one('taghini.breeder.batch', string='Breeder Batch', required=True, ondelete='cascade', tracking=True)
    farm_id = fields.Many2one('taghini.farm', related='batch_id.farm_id', store=True, readonly=True)
    company_id = fields.Many2one('res.company', related='batch_id.company_id', store=True, readonly=True)

    dispatch_note_no = fields.Char(string='Dispatch Note No.', required=True, tracking=True)
    dispatch_date = fields.Date(string='Dispatch Date', required=True, default=fields.Date.context_today, tracking=True)
    flock_age_week = fields.Integer(string='Av. Flock Age of Eggs (Week)', required=True)

    eggs_dispatched = fields.Integer(string='Eggs Dispatched')
    received_at_hatchery = fields.Integer(string='Received at Hatchery')
    set_date = fields.Date(string='Set Date (Incubation Start)')
    eggs_set = fields.Integer(string='Eggs Set in Incubator', required=True, default=0, tracking=True)

    # Break-out & Candling
    candling_date = fields.Date(string='Candling Date')
    infertile_clears = fields.Integer(string='Infertile (Clears)', default=0)
    early_dead = fields.Integer(string='Early Dead (0–7 d)', default=0)
    mid_dead = fields.Integer(string='Mid Dead (8–14 d)', default=0)
    late_dead = fields.Integer(string='Late Dead (15–21 d)', default=0)
    pipped_dead = fields.Integer(string='Pipped Dead', default=0)
    contaminated_exploders = fields.Integer(string='Contaminated / Exploders', default=0)

    # Hatch Output
    chicks_hatched = fields.Integer(string='Chicks Hatched (Total)', default=0)
    saleable_chicks = fields.Integer(string='Saleable Chicks (Grade-A DOCs)', required=True, default=0, tracking=True)
    cull_chicks = fields.Integer(string='Cull Chicks', default=0)

    # Rates & Benchmarks
    fertility_pct = fields.Float(string='Fertility %', compute='_compute_hatch_metrics', store=True, digits=(16, 4))
    hatch_pct_of_set = fields.Float(string='Hatch % (of set)', compute='_compute_hatch_metrics', store=True, digits=(16, 4))
    hatch_pct_of_fertile = fields.Float(string='Hatch of Fertile %', compute='_compute_hatch_metrics', store=True, digits=(16, 4))
    early_dead_pct = fields.Float(string='Early Dead %', compute='_compute_hatch_metrics', store=True, digits=(16, 4))
    contaminated_pct = fields.Float(string='Contaminated %', compute='_compute_hatch_metrics', store=True, digits=(16, 4))
    cull_chicks_pct = fields.Float(string='Cull Chicks %', compute='_compute_hatch_metrics', store=True, digits=(16, 4))

    aa_hatch_pct = fields.Float(string='AA Hatch % at this age', compute='_compute_aa_benchmark', store=True, digits=(16, 4))
    hatch_dev_pts = fields.Float(string='Hatch Dev. vs AA (pts)', compute='_compute_aa_benchmark', store=True, digits=(16, 2))
    chicks_per_hen_housed = fields.Float(string='Cum. Chicks per Hen Housed', compute='_compute_cum_chicks', store=True, digits=(16, 2))

    state = fields.Selection([
        ('draft', 'Draft'),
        ('incubating', 'Incubating'),
        ('candled', 'Candled'),
        ('hatched', 'Hatch Completed'),
    ], default='draft', required=True, tracking=True)

    @api.onchange('egg_room_id')
    def _onchange_egg_room_id(self):
        if self.egg_room_id:
            self.dispatch_note_no = self.egg_room_id.dispatch_note_no or ''
            self.dispatch_date = self.egg_room_id.date or fields.Date.context_today(self)
            self.eggs_dispatched = self.egg_room_id.dispatched_to_hatchery
            self.received_at_hatchery = self.egg_room_id.dispatched_to_hatchery
            self.batch_id = self.egg_room_id.batch_id
            self.flock_age_week = self.egg_room_id.flock_age_week

    @api.onchange('dispatch_date', 'batch_id')
    def _onchange_dispatch_date(self):
        if self.batch_id and self.batch_id.date and self.dispatch_date:
            days = (self.dispatch_date - self.batch_id.date).days
            self.flock_age_week = max(days // 7, 0)

    @api.constrains('eggs_set', 'received_at_hatchery', 'chicks_hatched', 'saleable_chicks', 'cull_chicks',
                    'infertile_clears', 'early_dead', 'mid_dead', 'late_dead', 'pipped_dead', 'contaminated_exploders')
    def _check_hatchery_quantities(self):
        for rec in self:
            if rec.received_at_hatchery > 0 and rec.eggs_set > rec.received_at_hatchery:
                raise ValidationError(_(
                    "Eggs set in incubator (%(set)s) cannot exceed eggs received at hatchery (%(recv)s)!"
                ) % {'set': f"{rec.eggs_set:,}", 'recv': f"{rec.received_at_hatchery:,}"})

            if (rec.saleable_chicks + rec.cull_chicks) > rec.chicks_hatched and rec.chicks_hatched > 0:
                raise ValidationError(_(
                    "Saleable chicks (%(sal)s) + cull chicks (%(cull)s) cannot exceed total chicks hatched (%(tot)s)!"
                ) % {'sal': rec.saleable_chicks, 'cull': rec.cull_chicks, 'tot': rec.chicks_hatched})

            total_breakdown = (
                rec.infertile_clears + rec.early_dead + rec.mid_dead +
                rec.late_dead + rec.pipped_dead + rec.contaminated_exploders +
                rec.chicks_hatched
            )
            if rec.eggs_set > 0 and total_breakdown > rec.eggs_set:
                raise ValidationError(_(
                    "Candling breakout and hatched chicks total (%(brk)s) exceeds total eggs set (%(set)s)!"
                ) % {'brk': f"{total_breakdown:,}", 'set': f"{rec.eggs_set:,}"})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New' or not vals.get('name'):
                vals['name'] = self.env['ir.sequence'].next_by_code('taghini.breeder.hatchery.dispatch') or 'New'
        return super().create(vals_list)

    @api.depends('eggs_set', 'infertile_clears', 'saleable_chicks', 'early_dead', 'contaminated_exploders', 'cull_chicks')
    def _compute_hatch_metrics(self):
        for rec in self:
            if rec.eggs_set > 0:
                fertile_count = max(rec.eggs_set - rec.infertile_clears, 0)
                rec.fertility_pct = fertile_count / rec.eggs_set
                rec.hatch_pct_of_set = rec.saleable_chicks / rec.eggs_set
                rec.hatch_pct_of_fertile = (rec.saleable_chicks / fertile_count) if fertile_count > 0 else 0.0
                rec.early_dead_pct = rec.early_dead / rec.eggs_set
                rec.contaminated_pct = rec.contaminated_exploders / rec.eggs_set
                rec.cull_chicks_pct = rec.cull_chicks / rec.eggs_set
            else:
                rec.fertility_pct = 0.0
                rec.hatch_pct_of_set = 0.0
                rec.hatch_pct_of_fertile = 0.0
                rec.early_dead_pct = 0.0
                rec.contaminated_pct = 0.0
                rec.cull_chicks_pct = 0.0

    @api.depends('batch_id.standard_id', 'flock_age_week', 'hatch_pct_of_set')
    def _compute_aa_benchmark(self):
        for rec in self:
            std = rec.batch_id.standard_id if rec.batch_id else False
            if std and rec.flock_age_week:
                line = std.line_ids.filtered(lambda l: l.week == rec.flock_age_week)
                if line:
                    rec.aa_hatch_pct = line[0].aa_hatchability_pct or 0.0
                else:
                    rec.aa_hatch_pct = 0.0
            else:
                rec.aa_hatch_pct = 0.0
            rec.hatch_dev_pts = round((rec.hatch_pct_of_set - rec.aa_hatch_pct) * 100.0, 2)

    @api.depends('batch_id', 'saleable_chicks')
    def _compute_cum_chicks(self):
        for rec in self:
            init_f = rec.batch_id.stocked_female_qty if rec.batch_id else 0
            if init_f > 0:
                all_dispatches = self.search([
                    ('batch_id', '=', rec.batch_id.id),
                    ('dispatch_date', '<=', rec.dispatch_date),
                ])
                tot_saleable = sum(all_dispatches.mapped('saleable_chicks'))
                rec.chicks_per_hen_housed = round(tot_saleable / init_f, 2)
            else:
                rec.chicks_per_hen_housed = 0.0

    def action_start_incubation(self):
        self.write({'state': 'incubating'})

    def action_record_candling(self):
        self.write({'state': 'candled'})

    def action_complete_hatch(self):
        self.write({'state': 'hatched'})
