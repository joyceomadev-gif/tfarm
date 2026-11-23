from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class BreederEggRoom(models.Model):
    _name = 'taghini.breeder.egg.room'
    _description = 'Egg Room Daily Stock & Dispatch Ledger'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string='Entry ID', readonly=True, copy=False, default='New')
    batch_id = fields.Many2one('taghini.breeder.batch', string='Breeder Batch', required=True, ondelete='cascade', tracking=True)
    farm_id = fields.Many2one('taghini.farm', related='batch_id.farm_id', store=True, readonly=True)
    company_id = fields.Many2one('res.company', related='batch_id.company_id', store=True, readonly=True)

    date = fields.Date(string='Date', default=fields.Date.context_today, required=True, tracking=True)
    flock_age_week = fields.Integer(string='Flock Age (week)', compute='_compute_flock_age_week', store=True)

    # Stock Reconciliation
    opening_stock = fields.Integer(string='Opening Stock (eggs)', compute='_compute_stock_balances', store=True)
    received_from_pens = fields.Integer(string='Hatching Eggs Received from Pens', compute='_compute_pen_receipts', store=True)
    rejected_in_room = fields.Integer(string='Eggs Rejected / Broken in Egg Room', default=0, tracking=True)
    dispatched_to_hatchery = fields.Integer(string='Eggs Dispatched to Hatchery', default=0, tracking=True)
    dispatch_note_no = fields.Char(string='Dispatch Note No.', tracking=True)
    confirmed_by_hatchery = fields.Integer(string='Count Confirmed by Hatchery', tracking=True)
    closing_stock = fields.Integer(string='Closing Stock (eggs)', compute='_compute_stock_balances', store=True)

    days_since_last_dispatch = fields.Integer(string='Days Since Last Dispatch', compute='_compute_dispatch_interval', store=True)
    transit_loss_pct = fields.Float(string='Transit Loss %', compute='_compute_transit_loss', store=True, digits=(16, 4))

    # Room Climate & Sanitization
    room_min_temp = fields.Float(string='Egg-Room Min. Temp (°C)')
    room_max_temp = fields.Float(string='Egg-Room Max. Temp (°C)')
    room_rh = fields.Float(string='Egg-Room RH (%)')
    fumigated = fields.Boolean(string='Eggs Fumigated / Sanitised (Y/N)', default=False)
    recorded_by = fields.Char(string='Recorded By', default=lambda self: self.env.user.name)

    # Automated Flags
    danger_flags = fields.Text(string='DANGER FLAGS', compute='_compute_flags', store=True)
    data_errors = fields.Text(string='DATA ERRORS', compute='_compute_flags', store=True)
    danger_count = fields.Integer(string='Danger Count', compute='_compute_flags', store=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed / Dispatched'),
    ], default='draft', required=True, tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New' or not vals.get('name'):
                vals['name'] = self.env['ir.sequence'].next_by_code('taghini.breeder.egg.room') or 'New'
        return super().create(vals_list)

    @api.depends('batch_id', 'date')
    def _compute_flock_age_week(self):
        for rec in self:
            if rec.batch_id and rec.batch_id.date and rec.date:
                days = (rec.date - rec.batch_id.date).days
                rec.flock_age_week = max(days // 7, 0)
            else:
                rec.flock_age_week = 0

    @api.depends('batch_id', 'date')
    def _compute_pen_receipts(self):
        for rec in self:
            if not rec.batch_id or not rec.date:
                rec.received_from_pens = 0
                continue
            logs = self.env['taghini.breeder.pen.log'].search([
                ('batch_id', '=', rec.batch_id.id),
                ('date', '=', rec.date),
            ])
            rec.received_from_pens = sum(logs.mapped('hatching_eggs'))

    @api.depends('batch_id', 'date', 'received_from_pens', 'rejected_in_room', 'dispatched_to_hatchery')
    def _compute_stock_balances(self):
        for rec in self:
            if not rec.batch_id or not rec.date:
                rec.opening_stock = 0
                rec.closing_stock = 0
                continue
            prior = self.search([
                ('batch_id', '=', rec.batch_id.id),
                ('date', '<', rec.date),
                ('id', '!=', rec.id or 0),
            ], order='date desc, id desc', limit=1)

            rec.opening_stock = prior.closing_stock if prior else 0
            rec.closing_stock = rec.opening_stock + rec.received_from_pens - (rec.rejected_in_room or 0) - (rec.dispatched_to_hatchery or 0)

    @api.constrains('closing_stock')
    def _check_closing_stock(self):
        for rec in self:
            if rec.closing_stock < 0:
                raise ValidationError(_(
                    "Negative Egg Room Closing Stock (%s)!\n\n"
                    "Dispatched (%s) + Rejected (%s) exceeds Opening Stock (%s) + Received from Pens (%s)."
                ) % (rec.closing_stock, rec.dispatched_to_hatchery, rec.rejected_in_room, rec.opening_stock, rec.received_from_pens))

    @api.depends('batch_id', 'date', 'dispatched_to_hatchery')
    def _compute_dispatch_interval(self):
        for rec in self:
            if not rec.batch_id or not rec.date:
                rec.days_since_last_dispatch = 0
                continue
            last_dispatch = self.search([
                ('batch_id', '=', rec.batch_id.id),
                ('date', '<', rec.date),
                ('dispatched_to_hatchery', '>', 0),
                ('id', '!=', rec.id or 0),
            ], order='date desc, id desc', limit=1)

            if last_dispatch:
                rec.days_since_last_dispatch = (rec.date - last_dispatch.date).days
            else:
                rec.days_since_last_dispatch = 0

    @api.depends('dispatched_to_hatchery', 'confirmed_by_hatchery')
    def _compute_transit_loss(self):
        for rec in self:
            if rec.dispatched_to_hatchery > 0 and rec.confirmed_by_hatchery > 0:
                diff = rec.dispatched_to_hatchery - rec.confirmed_by_hatchery
                rec.transit_loss_pct = max(diff / rec.dispatched_to_hatchery, 0.0)
            else:
                rec.transit_loss_pct = 0.0

    @api.depends('days_since_last_dispatch', 'room_min_temp', 'room_max_temp', 'room_rh', 'transit_loss_pct', 'dispatched_to_hatchery', 'dispatch_note_no')
    def _compute_flags(self):
        for rec in self:
            dangers = []
            errors = []

            # Storage age flag (using batch threshold)
            max_days = rec.batch_id.t_dispatch_interval if (rec.batch_id and rec.batch_id.t_dispatch_interval) else 7
            if rec.days_since_last_dispatch > max_days:
                dangers.append(f"D23 Hatching egg dispatch interval exceeded (>{max_days} days in storage)")

            # Climate flags
            if rec.room_max_temp and rec.room_max_temp > 21.0:
                dangers.append("D28 Egg-room max temperature above recommended (max 21°C)")
            if rec.room_min_temp and rec.room_min_temp < 15.0:
                dangers.append("D29 Egg-room min temperature below recommended (min 15°C)")
            if rec.room_rh and (rec.room_rh < 70.0 or rec.room_rh > 85.0):
                dangers.append("D30 Egg-room relative humidity out of range (70-85%)")

            # Transit loss flag
            if rec.transit_loss_pct > 0.005:
                dangers.append("D31 Transit breakage high (>0.5%)")

            # Missing dispatch note
            if rec.dispatched_to_hatchery > 0 and not rec.dispatch_note_no:
                errors.append("E01 Missing dispatch note number")

            rec.danger_flags = "; ".join(dangers) if dangers else False
            rec.data_errors = "; ".join(errors) if errors else False
            rec.danger_count = len(dangers)

    def action_confirm_dispatch(self):
        self.write({'state': 'confirmed'})

    def write(self, vals):
        res = super().write(vals)
        cascade_fields = {'date', 'rejected_in_room', 'dispatched_to_hatchery'}
        if any(f in vals for f in cascade_fields):
            self._recompute_subsequent_egg_rooms()
        return res

    def unlink(self):
        for rec in self:
            if rec.state == 'confirmed':
                raise UserError(_("You cannot delete a confirmed Egg Room record."))
        batches = self.mapped('batch_id')
        dates = [d for d in self.mapped('date') if d]
        min_date = min(dates) if dates else False
        res = super().unlink()
        if batches and min_date:
            subsequent = self.search([
                ('batch_id', 'in', batches.ids),
                ('date', '>=', min_date),
            ], order='date asc, id asc')
            if subsequent:
                subsequent._compute_stock_balances()
        return res

    def _recompute_subsequent_egg_rooms(self):
        for rec in self:
            if rec.batch_id and rec.date:
                subsequent = self.search([
                    ('batch_id', '=', rec.batch_id.id),
                    ('date', '>=', rec.date),
                    ('id', '!=', rec.id)
                ], order='date asc, id asc')
                if subsequent:
                    subsequent._compute_stock_balances()
