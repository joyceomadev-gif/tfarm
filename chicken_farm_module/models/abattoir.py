from odoo import models, fields, api, _
from odoo.exceptions import UserError

class AbattoirBatch(models.Model):
    _name = 'taghini.abattoir.batch'
    _description = 'Abattoir Daily Production'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'

    name = fields.Char(string='Batch Reference', required=True, copy=False, readonly=True, default='New')
    date = fields.Date(string='Production Date', default=fields.Date.context_today, required=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

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
    
    # QC FAULTS (From Excel)
    defects_count = fields.Integer(string='Defected/Rejected')
    dirty_section_score = fields.Integer(string='Dirty Section Score (%)')
    cold_room_score = fields.Integer(string='Cold Room Score (%)')

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

    def action_post_inventory(self):
        """ 
        Performs the 'Reverse Manufacturing':
        1. Consumes Live Birds (Raw Material)
        2. Produces Finished Meat (Finished Goods)
        """
        self.ensure_one()
        
        if not self.line_ids:
            raise UserError(_("You cannot post an empty batch. Please add production lines."))
        
        # 1. Define Locations
        source_location = self.harvest_id.flock_id.standard_id.abattoir_location_id
        if not source_location:
            raise UserError(_("The Source Pen does not have an Abattoir Location defined."))

        dest_location = self.harvest_id.flock_id.standard_id.storage_location_id
        
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

        product = self.harvest_id.flock_id.product_id
        uom = self.harvest_id.flock_id.product_id.uom_id
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
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Stock Updated'),
                'message': f'Inventory moved to {self.harvest_id.flock_id.standard_id.storage_location_id.name}. Live birds consumed.',
                'type': 'success',
                'sticky': False,
            }
        }



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
    # Note: You might want a custom field on product.template for this instead
    no_bags = fields.Integer(string='Number of bags')
    quantity = fields.Integer(string='Pieces / Birds')
    weight_kg = fields.Float(string='Total Weight (Kg)')
    avg_weight = fields.Float(string='Avg Unit Wgt', compute='_compute_avg')

    @api.depends('quantity', 'weight_kg')
    def _compute_avg(self):
        for line in self:
            line.avg_weight = line.weight_kg / line.quantity if line.quantity else 0.0