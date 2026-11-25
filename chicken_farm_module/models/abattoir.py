from odoo import models, fields, api, _
from odoo.exceptions import UserError

class AbattoirBatch(models.Model):
    _name = 'taghini.abattoir.batch'
    _description = 'Abattoir Daily Production'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'

    name = fields.Char(string='Batch Reference', required=True, copy=False, readonly=True, default='New')
    date = fields.Date(string='Production Date', default=fields.Date.context_today, required=True)
    company_id = fields.Many2one(
        'res.company', string='Company',
        compute='_compute_company_id', store=True, readonly=False,
        default=lambda self: self.env.company
    )
    farm_id = fields.Many2one(
        'taghini.farm', string='Farm',
        related='harvest_id.farm_id', store=True, readonly=True
    )
    abattoir_id = fields.Many2one(
        'taghini.abattoir', string='Abattoir',
        related='harvest_id.abattoir_id', store=True, readonly=True
    )

    # --- TIMING (From Excel) ---
    start_time = fields.Float(string='Start Time')
    end_time = fields.Float(string='End Time')
    production_hours = fields.Float(string='Duration', compute='_compute_duration')

    # --- INPUT (From Harvest) ---
    harvest_id = fields.Many2one('taghini.harvest', string='Source Harvest', domain=[('state', '=', 'done')])
    pen_id = fields.Many2one('taghini.pen', string='Pen',related='harvest_id.pen_id' )
    batch_id = fields.Many2one('taghini.chicken.batch', string='Batch number',related='harvest_id.flock_id.batch_id' )
    input_birds = fields.Integer(string='Birds Sent', related='harvest_id.birds_received', store=True)
    input_weight_kg = fields.Float(string='Weight (Kg)', related='harvest_id.total_live_weight', store=True)

    # --- OUTPUT LINES ---
    line_ids = fields.One2many('taghini.abattoir.line', 'batch_id', string='Production Output')

    # Note: These point to the same model and use the same inverse field ('batch_id')
    series_line_ids = fields.One2many('taghini.abattoir.line', 'batch_id', 
                                      domain=[('category_type', '=', 'series')], string='Chicken Series')
    
    parts_line_ids = fields.One2many('taghini.abattoir.line', 'batch_id', 
                                     domain=[('category_type', '=', 'parts')], string='Chicken Parts')
    
    cuts_line_ids = fields.One2many('taghini.abattoir.line', 'batch_id', 
                                    domain=[('category_type', '=', 'cuts')], string='Chicken Cuts')
    
    residuals_line_ids = fields.One2many('taghini.abattoir.line', 'batch_id', 
                                         domain=[('category_type', '=', 'residuals')], string='Residuals')
    
    # --- SUMMARY METRICS ---
    total_output_qty = fields.Integer(string='Total Birds Processed', compute='_compute_totals', store=True)
    total_output_weight_kg = fields.Float(string='Total Output Weight', compute='_compute_totals', store=True)
    
    # YIELD (Crucial KPI)
    yield_percentage = fields.Float(string='Yield %', compute='_compute_totals', store=True, 
                                    help="(Output Weight / Input Live Weight) * 100")
    
    processing_loss_kg = fields.Float(string='Process Loss (Kg)', compute='_compute_totals', store=True)

    # --- STAFF & QC ---
    manager_id = fields.Many2one('res.users', string='Abattoir Manager', default=lambda self: self.env.user)
    attendants_present_percent = fields.Float(string='Attendants Present %')

    # === SECTION SUPERVISORS (Task D) ===
    dirty_section_supervisor_id = fields.Many2one('res.users', string='Dirty Section Supervisor')
    grading_supervisor_id = fields.Many2one('res.users', string='Grading Unit Supervisor')
    packaging_supervisor_id = fields.Many2one('res.users', string='Packaging/Cold Room Supervisor')
    qa_shopfloor_id = fields.Many2one('res.users', string='QA on Shopfloor')
    maintenance_count = fields.Integer(string='Maintenance Count on Shopfloor')
    production_manager_id = fields.Many2one('res.users', string='Production Manager')

    # QC FAULTS (From Excel)
    defects_count = fields.Integer(string='Defected/Rejected')
    dirty_section_score = fields.Integer(string='Dirty Section Score (%)')
    cold_room_score = fields.Integer(string='Cold Room Score (%)')

    # === INSPECTOR / QC RATINGS (Task E) ===
    inspector_rating = fields.Selection([
        ('1', '1 - Very Poor'),
        ('2', '2 - Poor'),
        ('3', '3 - Acceptable'),
        ('4', '4 - Good'),
        ('5', '5 - Excellent'),
    ], string='Inspector Rating', help="Rating given by inspector during QC visit.")
    qc_rating = fields.Selection([
        ('1', '1 - Very Poor'),
        ('2', '2 - Poor'),
        ('3', '3 - Acceptable'),
        ('4', '4 - Good'),
        ('5', '5 - Excellent'),
    ], string='QC Department Rating', help="Rating given by QC department — used to evaluate farm managers.")

    # Bagging link
    bagging_id = fields.Many2one('taghini.abattoir.bagging', string='Bagging Record', readonly=True)
    bagging_state = fields.Selection(related='bagging_id.state', string='Bagging Status', store=True)

    # storage_location_id = fields.Many2one(
    #     'stock.location', 
    #     string='Target Freezer/Store', 
    #     domain="[('usage', '=', 'internal'), ('company_id', '=', company_id)]",
    #     required=True,
    #     default=lambda self: self.env['stock.location'].search([
    #         ('company_id', '=', self.env.company.id), 
    #         ('usage', '=', 'internal')
    #     ], limit=1)
    # )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('reception', '1. Verification (Reception)'),  # Corresponds to Image 1
        ('slaughtering', '2. Slaughtering'),           # Corresponds to Image 2
        ('production', '3. Production (Cutting)'),
        ('done', 'Done')
    ], string="Process Status", default='draft', tracking=True)

    # --- 2. VERIFICATION FIELDS (Image 1) ---
    # "Number of Birds"
    birds_arrived = fields.Integer(string="Number of Birds (Arrived)")
    
    # "Total weight: kg"
    weight_arrived = fields.Float(string="Total Weight (kg)")
    
    # "Average weight: kg" (Computed)
    average_weight_arrived = fields.Float(
        string="Avg Weight (kg)", 
        compute="_compute_verification_stats", 
        store=True
    )
    
    # "Condition of birds"
    condition_of_birds = fields.Selection([
        ('active', 'Active'),
        ('stressed', 'Stressed'),
        ('weak', 'Weak'),
        ('mixed', 'Mixed')
    ], string="Condition of Birds", default='active')

    # "Mortality" & "% Mortality"
    mortality_arrived = fields.Integer(string="Mortality (Dead on Arrival)")
    mortality_percentage = fields.Float(
        string="% Mortality", 
        compute="_compute_verification_stats", 
        store=True
    )

    # "NO OF DEFECTED CHICKEN" & "%"
    defected_birds = fields.Integer(string="No. of Defected Chicken")
    defected_percentage = fields.Float(
        string="% Defected", 
        compute="_compute_verification_stats", 
        store=True
    )

    # --- 3. SLAUGHTERING INFO FIELDS (Image 2) ---
    # "Hanging Time" (Start/End) -> "Total hanging hour"
    hanging_start_time = fields.Datetime(string="Hanging Start Time")
    hanging_end_time = fields.Datetime(string="Hanging End Time")
    total_hanging_duration = fields.Char(
        string="Total Hanging Hour", 
        compute="_compute_hanging_duration"
    )

    # "Bleeding time"
    bleeding_time = fields.Char(string="Bleeding Time", default="4min")

    # "Scalding time/Temp"
    scalding_time = fields.Char(string="Scalding Time", default="2min")
    scalding_temp = fields.Float(string="Scalding Temp (°C)", default=62.1)

    # "Evisceration time"
    evisceration_time = fields.Char(string="Evisceration Time")

    # "stunning time/volt"
    stunning_time = fields.Char(string="Stunning Time", default="20Sec")
    stunning_voltage = fields.Float(string="Stunning Volt (V)", default=43.0)

    # "Time last bird leaves the chiller"
    chiller_exit_time = fields.Datetime(string="Time Last Bird Leaves Chiller")

    # "packaging - locking of blast (mins)"
    blast_locking_time = fields.Datetime(string="Packaging/Locking of Blast")

    @api.depends('abattoir_id', 'abattoir_id.company_id', 'harvest_id', 'harvest_id.company_id')
    def _compute_company_id(self):
        for rec in self:
            rec.company_id = (
                rec.abattoir_id.company_id
                or rec.harvest_id.company_id
                or rec.company_id
                or self.env.company
            )

    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        for record in self:
            if record.end_time > record.start_time:
                record.production_hours = record.end_time - record.start_time
            else:
                record.production_hours = 0.0

    @api.depends('line_ids.quantity', 'line_ids.weight_kg', 'input_weight_kg')
    def _compute_totals(self):
        for record in self:
            qty = sum(record.line_ids.mapped('quantity'))
            wgt = sum(record.line_ids.mapped('weight_kg'))
            
            record.total_output_qty = qty
            record.total_output_weight_kg = wgt
            
            if record.input_weight_kg > 0:
                record.yield_percentage = (wgt / record.input_weight_kg) * 100
                record.processing_loss_kg = record.input_weight_kg - wgt
            else:
                record.yield_percentage = 0.0
                record.processing_loss_kg = 0.0

    @api.depends('birds_arrived', 'weight_arrived', 'mortality_arrived', 'defected_birds')
    def _compute_verification_stats(self):
        for record in self:
            # 1. Avg Weight
            if record.birds_arrived > 0:
                record.average_weight_arrived = record.weight_arrived / record.birds_arrived
                record.mortality_percentage = (record.mortality_arrived / record.birds_arrived)
                record.defected_percentage = (record.defected_birds / record.birds_arrived)
            else:
                record.average_weight_arrived = 0.0
                record.mortality_percentage = 0.0
                record.defected_percentage = 0.0

    @api.depends('hanging_start_time', 'hanging_end_time')
    def _compute_hanging_duration(self):
        for record in self:
            if record.hanging_start_time and record.hanging_end_time:
                duration = record.hanging_end_time - record.hanging_start_time
                total_seconds = int(duration.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                # Formatting like the image: "3hr:37min"
                record.total_hanging_duration = f"{hours}hr:{minutes}min"
            else:
                record.total_hanging_duration = ""

    # --- BUTTON ACTIONS ---
    def action_start_reception(self):
        self.state = 'reception'

    def action_confirm_verification(self):
        """ Validates reception and moves to Slaughtering """
        if self.birds_arrived <= 0:
            raise UserError(_("Please input the 'Number of Birds' arrived before proceeding."))
        self.state = 'slaughtering'

    def action_confirm_slaughtering(self):
        """ Validates slaughter info and moves to Production """
        self.state = 'production'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('taghini.abattoir') or 'New'
        return super().create(vals_list)

    def unlink(self):
        for record in self:
            if record.state == 'done':
                raise UserError(_("You cannot delete a Production Batch that has already been posted to stock."))
        return super().unlink()

    def action_view_bagging(self):
        """Task A: Smart button to open the linked Bagging record."""
        self.ensure_one()
        if not self.bagging_id:
            return {}
        return {
            'name': _('Bagging & Freezer'),
            'type': 'ir.actions.act_window',
            'res_model': 'taghini.abattoir.bagging',
            'view_mode': 'form',
            'res_id': self.bagging_id.id,
        }

    def action_create_bagging(self):
        """
        Validate required production details, create a Bagging record from
        production output if one does not already exist, and open it.
        """
        self.ensure_one()
        if self.bagging_id:
            return self.action_view_bagging()

        if self.state not in ('production', 'done'):
            raise UserError(_("You can only create a bagging record once the batch reaches Production."))

        if not self.line_ids:
            raise UserError(_("Please add at least one production output line before creating a bagging record."))

        incomplete_lines = self.line_ids.filtered(
            lambda l: not l.product_id or (l.weight_kg <= 0 and l.quantity <= 0)
        )
        if incomplete_lines:
            names = ", ".join(incomplete_lines.mapped(lambda l: l.product_id.name or _('Unnamed Line')))
            raise UserError(_(
                "Please enter a positive Weight (Kg) or Pieces/Birds for all production output lines before moving to bagging: %s"
            ) % names)

        bagging = self._create_bagging_from_output()
        self.bagging_id = bagging.id

        return {
            'name': _('Bagging & Freezer'),
            'type': 'ir.actions.act_window',
            'res_model': 'taghini.abattoir.bagging',
            'view_mode': 'form',
            'res_id': bagging.id,
            'target': 'current',
        }

    def action_post_inventory(self):
        """ 
        Performs the 'Reverse Manufacturing':
        1. Consumes Live Birds (Raw Material)
        2. Produces Finished Meat (Finished Goods)
        """
        self.ensure_one()
        if self.state == 'done':
            raise UserError(_("This Production Batch has already been posted to stock."))

        if not self.line_ids:
            raise UserError(_("You cannot post an empty batch. Please add production lines."))
        
        # 1. Define Locations
        # Prefer dedicated Abattoir site; fall back to farm-level locations or standard profile
        farm = self.harvest_id.flock_id.pen_model_id.farm_id or self.harvest_id.farm_id
        abattoir = self.abattoir_id or (farm.default_abattoir_id if farm else False)
        source_location = (
            (abattoir.abattoir_location_id if abattoir else False)
            or (farm.abattoir_location_id if farm else False)
            or self.harvest_id.flock_id.standard_id.abattoir_location_id
        )
        if not source_location:
            raise UserError(_(
                "No Abattoir Location defined. Set it on the Abattoir (Configuration > Abattoirs), "
                "on the Farm, or on the Growth Standard."
            ))

        dest_location = (
            (abattoir.storage_location_id if abattoir else False)
            or (abattoir.freezer_location_id if abattoir else False)
            or (farm.storage_location_id if farm else False)
            or (farm.freezer_location_id if farm else False)
            or self.harvest_id.flock_id.standard_id.storage_location_id
        )
        if not dest_location:
            raise UserError(_(
                "No Storage or Freezer Location defined. Set it on the Abattoir (Configuration > Abattoirs), "
                "on the Farm, or on the Growth Standard."
            ))
        
        # Search for Virtual Production Location
        production_loc_record = self.env['stock.location'].search([
            ('usage', '=', 'production'),
            ('company_id', 'in', [self.company_id.id, False])
        ], limit=1)
        
        if not production_loc_record:
            raise UserError(_("Could not find a Virtual Production location. Please contact your administrator."))
            
        production_location = production_loc_record
        stock_move_obj = self.env['stock.move']
        
        def create_and_force_move(product, qty, uom, loc_from, loc_to, company_id, origin):
            """ Helper to handle the creation and forcing of a move """
            move = stock_move_obj.sudo().create({
                'product_id': product.id,
                'product_uom_qty': qty,
                'product_uom': uom.id,
                'location_id': loc_from.id,
                'location_dest_id': loc_to.id,
                'date': fields.Datetime.now(),
                'company_id': company_id.id,
                'origin': origin,
                'state': 'draft',
            })
            move._action_confirm()
            move._action_assign()
            
            for line in move.move_line_ids:
                line.quantity = line.quantity_product_uom
            
            if not move.move_line_ids:
                self.env['stock.move.line'].sudo().create({
                    'move_id': move.id,
                    'product_id': move.product_id.id,
                    'product_uom_id': move.product_uom.id,
                    'location_id': move.location_id.id,
                    'location_dest_id': move.location_dest_id.id,
                    'quantity': qty,
                })
            
            move.picked = True
            move._action_done()
            return move

        # Identify Transit Location if needed
        transit_loc = self.env.ref('stock.location_inter_company', raise_if_not_found=False)
        if not transit_loc:
            transit_loc = self.env['stock.location'].sudo().search([
                ('usage', '=', 'transit'),
                ('company_id', '=', False)
            ], limit=1)
        # ==========================================================
        # END OF CHANGED BLOCK
        # ==========================================================
        
        # ---------------------------------------------------
        # 1. CONSUME LIVE BIRDS (Input)
        # ---------------------------------------------------
        # ==========================================================
        # START OF CHANGED BLOCK: INTER-COMPANY CONSUMPTION
        # ==========================================================
        src_company = source_location.company_id or self.company_id
        prod_company = self.company_id # Production happens in current company

        if self.harvest_id.flock_type == 'breeder' and self.harvest_id.breeder_flock_id:
            bird_tmpl = self.harvest_id.breeder_flock_id.batch_id.bird_variant_id
            product = bird_tmpl.product_variant_id or bird_tmpl.product_variant_ids[:1]
        else:
            product = self.harvest_id.flock_id.product_id
        if not product:
            raise UserError(_("Could not determine the live bird product from the Source Harvest."))
        uom = product.uom_id
        qty = self.input_birds

        if src_company.id == prod_company.id:
            # Same Company
            create_and_force_move(product, qty, uom, source_location, production_location, prod_company, self.name)
        else:
            # Inter-Company
            if not transit_loc: raise UserError(_("No Inter-Company Transit Location found."))
            # Step 1: Source -> Transit
            create_and_force_move(product, qty, uom, source_location, transit_loc, src_company, f"{self.name} (Consume Out)")
            # Step 2: Transit -> Production
            create_and_force_move(product, qty, uom, transit_loc, production_location, prod_company, f"{self.name} (Consume In)")
        # ==========================================================
        # END OF CHANGED BLOCK
        # ==========================================================

        # ---------------------------------------------------
        # 2. PRODUCE MEAT PRODUCTS (Output)
        # ---------------------------------------------------
        dest_company = dest_location.company_id or self.company_id

        for line in self.line_ids:
            qty_to_produce = 0.0
            
            # --- WEIGHT DETECTION ---
            uom_line = line.product_id.uom_id
            is_weight = False
            
            if hasattr(uom_line, 'category_id') and uom_line.category_id:
                if uom_line.category_id.name.lower() in ['weight', 'poids', 'mass', 'gewicht']:
                    is_weight = True
            
            if not is_weight and uom_line.name:
                if any(w in uom_line.name.lower() for w in ['kg', 'gram', 'lb', 'oz']):
                    is_weight = True

            if is_weight:
                qty_to_produce = line.weight_kg 
            else:
                qty_to_produce = line.quantity

            # ==========================================================
            # START OF CHANGED BLOCK: INTER-COMPANY PRODUCTION
            # ==========================================================
            if prod_company.id == dest_company.id:
                # Same Company
                create_and_force_move(line.product_id, qty_to_produce, uom_line, production_location, dest_location, prod_company, self.name)
            else:
                # Inter-Company
                if not transit_loc: raise UserError(_("No Inter-Company Transit Location found."))
                # Step 1: Production -> Transit
                create_and_force_move(line.product_id, qty_to_produce, uom_line, production_location, transit_loc, prod_company, f"{self.name} (Prod Out)")
                # Step 2: Transit -> Destination
                create_and_force_move(line.product_id, qty_to_produce, uom_line, transit_loc, dest_location, dest_company, f"{self.name} (Prod In)")

        # Lock the Batch
        self.state = 'done'

        # === TASK C4: Alert MD if bird count discrepancy ===
        self._check_and_alert_md_abattoir()

        # === TASK A5: Auto-create Bagging record from production output if not already created ===
        bagging = self.bagging_id
        if not bagging:
            bagging = self._create_bagging_from_output()
            self.bagging_id = bagging.id

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Stock Updated — Bagging Ready'),
                'message': (
                    f'Inventory posted. Bagging record {bagging.name} is linked. '
                    f'Live birds consumed from abattoir location.'
                ),
                'type': 'success',
                'sticky': False,
            }
        }

    def _check_and_alert_md_abattoir(self):
        """
        Task C4: If produced bird count ≠ input birds − abattoir mortality,
        send an immediate chatter alert to the MD.
        """
        self.ensure_one()
        input_birds = self.input_birds
        abattoir_mortality = self.mortality_arrived or 0
        expected_output = input_birds - abattoir_mortality
        actual_output = sum(self.series_line_ids.mapped('quantity')) if self.series_line_ids else self.total_output_qty

        if actual_output != expected_output:
            diff = expected_output - actual_output
            md_users = self._get_md_users()
            if md_users:
                partners = md_users.mapped('partner_id')
                body = _(
                    "<b>⚠️ Abattoir Bird Count Discrepancy — Immediate Alert</b><br/>"
                    "Batch: <b>%(batch)s</b><br/>"
                    "Birds Sent: <b>%(sent)d</b><br/>"
                    "Abattoir Mortality: <b>%(mort)d</b><br/>"
                    "Expected Produced: <b>%(expected)d</b><br/>"
                    "Actual Produced: <b>%(actual)d</b><br/>"
                    "<b style='color:red;'>Unaccounted: %(diff)d birds</b>"
                ) % {
                    'batch': self.name,
                    'sent': input_birds,
                    'mort': abattoir_mortality,
                    'expected': expected_output,
                    'actual': actual_output,
                    'diff': abs(diff),
                }
                self.message_post(
                    body=body,
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                    partner_ids=partners.ids,
                )

    def _create_bagging_from_output(self):
        """
        Task A: Create a Bagging record auto-populated from production lines.
        """
        self.ensure_one()
        bagging = self.env['taghini.abattoir.bagging'].create({
            'batch_id': self.id,
            'date': self.date,
        })
        lines_to_create = []
        for line in self.line_ids:
            lines_to_create.append({
                'bagging_id': bagging.id,
                'product_id': line.product_id.id,
                'no_bags': 0,
                'quantity': line.quantity,
                'weight_kg': line.weight_kg,
            })
        if lines_to_create:
            self.env['taghini.abattoir.bagging.line'].create(lines_to_create)
        return bagging

    def get_bag_count_for_product(self, product):
        """Return total bagged count for a product from linked bagging record."""
        self.ensure_one()
        if not self.bagging_id or not product:
            return 0
        return sum(self.bagging_id.line_ids.filtered(lambda l: l.product_id.id == product.id).mapped('no_bags'))

    def _get_md_users(self):
        """Return MD users from farm or fallback to system param."""
        farm = self.harvest_id.flock_id.pen_model_id.farm_id
        if farm and farm.md_user_id:
            return farm.md_user_id
        # Fallback: return all users in group_taghini_farm_manager
        manager_group = self.env.ref('chicken_farm_module.group_taghini_farm_manager', raise_if_not_found=False)
        if manager_group:
            return manager_group.users
        return self.env['res.users']



class AbattoirLine(models.Model):
    _name = 'taghini.abattoir.line'
    _description = 'Production Output Line'

    batch_id = fields.Many2one('taghini.abattoir.batch', string='Batch')
    product_id = fields.Many2one('product.template', string='Product / Series', required=True)
    
    # Categories to help grouping in the view (Whole vs Cut vs Offal)
    category_type = fields.Selection(
        related='product_id.abattoir_type', 
        string='Type', 
        store=True, 
        readonly=True
    )
    quantity = fields.Integer(string='Pieces / Birds')
    no_bags = fields.Integer(
        string='Number of Bags',
        compute='_compute_no_bags',
        store=True,
        readonly=True,
        help="Read-only count synced from Actual Bags entered in Bagging."
    )
    grading_line_id = fields.Many2one(
        'taghini.grading.checklist.line', string='Series Spec',
        compute='_compute_grading_line', store=True
    )
    avg_weight = fields.Float(
        string='Avg Unit Wgt', compute='_compute_weights', store=True, readonly=True
    )
    weight_kg = fields.Float(
        string='Total Weight (Kg)', compute='_compute_weights', store=True, readonly=False
    )

    @api.depends('batch_id.bagging_id', 'batch_id.bagging_id.line_ids.no_bags',
                 'batch_id.bagging_id.line_ids.product_id', 'product_id')
    def _compute_no_bags(self):
        for line in self:
            bagging = line.batch_id.bagging_id
            if bagging and line.product_id:
                line.no_bags = sum(
                    bagging.line_ids.filtered(lambda bl: bl.product_id.id == line.product_id.id).mapped('no_bags')
                )
            else:
                line.no_bags = 0

    @api.depends('product_id', 'product_id.grading_line_id', 'product_id.name')
    def _compute_grading_line(self):
        checklist = self.env['taghini.grading.checklist'].search([('is_default', '=', True)], limit=1)
        if not checklist:
            checklist = self.env['taghini.grading.checklist'].search([], limit=1)
        for line in self:
            if line.product_id.grading_line_id:
                line.grading_line_id = line.product_id.grading_line_id
                continue
            matched = False
            if checklist and line.product_id:
                prod_name = (line.product_id.name or '').lower()
                if 'head' in prod_name and 'leg' in prod_name:
                    matched = checklist.line_ids.filtered(lambda l: l.is_head_and_leg)[:1]
                if not matched:
                    for cl_line in checklist.line_ids:
                        cl_code_key = (cl_line.name or '').split('/')[0].strip().lower()
                        if cl_code_key and cl_code_key in prod_name:
                            matched = cl_line
                            break
            line.grading_line_id = matched or False

    def _get_nominal_unit_weight(self):
        self.ensure_one()
        spec = self.grading_line_id
        if spec and not spec.is_underweight and not spec.is_head_and_leg:
            if spec.unit_weight_min > 0 and spec.unit_weight_max < 90:
                return round((spec.unit_weight_min + spec.unit_weight_max) / 2.0, 3)
            if self.product_id and self.product_id.weight > 0:
                return self.product_id.weight
            if spec.unit_weight_min > 0:
                return spec.unit_weight_min
        if self.product_id and self.product_id.weight > 0:
            return self.product_id.weight
        return 0.0

    @api.depends('product_id', 'quantity', 'grading_line_id', 'product_id.weight')
    def _compute_weights(self):
        for line in self:
            nominal = line._get_nominal_unit_weight()
            if nominal > 0 and line.quantity > 0:
                line.avg_weight = nominal
                line.weight_kg = round(nominal * line.quantity, 2)
            elif nominal > 0:
                line.avg_weight = nominal
                line.weight_kg = 0.0
            else:
                line.avg_weight = (line.weight_kg / line.quantity) if line.quantity else 0.0