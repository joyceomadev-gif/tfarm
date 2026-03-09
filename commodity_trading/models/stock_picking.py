from odoo import models, fields, api, exceptions

class StockPicking(models.Model):
    _inherit = 'stock.picking'



    # Weighbridge capture (From Step 3)
    weighbridge_in = fields.Float(string='Weighbridge IN (KG)', tracking=True)
    weighbridge_out = fields.Float(string='Weighbridge OUT / Empty Truck (KG)', tracking=True)
    gross_weight = fields.Float(string='Gross Weight (KG)', compute='_compute_weighbridge_weights', store=True)

    bag_count = fields.Integer(string='Number of Bags Used')
    bag_discount = fields.Float(string='Bag Discount (KG)', compute='_compute_weighbridge_weights', store=True)
    moisture_discount = fields.Float(string='Moisture Discount (%)')

    net_weight = fields.Float(string='Net Received Weight (KG)', compute='_compute_weighbridge_weights', store=True)
    

    quality_discount_weight = fields.Float(string='Quality Discount (%)', tracking=True, help="This does NOT reduce physical stock, only payable weight.")
    payable_weight = fields.Float(string='Payable Weight (KG)', compute='_compute_payable_weight', store=True)

    # ==========================================
    # STEP 5 ADDITIONS: INVOICING TRACKING
    # ==========================================
    commodity_invoice_id = fields.Many2one('account.move', string='Linked Invoice', copy=False, readonly=True)
    is_invoiced = fields.Boolean(string='Is Invoiced', compute='_compute_is_invoiced', store=True)

    commodity_contract_id = fields.Many2one(
        'commodity.contract', 
        string='Commodity Contract',
        compute='_compute_contract_from_sale',
        store=True,
        readonly=False
    )
    is_discount_invoiced = fields.Boolean(string='Discount Invoiced', copy=False, default=False)    

# ==========================================
    # QUALITY CONTROL (QC) PARAMETERS
    # ==========================================
    is_qc_locked = fields.Boolean(string='QC Locked', default=False, copy=False)

    # 1. ADM Group
    qc_sieve = fields.Float(string='Sieve (%)')
    qc_fm = fields.Float(string='FM (%)')
    qc_flat = fields.Float(string='FLAT (%)')
    qc_adm_sum = fields.Float(string='ADM Sum', readonly=True)

    # 2. CRM Group
    qc_bb = fields.Float(string='BB (%)')
    qc_fragment = fields.Float(string='Fragment (%)')
    qc_cluster = fields.Float(string='Cluster (%)')
    qc_crm_sum = fields.Float(string='CRM Sum', readonly=True)

    # 3. TD Group
    qc_mould = fields.Float(string='Mould (%)')
    qc_insect = fields.Float(string='Insect (%)')
    qc_td_sum = fields.Float(string='TD Sum', readonly=True)

    # 4. Bean Bloc
    qc_slaty = fields.Float(string='Slaty (%)')
    qc_moisture = fields.Float(string='Moisture Content (%)')
    qc_bean_count = fields.Float(string='Bean Count')

    # Status
    qc_status = fields.Selection([
        ('pending', 'Pending QC'),
        ('pass', 'Passed'),
        ('fail', 'Failed')
    ], string='QC Result', default='pending', tracking=True)

    # ==========================================
    # NEW QC BUTTON ACTIONS
    # ==========================================
    def action_calculate_qc(self):
        """ Button 1: Evaluates the inputs and sets Pass/Fail """
        for picking in self:
            # Calculate Sums
            picking.qc_adm_sum = picking.qc_sieve + picking.qc_fm + picking.qc_flat
            picking.qc_crm_sum = picking.qc_bb + picking.qc_fragment + picking.qc_cluster
            picking.qc_td_sum = picking.qc_mould + picking.qc_insect

            # Evaluate thresholds
            adm_pass = (picking.qc_sieve <= 2.0 and picking.qc_fm < 2.0 and picking.qc_flat <= 2.0 and picking.qc_adm_sum <= 3.5)
            crm_pass = (picking.qc_bb <= 2.0 and picking.qc_fragment <= 2.0 and picking.qc_cluster <= 2.0 and picking.qc_crm_sum <= 3.5)
            td_pass = (picking.qc_mould <= 5.0 and picking.qc_insect <= 5.0 and picking.qc_td_sum <= 5.0)
            bean_bloc_pass = (picking.qc_slaty <= 7.0 and picking.qc_moisture < 8.0 and picking.qc_bean_count >= 200.0)

            # Determine Result
            if adm_pass and crm_pass and td_pass and bean_bloc_pass:
                picking.qc_status = 'pass'
                picking.quality_discount_weight = 0.0
                picking.is_qc_locked = True  # Automatically lock if it passes perfectly
            else:
                picking.qc_status = 'fail'
                # We do NOT lock it yet, so the manager can type the penalty discount

    def action_finalize_qc(self):
        """ Button 2: Locks the record after a manager inputs the penalty for a Fail """
        for picking in self:
            if picking.qc_status == 'fail' and picking.quality_discount_weight <= 0:
                raise exceptions.UserError("You must enter a Quality Discount penalty before finalizing a Failed QC.")
            
            picking.is_qc_locked = True



    @api.depends('sale_id.commodity_contract_id')
    def _compute_contract_from_sale(self):
        for picking in self:
            if picking.sale_id and picking.sale_id.commodity_contract_id:
                picking.commodity_contract_id = picking.sale_id.commodity_contract_id

    @api.depends('commodity_invoice_id')
    def _compute_is_invoiced(self):
        for picking in self:
            picking.is_invoiced = bool(picking.commodity_invoice_id)

    @api.depends('weighbridge_in', 'weighbridge_out', 'bag_count', 'moisture_discount')
    def _compute_weighbridge_weights(self):
        for picking in self:
            picking.gross_weight = picking.weighbridge_in - picking.weighbridge_out
            picking.bag_discount = picking.bag_count * 1.0  # 1 bag = 1kg
            picking.net_weight = picking.gross_weight - picking.bag_discount - (picking.gross_weight*picking.moisture_discount)

    @api.depends('net_weight', 'quality_discount_weight')
    def _compute_payable_weight(self):
        for picking in self:
            # Payable Weight is the Final Financial Quantity
            picking.payable_weight = picking.net_weight*(1 - picking.quality_discount_weight)

    @api.depends('sale_id.commodity_contract_id', 'purchase_id.commodity_contract_id')
    def _compute_contract_from_sale_or_purchase(self):
        for picking in self:
            if picking.sale_id and picking.sale_id.commodity_contract_id:
                picking.commodity_contract_id = picking.sale_id.commodity_contract_id
            elif picking.purchase_id and picking.purchase_id.commodity_contract_id:
                picking.commodity_contract_id = picking.purchase_id.commodity_contract_id

    def action_approve_qc_discount(self):
        """ This button allows a manager to approve a failed QC with a discount """
        for picking in self:
            if picking.quality_discount_weight <= 0 and picking.qc_state == 'fail':
                raise exceptions.UserError("You must specify a Quality Discount Weight before approving a failed check.")
            picking.qc_state = 'approved'

    def action_pass_qc(self):
        for picking in self:
            picking.quality_discount_weight = 0.0
            picking.qc_state = 'pass'

    def action_fail_qc(self):
        for picking in self:
            picking.qc_state = 'fail'
    
    def button_validate(self):
        # Before validating the delivery/receipt, force the inventory lines to match the Net Weight
        for picking in self:
            if picking.commodity_contract_id and picking.net_weight > 0:
                for move in picking.move_ids:
                    # Update the physical stock move quantity to the Net Weight
                    if move.product_id == picking.commodity_contract_id.product_id:
                        move.quantity = picking.net_weight
                        
        return super(StockPicking, self).button_validate()