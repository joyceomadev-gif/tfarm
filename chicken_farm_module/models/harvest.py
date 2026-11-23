from odoo import models, fields, api, _
from odoo.exceptions import UserError

class FarmHarvest(models.Model):
    _name = 'taghini.harvest'
    _description = 'Abattoir / Harvest Batch'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'

    name = fields.Char(string='Harvest Reference', required=True, copy=False, readonly=True, default='New')
    date = fields.Date(string='Harvest Date', default=fields.Date.context_today, required=True)

    flock_type = fields.Selection([
        ('broiler', 'Commercial Broiler Flock'),
        ('breeder', 'Breeder Pen Series (Spent Hens)'),
    ], string='Flock Type', default='broiler', required=True, tracking=True)

    company_id = fields.Many2one('res.company', string='Company', compute='_compute_origin_info', store=True, readonly=True)
    farm_id = fields.Many2one('taghini.farm', string='Farm', compute='_compute_origin_info', store=True, readonly=True)
    # Link to Farm
    flock_id = fields.Many2one('taghini.flock', string='Source Broiler Batch', required=False, domain=[('state', '=', 'active')])
    breeder_flock_id = fields.Many2one('taghini.breeder.flock', string='Source Breeder Pen Series', required=False, domain=[('state', '=', 'active')])
    pen_id = fields.Many2one('taghini.pen', string='Source Pen', compute='_compute_origin_info', store=True)

    # --- INPUT METRICS (At the Gate) ---
    birds_received = fields.Integer(string='Birds Received (Head)', help="Number of birds arrived alive at abattoir")
    total_live_weight = fields.Float(string='Total Live Weight (Kg)', help="Total weight of truck/crates")
    
    avg_harvest_weight_g = fields.Float(string='Avg Body Weight (g)', compute='_compute_avg_weight', store=True)

    # --- QUALITY SCORES (The "Look and Feel") ---
    feather_condition = fields.Selection([
        ('excellent', 'Excellent (Clean/Full)'),
        ('good', 'Good'),
        ('fair', 'Fair (Some dirt/patches)'),
        ('poor', 'Poor (Dirty/Bare)')
    ], string='Feather Condition', default='good', tracking=True)
    
    visual_quality = fields.Selection([
        ('premium', 'Premium (Uniform/Healthy)'),
        ('standard', 'Standard'),
        ('irregular', 'Irregular Sizes'),
        ('rejected', 'Many Rejects')
    ], string='Visual Look & Feel', default='standard', tracking=True)
    
    notes = fields.Text(string='Abattoir Notes')

    # --- PERFORMANCE SUMMARY (Auto-Calculated from Log) ---
    total_feed_consumed_kg = fields.Float(string='Total Feed Consumed (Kg)', compute='_compute_performance', store=True)
    total_meds_count = fields.Integer(string='Medication Days', compute='_compute_performance', store=True, help="Count of days meds were applied")
    
    # THE GOLDEN METRIC: Feed Conversion Ratio (FCR)
    fcr = fields.Float(string='FCR (Conversion)', compute='_compute_performance', store=True, 
                       help="Feed Conversion Ratio: Kg of Feed needed to produce 1 Kg of Meat. Lower is better.")

    state = fields.Selection([
        ('draft', 'Draft'),
        ('processing', 'Processing'),
        ('done', 'Completed')
    ], string='Status', default='draft', tracking=True)

    move_id = fields.Many2one('stock.move', string='Stock Move', readonly=True)

    # === TASK C2: Unrecorded birds display on Harvest form ===
    unrecorded_birds = fields.Integer(
        string='Unrecorded / Missing Birds',
        compute='_compute_unrecorded', store=True,
        help=(
            "Birds placed in pen − total mortality − total harvested. "
            "If > 0, there are birds missing from records. "
            "An alert is sent to the MD when this is non-zero after harvest."
        )
    )

    @api.depends('flock_type', 'flock_id', 'breeder_flock_id')
    def _compute_origin_info(self):
        for rec in self:
            if rec.flock_type == 'breeder' and rec.breeder_flock_id:
                rec.company_id = rec.breeder_flock_id.company_id
                rec.farm_id = rec.breeder_flock_id.farm_id
                rec.pen_id = rec.breeder_flock_id.pen_id
            elif rec.flock_id:
                rec.company_id = rec.flock_id.company_id
                rec.farm_id = rec.flock_id.farm_id
                rec.pen_id = rec.flock_id.pen_model_id
            else:
                rec.company_id = False
                rec.farm_id = False
                rec.pen_id = False

    @api.depends('flock_type', 'flock_id', 'flock_id.quantity_placed',
                 'flock_id.log_ids.mortality', 'flock_id.log_ids.harvested_qty',
                 'breeder_flock_id', 'breeder_flock_id.initial_females', 'breeder_flock_id.initial_males',
                 'breeder_flock_id.pen_log_ids.female_mortality', 'breeder_flock_id.pen_log_ids.male_mortality',
                 'birds_received')
    def _compute_unrecorded(self):
        for record in self:
            if record.flock_type == 'breeder' and record.breeder_flock_id:
                placed = (record.breeder_flock_id.initial_females or 0) + (record.breeder_flock_id.initial_males or 0)
                logs = record.breeder_flock_id.pen_log_ids
                total_dead = sum(logs.mapped('female_mortality')) + sum(logs.mapped('male_mortality')) + sum(logs.mapped('female_culls')) + sum(logs.mapped('male_culls'))
                remaining = placed - total_dead - (record.birds_received or 0)
                record.unrecorded_birds = abs(remaining) if (remaining < 0 or record.state == 'done') else 0
            elif record.flock_id:
                placed = record.flock_id.quantity_placed or 0
                total_dead = sum(record.flock_id.log_ids.mapped('mortality'))
                total_harvested = sum(record.flock_id.log_ids.mapped('harvested_qty'))
                remaining = placed - total_dead - total_harvested
                record.unrecorded_birds = abs(remaining) if (remaining < 0 or record.state == 'done') else 0
            else:
                record.unrecorded_birds = 0

    # --- COMPUTATIONS ---
    @api.depends('birds_received', 'total_live_weight')
    def _compute_avg_weight(self):
        for record in self:
            if record.birds_received > 0:
                # Result in Grams
                record.avg_harvest_weight_g = (record.total_live_weight * 1000) / record.birds_received
            else:
                record.avg_harvest_weight_g = 0.0

    @api.depends('flock_type', 'flock_id', 'breeder_flock_id', 'total_live_weight')
    def _compute_performance(self):
        for record in self:
            if record.flock_type == 'breeder' and record.breeder_flock_id:
                logs = record.breeder_flock_id.pen_log_ids
                total_feed_kg = sum(logs.mapped('female_feed_kg')) + sum(logs.mapped('male_feed_kg'))
                record.total_feed_consumed_kg = total_feed_kg
                record.total_meds_count = len(logs.filtered(lambda l: l.danger_count > 0 or l.post_mortem_done))
                if record.total_live_weight > 0:
                    record.fcr = record.total_feed_consumed_kg / record.total_live_weight
                else:
                    record.fcr = 0.0
            elif record.flock_id:
                # 1. Sum Feed from Logs (Stored in Grams, convert to Kg)
                total_feed_g = sum(record.flock_id.log_ids.mapped('feed_consumed_g'))
                record.total_feed_consumed_kg = total_feed_g / 1000.0
                
                # 2. Count Meds
                med_logs = record.flock_id.log_ids.filtered(lambda l: l.medication_line_ids or l.medication_product_id or l.vaccine_name)
                record.total_meds_count = len(med_logs)

                # 3. Calculate FCR (Total Feed Kg / Total Live Weight Kg)
                if record.total_live_weight > 0:
                    record.fcr = record.total_feed_consumed_kg / record.total_live_weight
                else:
                    record.fcr = 0.0
            else:
                record.total_feed_consumed_kg = 0.0
                record.total_meds_count = 0
                record.fcr = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        """ Overridden to generate Sequence Number for every record in the list """
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('taghini.harvest') or 'New'
        return super(FarmHarvest, self).create(vals_list)

    def action_confirm_harvest(self):
        """ 
        1. Creates Internal Transfer (Forced to Done).
        2. UPDATES existing Daily Log OR Creates new one (for broilers).
        3. Updates Flock Status.
        """
        self.ensure_one()

        if self.flock_type == 'breeder':
            if not self.breeder_flock_id:
                raise UserError(_("Please select a Source Breeder Pen Series."))
            bird_template = self.breeder_flock_id.batch_id.bird_variant_id
            product = bird_template.product_variant_id or bird_template.product_variant_ids[:1]
            if not product:
                raise UserError(_("The Breeder Batch does not have a Bird Variant Product."))
            source_loc = self.pen_id.location_id
            dest_loc = (
                self.breeder_flock_id.farm_id.abattoir_location_id
                or self.breeder_flock_id.batch_id.standard_id.abattoir_location_id
            )
            if not dest_loc:
                raise UserError(_(
                    "Destination Abattoir Location is missing. "
                    "Set it on the Farm (Configuration > Farms) or the Breed Standard."
                ))
        else:
            if not self.flock_id:
                raise UserError(_("Please select a Source Batch."))
            if not self.flock_id.product_id:
                raise UserError(_("The Flock does not have a Product defined."))
            product = self.flock_id.product_id
            source_loc = self.pen_id.location_id
            dest_loc = (
                self.flock_id.pen_model_id.farm_id.abattoir_location_id
                or self.flock_id.standard_id.abattoir_location_id
            )
            if not dest_loc:
                raise UserError(_(
                    "Destination Abattoir Location is missing. "
                    "Set it on the Farm (Configuration > Farms) or the Growth Standard."
                ))

        src_company = source_loc.company_id or self.company_id
        dest_company = dest_loc.company_id or self.company_id

        # We need a list to hold moves to process
        moves_to_process = []

        if src_company.id == dest_company.id:
            # --- SAME COMPANY ---
            move_vals = {
                'description_picking': f"Harvest {self.name} - {product.display_name}",
                'product_id': product.id,
                'product_uom_qty': self.birds_received,
                'product_uom': product.uom_id.id,
                'location_id': source_loc.id,
                'location_dest_id': dest_loc.id,
                'date': self.date,
                'company_id': src_company.id,
                'origin': self.name,
                'state': 'draft',
            }
            moves_to_process.append(self.env['stock.move'].sudo().create(move_vals))

        else:
            # --- DIFFERENT COMPANIES (INTER-COMPANY TRANSIT) ---
            transit_loc = self.env.ref('stock.location_inter_company', raise_if_not_found=False)
            if not transit_loc:
                transit_loc = self.env['stock.location'].sudo().search([
                    ('usage', '=', 'transit'),
                    ('company_id', '=', False)
                ], limit=1)
            
            if not transit_loc:
                raise UserError(_("No Inter-Company Transit Location found. Please configure one."))

            move_out_vals = {
                'description_picking': f"Harvest {self.name} Out - {product.display_name}",
                'product_id': product.id,
                'product_uom_qty': self.birds_received,
                'product_uom': product.uom_id.id,
                'location_id': source_loc.id,
                'location_dest_id': transit_loc.id,
                'date': self.date,
                'company_id': src_company.id,
                'origin': f"{self.name} (Out)",
                'state': 'draft',
            }
            moves_to_process.append(self.env['stock.move'].sudo().create(move_out_vals))

            move_in_vals = {
                'description_picking': f"Harvest {self.name} In - {product.display_name}",
                'product_id': product.id,
                'product_uom_qty': self.birds_received,
                'product_uom': product.uom_id.id,
                'location_id': transit_loc.id,
                'location_dest_id': dest_loc.id,
                'date': self.date,
                'company_id': dest_company.id,
                'origin': f"{self.name} (In)",
                'state': 'draft',
            }
            moves_to_process.append(self.env['stock.move'].sudo().create(move_in_vals))

        # --- PROCESS ALL MOVES (FORCE DONE LOGIC) ---
        final_move = False
        
        for move in moves_to_process:
            move._action_confirm()
            move._action_assign()
            
            # 1. Set Done Quantity on existing lines
            for line in move.move_line_ids:
                line.quantity = line.quantity_product_uom

            # 2. Force creation if stock is missing (Negative Inventory)
            if not move.move_line_ids:
                self.env['stock.move.line'].sudo().create({
                    'move_id': move.id,
                    'product_id': move.product_id.id,
                    'product_uom_id': move.product_uom.id,
                    'location_id': move.location_id.id,
                    'location_dest_id': move.location_dest_id.id,
                    'quantity': self.birds_received,
                })
            
            # 3. Mark as Picked and Finalize
            move.picked = True
            move._action_done()
            final_move = move

        self.move_id = final_move.id

        if self.flock_type == 'breeder':
            self.state = 'done'
            self.breeder_flock_id.write({'state': 'closed'})
            self._check_and_alert_md_harvest()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Breeder Depopulation Confirmed'),
                    'message': f'{self.birds_received} spent breeders transferred to Abattoir. Flock {self.breeder_flock_id.name} closed.',
                    'type': 'success',
                    'sticky': False,
                }
            }

        # === TASK C3: Compute unrecorded birds and alert MD ===
        self._check_and_alert_md_harvest()

        # 2. UPDATE OR CREATE DAILY LOG (Keep existing logic for broilers)
        existing_log = self.env['taghini.daily.log'].search([
            ('flock_id', '=', self.flock_id.id),
            ('date', '=', self.date)
        ], limit=1)

        if existing_log:
            existing_log.write({
                'harvested_qty': existing_log.harvested_qty + self.birds_received,
                'harvested_weight': existing_log.harvested_weight + self.total_live_weight,
                'state': 'done',
                'remarks': f"{existing_log.remarks or ''}\nHarvest: {self.name} ({self.birds_received} birds)"
            })
        else:
            self.env['taghini.daily.log'].create({
                'flock_id': self.flock_id.id,
                'date': self.date,
                'harvested_qty': self.birds_received,
                'harvested_weight': self.total_live_weight,
                'state': 'done',
                'remarks': f"Harvest Reference: {self.name}"
            })

        # 3. UPDATE FLOCK STATUS
        self.state = 'done'
        self.flock_id._compute_current_birds() 
        if self.flock_id.current_birds <= 0:
            self.flock_id.write({'state': 'closed'})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Harvest Confirmed'),
                'message': f'{self.birds_received} birds transferred to Abattoir.',
                'type': 'success',
                'sticky': False,
            }
        }


    def _check_and_alert_md_harvest(self):
        """
        Task C3: After harvest, compute unrecorded birds and send alert to MD if non-zero.
        """
        self.ensure_one()
        if self.flock_type == 'breeder':
            flock = self.breeder_flock_id
            if not flock:
                return
            placed = (flock.initial_females or 0) + (flock.initial_males or 0)
            logs = flock.pen_log_ids
            total_dead = sum(logs.mapped('female_mortality')) + sum(logs.mapped('male_mortality')) + sum(logs.mapped('female_culls')) + sum(logs.mapped('male_culls'))
            total_harvested = self.birds_received or 0
            farm = flock.farm_id
        else:
            flock = self.flock_id
            if not flock:
                return
            placed = flock.quantity_placed or 0
            total_dead = sum(flock.log_ids.mapped('mortality'))
            total_harvested = sum(flock.log_ids.mapped('harvested_qty'))
            farm = flock.pen_model_id.farm_id

        total_accounted = total_dead + total_harvested
        unrecorded = placed - total_accounted

        if unrecorded != 0:
            md_user = farm.md_user_id if farm else self.env['res.users']
            if not md_user:
                manager_group = self.env.ref('chicken_farm_module.group_taghini_farm_manager', raise_if_not_found=False)
                md_user = manager_group.users[:1] if manager_group else self.env['res.users']

            if md_user:
                body = _(
                    "<b>⚠️ Unrecorded/Unaccounted Birds — Farm Harvest Alert</b><br/>"
                    "Harvest: <b>%(harvest)s</b> | Farm: <b>%(farm)s</b><br/>"
                    "Birds Placed in Pen: <b>%(placed)d</b><br/>"
                    "Total Mortality/Culls: <b>%(dead)d</b><br/>"
                    "Total Harvested: <b>%(harvested)d</b><br/>"
                    "<b style='color:red;'>Unrecorded/Unaccounted: %(unrecorded)d birds</b><br/>"
                    "Please investigate immediately."
                ) % {
                    'harvest': self.name,
                    'farm': farm.name if farm else 'N/A',
                    'placed': placed,
                    'dead': total_dead,
                    'harvested': total_harvested,
                    'unrecorded': abs(unrecorded),
                }
                self.message_post(
                    body=body,
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                    partner_ids=md_user.mapped('partner_id').ids,
                )
