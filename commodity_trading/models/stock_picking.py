from odoo import models, fields, api, exceptions

class StockPicking(models.Model):
    _inherit = 'stock.picking'



    # Weighbridge capture (From Step 3)
    weighbridge_in = fields.Float(string='Weighbridge IN (KG)', tracking=True)
    weighbridge_out = fields.Float(string='Weighbridge OUT / Empty Truck (KG)', tracking=True)
    gross_weight = fields.Float(string='Gross Weight (KG)', compute='_compute_weighbridge_weights', store=True)

    bag_count = fields.Integer(string='Number of Bags Used')
    bag_discount = fields.Float(string='Bag Discount (KG)', compute='_compute_weighbridge_weights', store=True)
    moisture_discount = fields.Float(string='Moisture Discount (KG)')

    net_weight = fields.Float(string='Net Received Weight (KG)', compute='_compute_weighbridge_weights', store=True)

    # ==========================================
    # STEP 4 ADDITIONS: QUALITY CONTROL
    # ==========================================
    qc_adm = fields.Float(string='ADM (%)')
    qc_crm = fields.Float(string='CRM (%)')
    qc_td = fields.Float(string='TD (%)')
    qc_slaty = fields.Float(string='Slaty (%)')
    qc_bc = fields.Float(string='Bean Count (BC)')
    
    qc_state = fields.Selection([
        ('pending', 'Pending QC'),
        ('pass', 'Passed'),
        ('fail', 'Failed'),
        ('approved', 'Approved with Discount')
    ], string='QC Status', default='pending', tracking=True)

    quality_discount_weight = fields.Float(string='Quality Discount (KG)', tracking=True, help="This does NOT reduce physical stock, only payable weight.")
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
            picking.net_weight = picking.gross_weight - picking.bag_discount - picking.moisture_discount

    @api.depends('net_weight', 'quality_discount_weight')
    def _compute_payable_weight(self):
        for picking in self:
            # Payable Weight is the Final Financial Quantity
            picking.payable_weight = picking.net_weight - picking.quality_discount_weight

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